# FILE: bin/robot_pmdt.py
# =============================================================================
# BATIK PMDT ROBOT V17.4 (STABLE V15.3 BASE + RMS FEATURE)
# =============================================================================

import sys
import os
import time
import json
import re
import sqlite3
import logging
import traceback
import ctypes
import warnings
from datetime import datetime

# GUI & Automation Imports
import pyautogui
import win32gui
import win32con
import numpy as np
import cv2
import mss
import pyperclip
from pywinauto import Application, Desktop

# Local Import
import config

# --- CONFIGURATION & PATHS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "live_monitor.log")
STATUS_FILE = os.path.join(BASE_DIR, "current_status.txt")

# PyAutoGUI Safety
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.5

# PMDT Window Target
PMDT_X, PMDT_Y, PMDT_W, PMDT_H = 2379, -1052, 1024, 768

TARGET_MAP = {
    "LOCALIZER": ("LOCALIZER", "target_loc.png", "INDONESIA SOLO"),
    "GLIDE PATH": ("GLIDE PATH", "target_gp.png", "332.9"),
    "MIDDLE MARKER": ("MIDDLE MARKER", "target_mm.png", "MIDDLE MARKER"),
    "OUTER MARKER": ("OUTER MARKER", "target_om.png", "OUTER MARKER"),
}

# --- UNIFIED LOGGING ---
def broadcast_log(module, msg, status="INFO"):
    t_str = time.strftime("%H:%M:%S")
    log_line = f"{t_str} | {module:<15} | {msg:<40} | {status}"
    print(log_line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
    except: pass
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            f.write(f"[{module}] {msg}") 
    except: pass

# --- ADMIN CHECK ---
def is_admin():
    try: return ctypes.windll.shell32.IsUserAnAdmin()
    except: return False

if __name__ == "__main__":
    if not is_admin():
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        sys.exit()

# --- SYSTEM LOGGING SETUP ---
warnings.simplefilter("ignore")
logging.basicConfig(
    filename=os.path.join(config.LOG_DIR, 'robot_debug.log'),
    level=logging.ERROR,
    format='%(asctime)s - %(message)s'
)

# --- DATABASE MANAGER ---
class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect(config.DB_PATH)
        self.conn.execute("PRAGMA journal_mode=WAL;") 
        self.cursor = self.conn.cursor()
        self.check_and_update_schema()

    def check_and_update_schema(self):
        # Memastikan tabel ada (Kode dari V15.3 + Kolom Baru V17)
        self.cursor.execute("CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, station_name TEXT, timestamp DATETIME, evidence_path TEXT, raw_clipboard TEXT)")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS measurements (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER, parameter_name TEXT, value_mon1 TEXT, value_mon2 TEXT, FOREIGN KEY(session_id) REFERENCES sessions(id))")
        
        # Penambahan Kolom Status (V17 requirement)
        try: self.cursor.execute("ALTER TABLE sessions ADD COLUMN tx_fwd_power TEXT"); broadcast_log("DB", "Added col: tx_fwd_power", "UPDATE")
        except: pass
        try: self.cursor.execute("ALTER TABLE sessions ADD COLUMN tx_ref_power TEXT")
        except: pass
        try: self.cursor.execute("ALTER TABLE sessions ADD COLUMN tx_status TEXT")
        except: pass
        self.conn.commit()

    def save_session(self, station, evidence, raw, parsed, tx_info=None):
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Default Values
            fwd, ref, stat = "-", "-", "MONITORING"
            
            if tx_info:
                fwd = tx_info.get("fwd", "-")
                ref = tx_info.get("ref", "-")
                stat = tx_info.get("status", "UNKNOWN")

            self.cursor.execute(
                "INSERT INTO sessions (station_name, timestamp, evidence_path, raw_clipboard, tx_fwd_power, tx_ref_power, tx_status) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                (station, ts, evidence, raw, fwd, ref, stat)
            )
            session_id = self.cursor.lastrowid
            
            if parsed:
                temp_measurements = {} 
                for full_key, val in parsed.items():
                    base_name = full_key.replace(" (Mon1)", "").replace(" (Mon2)", "")
                    if base_name not in temp_measurements: temp_measurements[base_name] = {"m1": "-", "m2": "-"}
                    if "(Mon1)" in full_key: temp_measurements[base_name]["m1"] = val
                    elif "(Mon2)" in full_key: temp_measurements[base_name]["m2"] = val

                rows = [(session_id, k, v["m1"], v["m2"]) for k, v in temp_measurements.items()]
                self.cursor.executemany("INSERT INTO measurements (session_id, parameter_name, value_mon1, value_mon2) VALUES (?, ?, ?, ?)", rows)
            
            self.conn.commit()
            broadcast_log(station, "Database Saved (WAL)", "DONE")
        except Exception as e:
            broadcast_log(station, f"DB Error: {e}", "FAIL")

    def close(self):
        if self.conn: self.conn.close()

# --- COMPUTER VISION (V15.3 Logic) ---
def locate_in_window(hwnd, template_path, threshold=0.55):
    if not os.path.exists(template_path): return None
    try:
        rect = win32gui.GetWindowRect(hwnd)
        w, h = rect[2] - rect[0], rect[3] - rect[1]
    except: return None
    
    with mss.mss() as sct:
        monitor = {"left": rect[0], "top": rect[1], "width": w, "height": h}
        img = np.array(sct.grab(monitor))[:, :, :3] 
    
    tpl = cv2.imread(template_path, cv2.IMREAD_COLOR)
    if tpl is None: return None
    
    res = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    
    if max_val < threshold: return None
    ih, iw = tpl.shape[:2]
    return (max_loc[0] + rect[0] + iw // 2, max_loc[1] + rect[1] + ih // 2)

# --- MAIN ROBOT LOGIC ---
class HybridBatikRobot:
    def __init__(self):
        self.db = DatabaseManager()
        self.coords = self.load_coords()
        self.hwnd = 0
        self.app = None

    def load_coords(self):
        if not os.path.exists(config.COORD_FILE): return {}
        with open(config.COORD_FILE, "r") as f: return json.load(f)

    def force_anchor_window(self):
        self.hwnd = 0
        def cb(h, _):
            title = win32gui.GetWindowText(h)
            if win32gui.IsWindowVisible(h) and ("PMDT" in title or "Selex" in title) and "About" not in title:
                self.hwnd = h
        win32gui.EnumWindows(cb, None)
        
        if not self.hwnd: return False
        try:
            if win32gui.IsIconic(self.hwnd): win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
            try: win32gui.SetForegroundWindow(self.hwnd)
            except: pyautogui.press("alt"); win32gui.SetForegroundWindow(self.hwnd)
            win32gui.MoveWindow(self.hwnd, PMDT_X, PMDT_Y, PMDT_W, PMDT_H, True)
            return True
        except: return False

    def check_title(self, keyword):
        if not self.hwnd: return False
        title = win32gui.GetWindowText(self.hwnd).upper()
        return keyword.upper() in title

    def start_and_login(self):
        # Logika Login V15.3 (Sudah stabil)
        broadcast_log("SYSTEM", "Starting PMDT...", "INIT")
        try: self.app = Application(backend="win32").connect(path=config.PATH_PMDT); self.force_anchor_window()
        except: 
            try: self.app = Application(backend="win32").start(config.PATH_PMDT)
            except: broadcast_log("SYSTEM", "Cannot open PMDT EXE", "FAIL"); return

        for _ in range(15):
            if self.force_anchor_window(): break
            time.sleep(1)
        
        if self.check_title("No Connection"):
            broadcast_log("SYSTEM", "Logging in...", "PROCESS")
            pyautogui.press("alt"); time.sleep(0.1)
            pyautogui.press("s"); time.sleep(0.1)
            pyautogui.press("c"); time.sleep(0.1)
            pyautogui.press("n")
            time.sleep(1.5); pyautogui.press("enter")
            time.sleep(1.5)
            pyautogui.write("q"); pyautogui.press("tab"); pyautogui.write("qqqq"); pyautogui.press("tab"); pyautogui.press("enter")
            time.sleep(3)
            
            if self.check_title("PC REMOTE"): broadcast_log("SYSTEM", "Login Successful", "OK")
            else: broadcast_log("SYSTEM", "Login Failed", "WARN")
        elif self.check_title("PC REMOTE"):
            broadcast_log("SYSTEM", "Already Logged In", "OK")

    def connect_tool(self, station, image_file, expected_keyword):
        # Logika Connect V15.3 (Restore Timing Original)
        self.force_anchor_window()
        
        if not self.check_title("PC REMOTE"):
            broadcast_log(station, "WAITING FOR PC REMOTE...", "WAIT")
            for _ in range(10): 
                time.sleep(0.5)
                if self.check_title("PC REMOTE"): break
            if not self.check_title("PC REMOTE"): return False

        broadcast_log(station, "Scanning target...", "SEARCH")
        img_path = os.path.join(config.ASSETS_DIR, image_file)
        
        for attempt in range(2):
            pos = locate_in_window(self.hwnd, img_path)
            if pos:
                # --- TIMING V15.3 (RESTORED) ---
                pyautogui.moveTo(pos)
                pyautogui.click()
                time.sleep(0.3)
                pyautogui.rightClick()
                time.sleep(0.4) # Timing V15.3
                pyautogui.press("down")
                time.sleep(0.2)
                pyautogui.press("enter")
                # -------------------------------

                for _ in range(20):
                    if self.check_title(expected_keyword):
                        broadcast_log(station, f"Connected: {expected_keyword}", "SUCCESS")
                        return True
                    time.sleep(0.5)
                break 
            time.sleep(1)
        return False

    def get_rms_status(self):
        """Fitur Baru: RMS Status dengan Shortcut Sekuensial"""
        broadcast_log("RMS", "Fetching Status (Alt, R, S)...", "CMD")
        
        # Shortcut khusus untuk RMS sesuai request (Sequential)
        pyautogui.press("alt")
        time.sleep(0.5)
        pyautogui.press("r")
        time.sleep(0.5)
        pyautogui.press("s")
        
        time.sleep(1.5) # Tunggu popup
        pyautogui.press("right") 
        time.sleep(0.5)
        
        pyperclip.copy("")
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.5)
        status_text = pyperclip.paste()
        
        pyautogui.press("esc")
        time.sleep(0.8) 
        return status_text

    def collect_data_sequence(self, station):
        self.force_anchor_window()

        # === 1. RMS STATUS (NEW FEATURE) ===
        # Dijalankan di awal, menggunakan fungsi barunya sendiri
        raw_rms = self.get_rms_status()
        rms_header = "="*40 + "\nRMS STATUS SNAPSHOT\n" + "="*40 + "\n" + raw_rms + "\n" + "="*40 + "\nRAW DATA DETAILS\n" + "="*40 + "\n\n"

        # === 2. MONITOR DATA (V15.3 LOGIC) ===
        # Menggunakan HOTKEY (bukan sequential) karena di V15.3 sudah stabil
        broadcast_log(station, "Getting Monitor Data...", "CMD")
        pyautogui.hotkey("alt", "o")
        time.sleep(0.8) 
        pyautogui.press("d")
        
        broadcast_log(station, "Stabilizing (10s)", "WAIT")
        time.sleep(10)
        
        pyperclip.copy(""); pyautogui.hotkey("ctrl", "c"); time.sleep(0.5)
        raw_monitor = pyperclip.paste()
        img_mon_path = self.take_screenshot(station, "Monitor_Data")

        # === 3. TRANSMITTER DATA (V15.3 LOGIC) ===
        # Menggunakan HOTKEY (bukan sequential)
        broadcast_log(station, "Getting Transmitter Data...", "CMD")
        pyautogui.hotkey("alt", "t")
        time.sleep(0.8)
        pyautogui.press("d")
        
        broadcast_log(station, "Stabilizing (5s)", "WAIT")
        time.sleep(5)
        
        pyperclip.copy(""); pyautogui.hotkey("ctrl", "c"); time.sleep(0.5)
        raw_transmitter = pyperclip.paste()
        img_tx_path = self.take_screenshot(station, "Transmitter_Data")

        # === 4. SAVE & PARSE ===
        final_monitor_text = rms_header + raw_monitor
        final_transmitter_text = rms_header + raw_transmitter
        
        # Save Monitor
        self.save_text_file(station, final_monitor_text, "Monitor_Data")
        parsed_mon = self.parse_monitor_text(raw_monitor) 
        tx_info_mon = self.parse_transmitter_with_status(raw_transmitter, raw_rms)
        self.db.save_session(station, img_mon_path, final_monitor_text, parsed_mon, tx_info=tx_info_mon)
        
        # Save Transmitter
        self.save_text_file(station, final_transmitter_text, "Transmitter_Data")
        tx_info_tx = self.parse_transmitter_with_status(raw_transmitter, raw_rms)
        broadcast_log(station, f"TX Status: {tx_info_tx['status']} ({tx_info_tx['fwd']} W)", "INFO")
        self.db.save_session(station, img_tx_path, final_transmitter_text, None, tx_info=tx_info_tx)

    def take_screenshot(self, station, data_type):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_folder = config.get_output_folder("PMDT", station)
        final_folder = os.path.join(base_folder, data_type)
        if not os.path.exists(final_folder): os.makedirs(final_folder)
        
        img_path = os.path.join(final_folder, f"{station}_{data_type}_{ts}.png")
        if self.hwnd:
            rect = win32gui.GetWindowRect(self.hwnd)
            with mss.mss() as sct:
                monitor = {"left":rect[0],"top":rect[1],"width":rect[2]-rect[0],"height":rect[3]-rect[1]}
                mss.tools.to_png(sct.grab(monitor).rgb, sct.grab(monitor).size, output=img_path)
        return img_path

    def save_text_file(self, station, content, data_type):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_folder = config.get_output_folder("PMDT", station)
        final_folder = os.path.join(base_folder, data_type)
        if not os.path.exists(final_folder): os.makedirs(final_folder)
        
        txt_path = os.path.join(final_folder, f"{station}_{data_type}_{ts}.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(content)

    def disconnect_tool(self):
        # Logika Disconnect V15.3 (Restore Timing Original)
        self.force_anchor_window()
        broadcast_log("SYSTEM", "Disconnecting...", "CMD")
        
        # Shortcut V15.3 (Hotkey)
        pyautogui.hotkey("alt", "s")
        time.sleep(0.8)
        pyautogui.press("d")
        
        # Looping Validation (dari V15.3 yang Anda sukai)
        broadcast_log("SYSTEM", "Waiting for PC REMOTE...", "WAIT")
        for _ in range(20):
            if self.check_title("PC REMOTE"):
                broadcast_log("SYSTEM", "State Confirmed: PC REMOTE", "OK")
                broadcast_log("SYSTEM", "Safety Delay (3s)...", "WAIT")
                time.sleep(3) 
                return True
            time.sleep(0.5)
        return False

    def parse_monitor_text(self, text):
        data = {}
        section = "General"
        for line in text.splitlines():
            line = line.strip()
            if not line or "Monitor" in line or "Integral" in line: continue
            if line in ["Course", "Clearance"]: section = line; continue
            parts = re.split(r"\s{2,}", line)
            if len(parts) >= 3 and "/" not in parts[0]:
                key = f"{section} - {parts[0]}"
                data[f"{key} (Mon1)"] = parts[1]
                data[f"{key} (Mon2)"] = parts[2]
        return data

    def parse_transmitter_with_status(self, wattmeter_text, status_text):
        info = {"fwd": "0.00", "ref": "0.00", "status": "OFF"}
        try:
            matches = re.findall(r"Forward Power\s+([\d\.]+)\s+Watts", wattmeter_text)
            if matches:
                powers = [float(x) for x in matches]
                max_power = max(powers)
                info["fwd"] = str(max_power)
        except: pass

        tx1_active = "G  Tx 1" in status_text
        tx2_active = "G  Tx 2" in status_text
        try: current_power = float(info["fwd"])
        except: current_power = 0.0
        
        if current_power > 1.0:
            if tx1_active and not tx2_active: info["status"] = "TX1 MAIN"
            elif tx2_active and not tx1_active: info["status"] = "TX2 MAIN"
            elif tx1_active and tx2_active: info["status"] = "BOTH ON"
            else: info["status"] = "ON AIR (UNKNOWN TX)"
        else:
             info["status"] = "OFF / DUMMY"
        return info

# --- ENTRY POINT ---
if __name__ == "__main__":
    import argparse
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=" * 60)
    print(" BATIK SYSTEM | PMDT ROBOT V17.4 (STABLE BASE)")
    print("=" * 60)

    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True, help="LOC, GP, MM, OM")
    args = parser.parse_args()

    target_key = args.target.upper()
    alt_map = {"LOC":"LOCALIZER", "GP":"GLIDE PATH", "MM":"MIDDLE MARKER", "OM":"OUTER MARKER"}
    if target_key in alt_map: target_key = alt_map[target_key]
        
    if target_key not in TARGET_MAP: sys.exit(1)

    station_name, image_file, expected_keyword = TARGET_MAP[target_key]
    bot = HybridBatikRobot()
    
    try:
        bot.start_and_login()
        time.sleep(1)
        if bot.connect_tool(station_name, image_file, expected_keyword):
            bot.collect_data_sequence(station_name)
            if bot.disconnect_tool():
                broadcast_log(station_name, "CYCLE COMPLETED", "FINISH")
            else: sys.exit(3)
        else: sys.exit(2)
    except KeyboardInterrupt: broadcast_log("SYSTEM", "User Stopped", "STOP")
    except Exception as e: 
        broadcast_log("SYSTEM", f"Error: {e}", "CRASH")
        logging.error(traceback.format_exc())
    finally: bot.db.close()