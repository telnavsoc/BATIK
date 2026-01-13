# FILE: bin/robot_pmdt.py
# =============================================================================
# BATIK PMDT ROBOT V15.3 (STRICT DISCONNECT VALIDATION)
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
LOG_FILE = os.path.join(BASE_DIR, "live_monitor.log")     # Untuk Log History (Append)
STATUS_FILE = os.path.join(BASE_DIR, "current_status.txt") # Untuk Status Realtime (Overwrite)

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

# --- UNIFIED LOGGING (SAFETY CURTAIN) ---
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
        self.create_tables()

    def create_tables(self):
        self.cursor.execute("CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, station_name TEXT, timestamp DATETIME, evidence_path TEXT, raw_clipboard TEXT)")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS measurements (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER, parameter_name TEXT, value_mon1 TEXT, value_mon2 TEXT, FOREIGN KEY(session_id) REFERENCES sessions(id))")
        self.conn.commit()

    def save_session(self, station, evidence, raw, parsed):
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.cursor.execute("INSERT INTO sessions (station_name, timestamp, evidence_path, raw_clipboard) VALUES (?, ?, ?, ?)", (station, ts, evidence, raw))
            session_id = self.cursor.lastrowid
            
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

# --- COMPUTER VISION ---
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
        """Memastikan window PMDT aktif & restore."""
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
        """Helper untuk mengecek text di title bar."""
        if not self.hwnd: return False
        title = win32gui.GetWindowText(self.hwnd).upper()
        return keyword.upper() in title

    def start_and_login(self):
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
            
            # Sequence: Alt, s, c, n -> System Directory
            pyautogui.press("alt")
            time.sleep(0.1)
            pyautogui.press("s")
            time.sleep(0.1)
            pyautogui.press("c")
            time.sleep(0.1)
            pyautogui.press("n")
            
            time.sleep(1.5)
            pyautogui.press("enter")
            
            time.sleep(1.5)
            pyautogui.write("q")
            pyautogui.press("tab")
            pyautogui.write("qqqq")
            pyautogui.press("tab")
            pyautogui.press("enter")
            
            time.sleep(3)
            
            if self.check_title("PC REMOTE"):
                 broadcast_log("SYSTEM", "Login Successful (PC REMOTE)", "OK")
            else:
                 broadcast_log("SYSTEM", "Login Failed / No PC REMOTE", "WARN")
        
        elif self.check_title("PC REMOTE"):
            broadcast_log("SYSTEM", "Already Logged In (PC REMOTE)", "OK")
        else:
            broadcast_log("SYSTEM", "Unknown State", "WARN")

    def connect_tool(self, station, image_file, expected_keyword):
        self.force_anchor_window()
        
        # Validasi Ekstra: Jangan mulai scan kalau bukan PC REMOTE
        if not self.check_title("PC REMOTE"):
            broadcast_log(station, "WAITING FOR PC REMOTE...", "WAIT")
            for _ in range(10): # Tunggu 5 detik tambahan jika belum siap
                time.sleep(0.5)
                if self.check_title("PC REMOTE"): break
            
            if not self.check_title("PC REMOTE"):
                broadcast_log(station, "ABORT: Not in PC REMOTE state", "FAIL")
                return False

        broadcast_log(station, "Scanning target...", "SEARCH")
        img_path = os.path.join(config.ASSETS_DIR, image_file)
        
        for attempt in range(2):
            pos = locate_in_window(self.hwnd, img_path)
            if pos:
                pyautogui.moveTo(pos)
                pyautogui.click()
                time.sleep(0.3)
                pyautogui.rightClick()
                time.sleep(0.4)
                pyautogui.press("down")
                time.sleep(0.2)
                pyautogui.press("enter")
                
                for _ in range(20):
                    if self.check_title(expected_keyword):
                        broadcast_log(station, f"Connected: {expected_keyword}", "SUCCESS")
                        return True
                    time.sleep(0.5)
                break 
            
            time.sleep(1)

        broadcast_log(station, "Target Not Found / Timeout", "FAIL")
        return False

    def collect_data_sequence(self, station):
        self.force_anchor_window()

        # === 1. MONITOR DATA ===
        broadcast_log(station, "Opening Monitor Data (Alt+O, D)", "CMD")
        pyautogui.hotkey("alt", "o")
        time.sleep(0.8) 
        pyautogui.press("d")
        
        broadcast_log(station, "Stabilizing Monitor (10s)", "WAIT")
        time.sleep(10)
        
        pyperclip.copy("") 
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.5)
        raw_monitor = pyperclip.paste()
        self.save_evidence_and_db(station, raw_monitor, data_type="Monitor_Data")


        # === 2. TRANSMITTER DATA ===
        broadcast_log(station, "Opening Transmitter Data (Alt+T, D)", "CMD")
        pyautogui.hotkey("alt", "t")
        time.sleep(0.8)
        pyautogui.press("d")
        
        broadcast_log(station, "Stabilizing Transmitter (5s)", "WAIT")
        time.sleep(5)
        
        pyperclip.copy("")
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.5)
        raw_transmitter = pyperclip.paste()
        self.save_evidence_and_db(station, raw_transmitter, data_type="Transmitter_Data")

    def disconnect_tool(self):
        self.force_anchor_window()
        broadcast_log("SYSTEM", "Disconnecting (Alt+S, D)...", "CMD")
        
        # Lakukan aksi disconnect
        pyautogui.hotkey("alt", "s")
        time.sleep(0.8)
        pyautogui.press("d")
        
        # --- REVISI: LOOPING SAMPAI TITLE BERUBAH ---
        broadcast_log("SYSTEM", "Waiting for PC REMOTE...", "WAIT")
        
        is_disconnected = False
        # Cek setiap 0.5 detik, maksimal 20 kali (10 detik timeout)
        for _ in range(20):
            if self.check_title("PC REMOTE"):
                is_disconnected = True
                break
            time.sleep(0.5)
            
        if is_disconnected:
            broadcast_log("SYSTEM", "State Confirmed: PC REMOTE", "OK")
            
            # --- JEDA WAJIB SESUAI REQUEST ---
            broadcast_log("SYSTEM", "Safety Delay (3s)...", "WAIT")
            time.sleep(3) 
            # ---------------------------------
            
            return True
        else:
            broadcast_log("SYSTEM", "Disconnect Failed / Stuck", "FAIL")
            return False

    def save_evidence_and_db(self, station, raw, data_type="Monitor_Data"):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        base_folder = config.get_output_folder("PMDT", station)
        final_folder = os.path.join(base_folder, data_type)
        if not os.path.exists(final_folder):
            os.makedirs(final_folder)
        
        img_filename = f"{station}_{data_type}_{ts}.png"
        img_path = os.path.join(final_folder, img_filename)
        
        if self.hwnd:
            rect = win32gui.GetWindowRect(self.hwnd)
            with mss.mss() as sct:
                monitor = {"left":rect[0],"top":rect[1],"width":rect[2]-rect[0],"height":rect[3]-rect[1]}
                mss.tools.to_png(sct.grab(monitor).rgb, sct.grab(monitor).size, output=img_path)

        txt_filename = f"{station}_{data_type}_{ts}.txt"
        txt_path = os.path.join(final_folder, txt_filename)
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(raw)
        
        broadcast_log(station, f"Saved {data_type}", "SAVED")

        if data_type == "Monitor_Data" and len(raw) > 20:
            parsed = self.parse_text(raw)
            self.db.save_session(station, img_path, raw, parsed)

    def parse_text(self, text):
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

# --- ENTRY POINT ---
if __name__ == "__main__":
    import argparse
    
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=" * 60)
    print(" BATIK SYSTEM | PMDT ROBOT V15.3 (STRICT DISCONNECT)")
    print("=" * 60)

    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True, help="LOC, GP, MM, OM")
    args = parser.parse_args()

    target_key = args.target.upper()
    alt_map = {"LOC":"LOCALIZER", "GP":"GLIDE PATH", "MM":"MIDDLE MARKER", "OM":"OUTER MARKER"}
    if target_key in alt_map: target_key = alt_map[target_key]
        
    if target_key not in TARGET_MAP:
        broadcast_log("SYSTEM", f"Unknown Target: {target_key}", "EXIT")
        sys.exit(1)

    station_name, image_file, expected_keyword = TARGET_MAP[target_key]
    
    bot = HybridBatikRobot()
    try:
        bot.start_and_login()
        time.sleep(1)
        
        if bot.connect_tool(station_name, image_file, expected_keyword):
            bot.collect_data_sequence(station_name)
            
            if bot.disconnect_tool():
                broadcast_log(station_name, "CYCLE COMPLETED", "FINISH")
            else:
                 broadcast_log(station_name, "Disconnect Warning", "WARN")
                 sys.exit(3) # Exit code beda untuk warning disconnect
        else:
            sys.exit(2)
            
    except KeyboardInterrupt:
        broadcast_log("SYSTEM", "User Stopped", "STOP")
    except Exception as e:
        broadcast_log("SYSTEM", f"Critical Error: {e}", "CRASH")
        logging.error(traceback.format_exc())
    finally:
        bot.db.close()