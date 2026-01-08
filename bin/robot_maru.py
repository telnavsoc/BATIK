# FILE: bin/robot_maru.py
# --------------------------------------------------------------------------------
# [LAYER 0] STDERR INTERCEPTOR (PENYARING WARNING)
# --------------------------------------------------------------------------------
import sys
import os

class StderrFilter:
    def __init__(self, original_stream):
        self.original_stream = original_stream

    def write(self, message):
        if "32-bit application" in message or "UserWarning" in message:
            return 
        self.original_stream.write(message)

    def flush(self):
        self.original_stream.flush()

    def __getattr__(self, attr):
        return getattr(self.original_stream, attr)

if sys.stderr:
    sys.stderr = StderrFilter(sys.stderr)

# --------------------------------------------------------------------------------
# IMPORTS & SETUP
# --------------------------------------------------------------------------------
import warnings
import logging
import contextlib

# Filter warning standard
warnings.simplefilter("ignore")
logging.getLogger("pywinauto").setLevel(logging.CRITICAL)

try:
    from pywinauto import Application, Desktop
except ImportError:
    pass

import pyautogui
import time
import json
import win32gui
import win32con
import pyperclip
import sqlite3
import csv
import traceback
from datetime import datetime

# Import Config Pusat
import config

# Setup Logging File
if not os.path.exists(config.LOG_DIR): os.makedirs(config.LOG_DIR)
logging.basicConfig(filename=os.path.join(config.LOG_DIR, 'robot_maru.log'), level=logging.INFO, format='%(asctime)s - %(message)s')

# Konfigurasi Robot
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.5 

# Init Folders
dirs = [config.TEMP_DIR, config.DVOR_DIR, config.DME_DIR, os.path.join(config.BASE_DIR, "output")]
for d in dirs:
    if not os.path.exists(d): os.makedirs(d)

# --------------------------------------------------------------------------------
# UI HELPER (CLEAN DASHBOARD)
# --------------------------------------------------------------------------------
def print_header():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("="*92)
    print(f" BATIK SYSTEM | MARU AUTOMATION | V1.2 (CLEAN UI)")
    print(f" Mode: 64-bit Optimized | Status: Dashboard Ready")
    print("="*92)
    print(f"{'TIME':<10} | {'STATION':<15} | {'ACTION':<45} | {'STATUS'}")
    print("-" * 92)

def log_ui(station, action, status="..."):
    time_str = datetime.now().strftime("%H:%M:%S")
    print(f"{time_str:<10} | {station:<15} | {action:<45} | {status}")

# --------------------------------------------------------------------------------
# DATABASE MANAGER
# --------------------------------------------------------------------------------
class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect(config.DB_PATH)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, station_name TEXT, timestamp DATETIME, evidence_path TEXT, raw_clipboard TEXT)''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS measurements (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER, parameter_name TEXT, value_mon1 TEXT, value_mon2 TEXT, FOREIGN KEY(session_id) REFERENCES sessions(id))''')
        self.conn.commit()

    def save_to_csv_backup(self, station_name, parsed_data):
        try:
            csv_file = os.path.join(config.BASE_DIR, "output", "monitor_live.csv")
            row = {'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'station': station_name}
            for k, v in parsed_data.items():
                clean_key = k.replace(" ", "_").replace("(", "").replace(")", "").replace("-", "")
                row[clean_key] = v
            
            file_exists = os.path.isfile(csv_file)
            with open(csv_file, mode='a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=row.keys())
                if not file_exists: writer.writeheader()
                writer.writerow(row)
        except Exception: pass

    def save_session(self, station_name, evidence_path, raw_text, parsed_data):
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.cursor.execute('INSERT INTO sessions (station_name, timestamp, evidence_path, raw_clipboard) VALUES (?, ?, ?, ?)', (station_name, timestamp, evidence_path, raw_text))
            session_id = self.cursor.lastrowid
            
            data_tuples = []
            for key, val in parsed_data.items():
                data_tuples.append((session_id, key, val, "-"))
            self.cursor.executemany('INSERT INTO measurements (session_id, parameter_name, value_mon1, value_mon2) VALUES (?, ?, ?, ?)', data_tuples)
            self.conn.commit()
            
            self.save_to_csv_backup(station_name, parsed_data)
            log_ui(station_name, "Data Saved to DB & CSV", "DONE")

        except Exception as e:
            log_ui(station_name, "DB Error", "FAIL")

    def close(self): 
        if self.conn: self.conn.close()

# --------------------------------------------------------------------------------
# ROBOT CLASS
# --------------------------------------------------------------------------------
class MaruRobot:
    def __init__(self):
        self.db = DatabaseManager()
        self.app = None
        self.hwnd = 0

    def find_window_strict(self, keyword):
        target_hwnd = []
        def callback(hwnd, ctx):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if keyword in title: target_hwnd.append(hwnd)
        win32gui.EnumWindows(callback, None)
        return target_hwnd[0] if target_hwnd else 0

    def force_focus(self):
        if self.hwnd:
            try:
                if win32gui.IsIconic(self.hwnd): 
                    win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(self.hwnd)
            except:
                pyautogui.press('alt')
                try: win32gui.SetForegroundWindow(self.hwnd)
                except: pass

    def process_queue(self, targets):
        for name, keyword, engine_type in targets:
            log_ui(name, "Scanning Application...", "SEARCH")
            
            hwnd = self.find_window_strict(keyword)
            if hwnd == 0:
                log_ui(name, "App Not Found (Skipping)", "MISSING")
                continue
            
            self.hwnd = hwnd
            try:
                self.app = Application(backend="win32").connect(handle=hwnd)
            except: pass

            self.force_focus()
            time.sleep(0.5)
            
            if engine_type == "220":
                self._logic_maru_220(name)
            elif engine_type == "320":
                self._logic_maru_320(name)
            
            time.sleep(1.0)

    # === LOGIC 220 (DVOR) ===
    def _logic_maru_220(self, station_name):
        log_ui(station_name, "Focusing Window", "OK")
        
        self.force_focus()
        rect = win32gui.GetWindowRect(self.hwnd)
        
        # Klik tombol 'Main' (Hidden from UI, but active)
        pyautogui.click(rect[0] + 60, rect[1] + 80)
        time.sleep(1.0) 

        # 1. SAVE TXT
        log_ui(station_name, "Saving Text Log", "...")
        pyautogui.hotkey('ctrl', 'p')
        time.sleep(1.5) 
        
        # Masuk menu Save
        pyautogui.hotkey('alt', 's')
        time.sleep(1.5)
        
        txt_path = os.path.join(config.TEMP_DIR, f"{station_name}_temp.txt")
        self._fast_save_dialog(txt_path, is_txt=True)
        
        raw_data = self._read_txt_file(txt_path)
        if not raw_data:
            log_ui(station_name, "TXT File Empty", "WARNING")

        # Reset Focus kembali ke Main Window
        self.force_focus()
        pyautogui.click(rect[0] + 60, rect[1] + 80)
        time.sleep(0.5)
        
        # 2. PRINT PDF
        log_ui(station_name, "Printing PDF Evidence", "...")
        pyautogui.hotkey('ctrl', 'p'); time.sleep(1.0)
        pyautogui.hotkey('alt', 'p'); time.sleep(1.0)
        
        # Pilih Printer (Microsoft Print to PDF)
        pyperclip.copy('microsoft print to pdf')
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.5)
        
        pyautogui.press('enter')
        time.sleep(1.5) 
        
        pdf_path = os.path.join(config.DVOR_DIR, f"{station_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        self._fast_save_dialog(pdf_path, is_txt=False)

        if raw_data:
            self.db.save_session(station_name, pdf_path, raw_data, self.parse_maru_text(raw_data))

    # === LOGIC 320 (DME) ===
    def _logic_maru_320(self, station_name):
        log_ui(station_name, "Focusing Window", "OK")
        self.force_focus()
        rect = win32gui.GetWindowRect(self.hwnd)
        
        pyautogui.click(rect[0] + 60, rect[1] + 80)
        time.sleep(0.5)

        # 1. SAVE TXT
        log_ui(station_name, "Saving Text Log", "...")
        pyautogui.hotkey('ctrl', 'p'); time.sleep(1.5)
        pyautogui.hotkey('alt', 'a') 
        pyautogui.hotkey('alt', 's'); time.sleep(1.5)

        txt_path = os.path.join(config.TEMP_DIR, f"{station_name.replace(' ', '_')}_temp.txt")
        self._fast_save_dialog(txt_path, is_txt=True)
        raw_data = self._read_txt_file(txt_path)

        # Reset Dialog
        pyautogui.press('esc'); time.sleep(1.0)
        self.force_focus()
        pyautogui.click(rect[0] + 60, rect[1] + 80)

        # 2. PRINT PDF
        log_ui(station_name, "Printing PDF Evidence", "...")
        pyautogui.hotkey('ctrl', 'p'); time.sleep(1.5)
        
        pyautogui.press('f4'); time.sleep(0.5)
        pyautogui.press('m'); time.sleep(0.5)
        pyautogui.press('enter'); time.sleep(1.0)

        pyautogui.hotkey('alt', 'a'); time.sleep(0.5)
        pyautogui.hotkey('alt', 'o')
        time.sleep(2.0) 

        pdf_path = os.path.join(config.DME_DIR, f"{station_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        self._fast_save_dialog(pdf_path, is_txt=False)

        if raw_data:
            self.db.save_session(station_name, pdf_path, raw_data, self.parse_maru_text(raw_data))

    def _fast_save_dialog(self, full_path, is_txt):
        # Buka dialog filename (Alt+N)
        pyautogui.hotkey('alt', 'n'); time.sleep(0.5)
        
        # Paste path (Instan)
        pyperclip.copy(full_path)
        pyautogui.hotkey('ctrl', 'v'); time.sleep(0.5)
        
        # Save (Alt+S)
        pyautogui.hotkey('alt', 's'); time.sleep(1.0)
        
        if is_txt:
            # Handle "Replace?" confirm jika file sudah ada
            pyautogui.hotkey('alt', 'y'); time.sleep(0.5)
        else:
            # Tunggu proses save PDF
            time.sleep(1.5)

    def _read_txt_file(self, path):
        try:
            with open(path, 'r') as f: return f.read()
        except: return ""

    def parse_maru_text(self, text):
        data = {}
        for line in text.splitlines():
            if ":" in line:
                parts = line.split(":", 1)
                data[parts[0].strip()] = parts[1].strip()
        return data

# --------------------------------------------------------------------------------
# MAIN EXECUTION
# --------------------------------------------------------------------------------
if __name__ == "__main__":
    print_header()
    
    bot = MaruRobot()
    targets = [
        ("MARU 320", "310/320", "320"),
        ("MARU 220", "MARU 220", "220") 
    ]
    
    try:
        bot.process_queue(targets)
        
        print("-" * 92)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] SYSTEM          | BATCH JOB COMPLETED                          | FINISH")
        print("=" * 92)
        
    except KeyboardInterrupt:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] SYSTEM          | OPERATION ABORTED BY USER                    | STOP")
    except Exception as e:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] SYSTEM          | CRITICAL ERROR                               | FAIL")
        logging.error(traceback.format_exc())
    finally:
        if bot.db:
            bot.db.close()