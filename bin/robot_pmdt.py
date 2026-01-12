# FILE: bin/robot_pmdt.py
# =============================================================================
# BATIK PMDT ROBOT V14.4 (CLEANSED & SAFETY CURTAIN INTEGRATED)
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
    "LOCALIZER": ("LOCALIZER", "target_loc.png", "LOCALIZER"),
    "GLIDE PATH": ("GLIDE PATH", "target_gp.png", "GLIDE"),
    "MIDDLE MARKER": ("MIDDLE MARKER", "target_mm.png", "MIDDLE"),
    "OUTER MARKER": ("OUTER MARKER", "target_om.png", "OUTER"),
}

# --- UNIFIED LOGGING (SAFETY CURTAIN) ---
def broadcast_log(module, msg, status="INFO"):
    """
    Fungsi tunggal untuk:
    1. Print ke Terminal
    2. Tulis ke live_monitor.log (Append)
    3. Tulis ke current_status.txt (Overwrite untuk Curtain UI)
    """
    t_str = time.strftime("%H:%M:%S")
    # Format untuk Terminal & Log File
    log_line = f"{t_str} | {module:<15} | {msg:<40} | {status}"
    
    # 1. Print Terminal
    print(log_line)
    
    # 2. Append Log File
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
    except: pass

    # 3. Update Status File (Hanya pesan terakhir untuk UI)
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            # Format ringkas untuk file status jika diperlukan Curtain
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
# Filter user warnings dari library 32-bit/64-bit mismatch
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
        self.conn.execute("PRAGMA journal_mode=WAL;") # Performance Mode
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
        img = np.array(sct.grab(monitor))[:, :, :3] # Remove Alpha channel
    
    tpl = cv2.imread(template_path, cv2.IMREAD_COLOR)
    if tpl is None: return None
    
    res = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    
    if max_val < threshold: return None
    ih, iw = tpl.shape[:2]
    # Return center point absolute coordinates
    return (max_loc[0] + rect[0] + iw // 2, max_loc[1] + rect[1] + ih // 2)

# --- MAIN ROBOT LOGIC ---
class HybridBatikRobot:
    def __init__(self):
        self.db = DatabaseManager()
        self.coords = self.load_coords()
        self.hwnd = 0
        self.app = None
        self.main_win = None

    def load_coords(self):
        if not os.path.exists(config.COORD_FILE): return {}
        with open(config.COORD_FILE, "r") as f: return json.load(f)

    def get_coord(self, key):
        if key in self.coords.get("buttons", {}):
            c = self.coords["buttons"][key]
            return c["x"], c["y"]
        return None, None

    def force_anchor_window(self):
        """Memastikan window PMDT aktif, restore jika minimize, dan pindah ke monitor sekunder."""
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
            
            # Pindahkan window ke posisi monitor monitoring
            win32gui.MoveWindow(self.hwnd, PMDT_X, PMDT_Y, PMDT_W, PMDT_H, True)
            return True
        except: return False

    def handle_unexpected_popup(self):
        """Menangani popup 'About' atau error kecil lainnya."""
        try:
            d = Desktop(backend="win32")
            if d.window(title="About").exists():
                try: d.window(title="About").OK.click()
                except: pyautogui.press("enter"); pyautogui.press("esc")
                time.sleep(0.3)
        except: pass

    def start_and_login(self):
        broadcast_log("SYSTEM", "Starting PMDT...", "INIT")
        
        # 1. Try Connect existing or Start new
        try: self.app = Application(backend="win32").connect(path=config.PATH_PMDT); self.force_anchor_window()
        except: 
            try: self.app = Application(backend="win32").start(config.PATH_PMDT)
            except: broadcast_log("SYSTEM", "Cannot open PMDT EXE", "FAIL"); return

        # 2. Wait for Window
        for _ in range(15):
            if self.force_anchor_window(): break
            time.sleep(1)
        self.handle_unexpected_popup()

        # 3. Check Connection / Login
        try: self.main_win = self.app.window(title_re=".*PMDT.*")
        except: self.main_win = None

        if self.main_win and "No Connection" in self.main_win.window_text():
            broadcast_log("SYSTEM", "Login Required", "PROCESS")
            # Trigger Menu Connect -> Network
            try: self.main_win.menu_select("System->Connect->Network")
            except: pyautogui.press(["alt", "s", "c", "n"])
            
            time.sleep(2)
            desk = Desktop(backend="win32")
            
            # Handle System Directory Dialog
            if desk.window(title=" System Directory").exists():
                dlg = desk.window(title=" System Directory")
                try: dlg.Connect.click()
                except: dlg.Button5.click() # Button5 biasanya Connect
            
            time.sleep(1)
            # Handle Login Dialog
            if desk.window(title="Login").exists():
                dlg = desk.window(title="Login")
                dlg.Edit1.set_text("q")      # User
                dlg.Edit2.set_text("qqqq")   # Pass
                dlg.OK.click()
            
            time.sleep(3)
            broadcast_log("SYSTEM", "Login Successful", "OK")
        else:
            broadcast_log("SYSTEM", "Application Ready", "OK")

    def find_and_connect(self, station, image_file, expected_keyword):
        self.force_anchor_window()
        self.handle_unexpected_popup()
        
        # Cek jika sudah connect ke station yang benar
        curr_title = win32gui.GetWindowText(self.hwnd).upper()
        if expected_keyword.upper() in curr_title:
            broadcast_log(station, "Already Connected", "CONNECTED")
            return True

        broadcast_log(station, "Scanning target...", "SEARCH")
        img_path = os.path.join(config.ASSETS_DIR, image_file)
        
        # Try scanning 2 times
        for _ in range(2):
            pos = locate_in_window(self.hwnd, img_path)
            if pos:
                # LOGIC KLIK MENU TREE
                pyautogui.moveTo(pos)
                pyautogui.click()
                time.sleep(0.3)
                pyautogui.rightClick()
                time.sleep(0.4)
                pyautogui.press("down") # Select 'Connect' context menu
                time.sleep(0.2)
                pyautogui.press("enter")
                
                # Wait for title change indicating connection
                for __ in range(16):
                    if expected_keyword.upper() in win32gui.GetWindowText(self.hwnd).upper():
                        broadcast_log(station, "Connection Established", "SUCCESS")
                        return True
                    self.handle_unexpected_popup()
                    time.sleep(0.4)
            time.sleep(1)
            
        broadcast_log(station, "Target Not Found", "FAIL")
        return False

    def collect_data_and_disconnect(self, station, expected_keyword):
        x_mon, y_mon = self.get_coord("monitor")
        x_dat, y_dat = self.get_coord("data")
        x_copy, y_copy = self.get_coord("btn_copy")

        if not all([x_mon, y_mon, x_dat, y_dat, x_copy, y_copy]):
            broadcast_log(station, "Coords Missing in JSON", "FAIL")
            return

        # Klik Tab Monitor -> Klik Tab Data
        pyautogui.click(x_mon, y_mon); time.sleep(1.5)
        pyautogui.click(x_dat, y_dat)
        
        # STABILISASI DATA (COUNTDOWN)
        broadcast_log(station, "Stabilizing Data (10s)", "WAIT")
        # Visual countdown di terminal saja agar tidak spam log
        for i in range(10, 0, -1):
            print(f"Sampling... {i}", end="\r")
            time.sleep(1)
        print("Sampling... OK  ")

        # COPY DATA
        pyperclip.copy("") # Clear clipboard first
        pyautogui.click(x_copy, y_copy)
        time.sleep(2) # Tunggu Windows copy buffer
        raw = pyperclip.paste()

        if raw and len(raw) > 20:
            self.save_evidence_and_db(station, raw)
        else:
            broadcast_log(station, "Clipboard empty/fail", "WARN")
            
        self.clean_disconnect()

    def clean_disconnect(self):
        """Disconnect rapi untuk persiapan next station"""
        self.force_anchor_window()
        self.handle_unexpected_popup()
        pyautogui.press("esc") # Tutup menu melayang jika ada
        time.sleep(0.4)
        
        x_sys, y_sys = self.get_coord("System")
        x_disc, y_disc = self.get_coord("btn_disconnect")
        
        if x_sys and y_sys:
            pyautogui.click(x_sys, y_sys)
            time.sleep(0.3)
            pyautogui.click(x_disc, y_disc)
        time.sleep(2)

    def save_evidence_and_db(self, station, raw):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder = config.get_output_folder("PMDT", station)
        
        # 1. Evidence Screenshot (Hanya area Window PMDT)
        img_filename = f"{station}_{ts}.png"
        img_path = os.path.join(folder, img_filename)
        if self.hwnd:
            rect = win32gui.GetWindowRect(self.hwnd)
            with mss.mss() as sct:
                mss.tools.to_png(
                    sct.grab({"left":rect[0],"top":rect[1],"width":rect[2]-rect[0],"height":rect[3]-rect[1]}).rgb, 
                    sct.grab({"left":rect[0],"top":rect[1],"width":rect[2]-rect[0],"height":rect[3]-rect[1]}).size, 
                    output=img_path
                )

        # 2. Raw Text File
        txt_filename = f"{station}_{ts}.txt"
        txt_path = os.path.join(folder, txt_filename)
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(raw)
        broadcast_log(station, "Raw Data Saved", "OK")

        # 3. SQLite Database
        parsed = self.parse_text(raw)
        self.db.save_session(station, img_path, raw, parsed)

    def parse_text(self, text):
        data = {}
        section = "General"
        for line in text.splitlines():
            line = line.strip()
            # Skip baris tidak penting
            if not line or "Monitor" in line or "Integral" in line: continue
            if line in ["Course", "Clearance"]: section = line; continue
            
            parts = re.split(r"\s{2,}", line) # Split berdasarkan 2 spasi atau lebih
            if len(parts) >= 3 and "/" not in parts[0]:
                key = f"{section} - {parts[0]}"
                data[f"{key} (Mon1)"] = parts[1]
                data[f"{key} (Mon2)"] = parts[2]
        return data

# --- ENTRY POINT ---
if __name__ == "__main__":
    import argparse
    
    # Print Header
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=" * 60)
    print(" BATIK SYSTEM | PMDT ROBOT V14.4 (SAFETY INTEGRATED)")
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
        if bot.find_and_connect(station_name, image_file, expected_keyword):
            bot.collect_data_and_disconnect(station_name, expected_keyword)
            broadcast_log(station_name, "TASK COMPLETED", "FINISH")
        else:
            sys.exit(2)
    except KeyboardInterrupt:
        broadcast_log("SYSTEM", "User Stopped", "STOP")
    except Exception as e:
        broadcast_log("SYSTEM", f"Critical Error: {e}", "CRASH")
        logging.error(traceback.format_exc())
    finally:
        bot.db.close()