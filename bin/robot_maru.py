# FILE: bin/robot_maru.py
# =============================================================================
# BATIK MARU ROBOT V14.4 (CURTAIN INTEGRATED & CLEAN)
# =============================================================================

import sys
import os
import time
import logging
import sqlite3
import traceback
import argparse
import ctypes
import shutil
import warnings
from datetime import datetime

# GUI Automation
import win32gui
import win32con
import pyautogui
import pyperclip

# Local Import
import config

# --- CONFIGURATION & PATHS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "live_monitor.log")      # Append History
STATUS_FILE = os.path.join(BASE_DIR, "current_status.txt") # Overwrite Realtime

# PyAutoGUI Settings
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.5

# --- UNIFIED LOGGING (SAFETY CURTAIN) ---
def broadcast_log(module, msg, status="INFO"):
    """
    Mengirim log ke:
    1. Terminal (Print)
    2. live_monitor.log (History)
    3. current_status.txt (Untuk UI Safety Curtain)
    """
    t_str = time.strftime("%H:%M:%S")
    log_line = f"{t_str} | {module:<15} | {msg:<40} | {status}"
    
    # 1. Terminal
    print(log_line)
    
    # 2. Log File
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
    except: pass

    # 3. Curtain Status
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

# --- SETUP ---
warnings.simplefilter("ignore")
os.makedirs(config.LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(config.LOG_DIR, "robot_maru_debug.log"),
    level=logging.ERROR,
    format="%(asctime)s - %(message)s"
)

# --- DATABASE MANAGER (WAL MODE) ---
class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect(config.DB_PATH)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        self.cursor.execute("CREATE TABLE IF NOT EXISTS sessions(id INTEGER PRIMARY KEY AUTOINCREMENT, station_name TEXT, timestamp DATETIME, evidence_path TEXT, raw_clipboard TEXT)")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS measurements(id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER, parameter_name TEXT, value_mon1 TEXT, value_mon2 TEXT, FOREIGN KEY(session_id) REFERENCES sessions(id))")
        self.conn.commit()

    def save_session(self, station, pdf_path, raw, parsed):
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.cursor.execute("INSERT INTO sessions(station_name,timestamp,evidence_path,raw_clipboard) VALUES(?,?,?,?)", (station, ts, pdf_path, raw))
            sid = self.cursor.lastrowid
            
            # Maru biasanya Single Value, kita set Mon2 jadi "-"
            rows = [(sid, k, v, "-") for k,v in parsed.items()]
            self.cursor.executemany("INSERT INTO measurements(session_id,parameter_name,value_mon1,value_mon2) VALUES(?,?,?,?)", rows)
            self.conn.commit()
            broadcast_log(station, "Database Saved (WAL)", "DONE")
        except Exception as e:
            broadcast_log(station, f"DB Error: {e}", "FAIL")

    def close(self):
        if self.conn: self.conn.close()

# --- MAIN ROBOT LOGIC ---
class MaruRobot:
    def __init__(self, mode):
        self.mode = mode.upper()
        self.db = DatabaseManager()
        self.hwnd = 0
        
        if "220" in self.mode:
            self.target_key = "220"
            self.station_name = "DVOR"
            self.temp_txt = "DVOR_temp.txt"
        else:
            self.target_key = "320"
            self.station_name = "DME"
            self.temp_txt = "DME_temp.txt"

        self.out_dir = config.get_output_folder("MARU", self.station_name)
        os.makedirs(config.TEMP_DIR, exist_ok=True)

    def find_window(self):
        target = 0
        def cb(h, p):
            nonlocal target
            if win32gui.IsWindowVisible(h) and self.target_key in win32gui.GetWindowText(h): target = h
        win32gui.EnumWindows(cb, None)
        return target

    def focus_and_click_main(self):
        if not self.hwnd: return False
        try:
            if win32gui.IsIconic(self.hwnd): win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(self.hwnd)
            time.sleep(0.5)
            rect = win32gui.GetWindowRect(self.hwnd)
            # Klik area aman untuk memastikan fokus
            pyautogui.click(rect[0] + 50, rect[1] + 10)
            time.sleep(0.2)
            pyautogui.click(rect[0] + 60, rect[1] + 80)
            time.sleep(0.5)
            return True
        except: return False

    def save_dialog(self, full_path, is_txt):
        """Menangani dialog Save As Windows"""
        pyautogui.hotkey("alt", "n")
        time.sleep(0.3)
        pyperclip.copy(full_path)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.3)
        pyautogui.hotkey("alt", "s") # Save
        time.sleep(0.8)
        
        if is_txt:
            # Jika replace existing file (Yes)
            pyautogui.hotkey("alt", "y")
            time.sleep(0.3)
        else:
            # PDF butuh waktu lebih lama render
            time.sleep(2.0)

    def read_file(self, f):
        try: 
            with open(f, "r") as x: return x.read()
        except: return ""

    def parse(self, raw):
        out = {}
        for line in raw.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                out[k.strip()] = v.strip()
        return out

    def run_job(self):
        broadcast_log(self.station_name, "Finding Window...", "SEARCH")
        self.hwnd = self.find_window()
        if not self.hwnd:
            broadcast_log(self.station_name, "Window Not Found", "MISSING")
            return

        # --- 1. Save TXT (Temp) ---
        self.focus_and_click_main()
        broadcast_log(self.station_name, "Saving Log (TXT)", "PROCESS")
        
        # LOGIKA HOTKEY (Dijaga Asli sesuai Permintaan)
        if "220" in self.mode:
            pyautogui.hotkey("ctrl", "p")
            time.sleep(1.0)
            pyautogui.hotkey("alt", "s")
            time.sleep(1.0)
        else:
            pyautogui.hotkey("ctrl", "p")
            time.sleep(1.0)
            pyautogui.hotkey("alt", "a")
            # Split line agar aman
            pyautogui.hotkey("alt", "s") 
            time.sleep(1.0)

        temp_txt_path = os.path.join(config.TEMP_DIR, self.temp_txt)
        self.save_dialog(temp_txt_path, True)
        raw = self.read_file(temp_txt_path)

        # --- 2. Print PDF ---
        broadcast_log(self.station_name, "Printing Evidence (PDF)", "PROCESS")
        pyautogui.press("esc") # Clear dialog sisa jika ada
        time.sleep(0.5)
        self.focus_and_click_main()
        
        pyautogui.hotkey("ctrl", "p")
        time.sleep(1.0)
        
        # Select 'Microsoft Print to PDF' logic
        if "220" in self.mode:
            pyautogui.hotkey("alt", "p")
            time.sleep(0.3)
            pyautogui.press(["f4", "m", "enter"])
            time.sleep(0.3)
            pyautogui.press("enter")
            time.sleep(1.5)
        else:
            pyautogui.press(["f4", "m", "enter"])
            time.sleep(0.5)
            pyautogui.hotkey("alt", "a")
            time.sleep(0.3)
            pyautogui.hotkey("alt", "o")
            time.sleep(1.5)

        file_base = f"{self.station_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        pdf_path = os.path.join(self.out_dir, f"{file_base}.pdf")
        self.save_dialog(pdf_path, False)

        # --- 3. Finalize ---
        if raw:
            perm_txt = os.path.join(self.out_dir, f"{file_base}.txt")
            try: shutil.copy(temp_txt_path, perm_txt)
            except: pass
            
            self.db.save_session(self.station_name, pdf_path, raw, self.parse(raw))
        
        broadcast_log(self.station_name, "Job Completed", "SUCCESS")

# --- ENTRY POINT ---
if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=" * 60)
    print(" BATIK SYSTEM | MARU ROBOT V14.4 (CURTAIN INTEGRATED)")
    print("=" * 60)
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--DVOR", action="store_true")
    parser.add_argument("--DME", action="store_true")
    args = parser.parse_args()
    
    # Jika tidak ada argumen, jalankan keduanya (Default behavior lama)
    run_all = not (args.DVOR or args.DME)
    
    try:
        if args.DVOR or run_all:
            bot1 = MaruRobot("220")
            bot1.run_job() 
            if args.DME or run_all: time.sleep(2)
            
        if args.DME or run_all:
            bot2 = MaruRobot("320")
            bot2.run_job()   
            
    except KeyboardInterrupt:
        broadcast_log("SYSTEM", "User Stopped", "STOP")
    except Exception as e:
        broadcast_log("SYSTEM", f"Critical Error: {e}", "CRASH")
        logging.error(traceback.format_exc())