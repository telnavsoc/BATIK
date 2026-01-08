# FILE: bin/robot_pmdt.py
# --------------------------------------------------------------------------------
# [LAYER 0] STDERR INTERCEPTOR (PENYARING WARNING)
# --------------------------------------------------------------------------------
import sys
import os

class StderrFilter:
    """
    Menyaring pesan error/warning yang tidak diinginkan agar terminal bersih,
    tapi tetap meneruskan error penting agar aplikasi tidak crash.
    """
    def __init__(self, original_stream):
        self.original_stream = original_stream

    def write(self, message):
        # Filter kata kunci yang mengganggu
        if "32-bit application" in message or "UserWarning" in message:
            return 
        self.original_stream.write(message)

    def flush(self):
        self.original_stream.flush()

    def __getattr__(self, attr):
        return getattr(self.original_stream, attr)

# Aktifkan Filter segera!
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
import mss
import mss.tools
import pyperclip
import re
import sqlite3
import csv
import traceback
from datetime import datetime

# Import Config Pusat
import config

# Setup Logging File
logging.basicConfig(filename=os.path.join(config.LOG_DIR, 'robot_pmdt.log'), level=logging.INFO, format='%(asctime)s - %(message)s')

# Konfigurasi Robot
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.5 

# Pastikan folder output ada
if not os.path.exists(config.PMDT_DIR): os.makedirs(config.PMDT_DIR)
if not os.path.exists(os.path.join(config.BASE_DIR, "output")): os.makedirs(os.path.join(config.BASE_DIR, "output"))

# --------------------------------------------------------------------------------
# UI HELPER (CLEAN DASHBOARD)
# --------------------------------------------------------------------------------
def print_header():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("="*92)
    print(f" BATIK SYSTEM | PMDT AUTOMATION | V13.0 (PERFECT TIMING)")
    print(f" Mode: 64-bit Optimized | Status: Dashboard Ready")
    print("="*92)
    # Header Tabel: Time(10) | Station(15) | Action(45) | Status(Sisa)
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
            
            temp_storage = {}
            for full_key, value in parsed_data.items():
                param = full_key.replace(" (Mon1)", "").replace(" (Mon2)", "")
                if "(Mon1)" in full_key: 
                    if param not in temp_storage: temp_storage[param] = {}
                    temp_storage[param]['mon1'] = value
                elif "(Mon2)" in full_key:
                    if param not in temp_storage: temp_storage[param] = {}
                    temp_storage[param]['mon2'] = value

            data_tuples = []
            for param, vals in temp_storage.items():
                data_tuples.append((session_id, param, vals.get('mon1', '0'), vals.get('mon2', '0')))

            self.cursor.executemany('INSERT INTO measurements (session_id, parameter_name, value_mon1, value_mon2) VALUES (?, ?, ?, ?)', data_tuples)
            self.conn.commit()
            self.save_to_csv_backup(station_name, parsed_data)

        except Exception as e:
            log_ui(station_name, "DB Error", "FAIL")

    def close(self): 
        if self.conn: self.conn.close()

# --------------------------------------------------------------------------------
# ROBOT LOGIC
# --------------------------------------------------------------------------------
class HybridBatikRobot:
    def __init__(self):
        self.db = DatabaseManager()
        self.coords = self.load_coords()
        self.app = None
        self.main_win = None
        self.hwnd = 0

    def load_coords(self):
        if not os.path.exists(config.COORD_FILE): return {}
        with open(config.COORD_FILE, 'r') as f: return json.load(f)

    def get_coord(self, key):
        if key in self.coords.get("buttons", {}):
            btn = self.coords["buttons"][key]
            return btn["x"], btn["y"]
        return None, None

    def force_anchor_window(self):
        self.hwnd = 0
        def callback(h, _):
            text = win32gui.GetWindowText(h)
            if win32gui.IsWindowVisible(h) and ("PMDT" in text or "Selex" in text) and "About" not in text: 
                self.hwnd = h
        win32gui.EnumWindows(callback, None)

        if self.hwnd:
            try:
                if win32gui.IsIconic(self.hwnd): win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
                try: win32gui.SetForegroundWindow(self.hwnd)
                except: pyautogui.press('alt'); win32gui.SetForegroundWindow(self.hwnd)
                x, y, w, h = config.PMDT_ANCHOR
                win32gui.MoveWindow(self.hwnd, x, y, w, h, True)
                return True
            except: return False
        return False

    def handle_unexpected_popup(self):
        try:
            desktop = Desktop(backend="win32")
            if desktop.window(title="About").exists():
                try: desktop.window(title="About").OK.click()
                except: pyautogui.press('enter'); pyautogui.press('esc')
                time.sleep(0.5)
        except Exception: pass

    def start_and_login(self):
        log_ui("SYSTEM", "Initializing Application", "START")
        self.force_anchor_window()
        
        found = False
        try:
            self.app = Application(backend="win32").connect(path=config.PATH_PMDT)
            found = True
        except:
            try:
                self.app = Application(backend="win32").start(config.PATH_PMDT)
            except Exception as e:
                # Fallback start manual
                try:
                    os.startfile(config.PATH_PMDT)
                    time.sleep(5)
                    self.app = Application(backend="win32").connect(path=config.PATH_PMDT)
                except:
                    log_ui("SYSTEM", "EXE Not Found", "FAIL")
                    return

            for i in range(15):
                if self.force_anchor_window():
                    found = True; break
                time.sleep(1)
        
        if not found:
            log_ui("SYSTEM", "Launch Timeout", "ERROR")
            return

        self.handle_unexpected_popup()
        try: self.main_win = self.app.window(title_re=".*PMDT.*")
        except: pass
        
        if self.main_win and "No Connection" in self.main_win.window_text():
            log_ui("SYSTEM", "Authenticating User", "...")
            try: self.main_win.menu_select("System->Connect->Network")
            except: pyautogui.press(['alt', 's', 'c', 'n'])
            time.sleep(2)
            
            desktop = Desktop(backend="win32")
            if desktop.window(title=" System Directory").exists():
                dlg = desktop.window(title=" System Directory")
                try: dlg.Connect.click()
                except: dlg.Button5.click()
            
            time.sleep(1)
            if desktop.window(title="Login").exists():
                dlg = desktop.window(title="Login")
                dlg.Edit1.set_text("q"); dlg.Edit2.set_text("qqqq")
                dlg.OK.click()
                time.sleep(3) 
            log_ui("SYSTEM", "Login Successful", "OK")
        else:
            log_ui("SYSTEM", "Application Ready", "OK")

    def find_and_connect(self, station_name, image_file, expected_keyword):
        self.force_anchor_window()
        self.handle_unexpected_popup()
        
        title_now = win32gui.GetWindowText(self.hwnd).upper()
        if expected_keyword.upper() in title_now:
             log_ui(station_name, "Already Connected", "CONNECTED")
             return True

        log_ui(station_name, "Scanning Target...", "SEARCH")
        
        for attempt in range(2): 
            img_path = os.path.join(config.ASSETS_DIR, image_file)
            try:
                location = pyautogui.locateCenterOnScreen(img_path, confidence=0.7, grayscale=True, region=(0, 100, 300, 600))
            except Exception:
                location = None 

            if location and location.x < 300:
                pyautogui.moveTo(location); pyautogui.click(); time.sleep(0.2)         
                pyautogui.rightClick(); time.sleep(0.5) 
                pyautogui.press('down'); time.sleep(0.2); pyautogui.press('enter')
                
                connected = False
                for _ in range(16):
                    self.handle_unexpected_popup()
                    if expected_keyword.upper() in win32gui.GetWindowText(self.hwnd).upper():
                        connected = True; break
                    time.sleep(0.5)
                
                if connected:
                    log_ui(station_name, "Connection Established", "SUCCESS")
                    return True
                else:
                    pyautogui.click(10, 200) # Retry click
            else:
                time.sleep(1)
        
        log_ui(station_name, "Target Not Found (Skip)", "FAILED")
        return False

    def collect_data_and_disconnect(self, station_name, expected_keyword):
        x_mon, y_mon = self.get_coord("monitor")
        x_dat, y_dat = self.get_coord("data")
        x_copy, y_copy = self.get_coord("btn_copy")

        if x_mon and x_dat and x_copy:
            # 1. Klik MONITOR
            pyautogui.click(x_mon, y_mon)
            
            # [FIX CRUCIAL] PERLAMBAT JEDA AGAR MENU TURUN DULU
            time.sleep(1.5) 
            
            # 2. Klik DATA
            pyautogui.click(x_dat, y_dat)
            
            # 3. VISUAL COUNTDOWN
            time_str = datetime.now().strftime("%H:%M:%S")
            action_text = "Stabilizing Data (8s)"
            # Prefix Alignment agar rata
            prefix = f"{time_str:<10} | {station_name:<15} | {action_text:<45} | "
            print(f"{prefix}", end="", flush=True)
            
            for i in range(8, 0, -1):
                print(f"{i}..", end="", flush=True)
                time.sleep(1)
            print("OK") # Newline
            
            # 4. Copy Process
            pyperclip.copy("") 
            pyautogui.click(x_copy, y_copy)
            time.sleep(2.0) 
            
            raw_text = pyperclip.paste()
            if raw_text and len(raw_text) > 20:
                self.save_evidence_and_db(station_name, raw_text)
            else:
                log_ui(station_name, "Clipboard Empty", "WARNING")
        else:
             log_ui(station_name, "Coordinates Missing", "ERROR")
        
        self.clean_disconnect()

    def clean_disconnect(self):
        self.force_anchor_window()
        self.handle_unexpected_popup()
        pyautogui.moveTo(10, 10) 
        pyautogui.press('esc'); time.sleep(0.5)
        
        x_sys, y_sys = self.get_coord("System")
        x_disc, y_disc = self.get_coord("btn_disconnect")
        
        if x_sys and y_sys and x_disc and y_disc:
            pyautogui.click(x_sys, y_sys); time.sleep(0.3) 
            pyautogui.click(x_disc, y_disc)
            pyautogui.moveTo(5, 5) 
            
            for _ in range(10):
                if "PC REMOTE" in win32gui.GetWindowText(self.hwnd).upper(): break
                time.sleep(0.5)
        time.sleep(2)

    def take_screenshot(self, filepath):
        if self.hwnd:
            rect = win32gui.GetWindowRect(self.hwnd)
            with mss.mss() as sct:
                monitor = {"top": rect[1], "left": rect[0], "width": rect[2]-rect[0], "height": rect[3]-rect[1]}
                mss.tools.to_png(sct.grab(monitor).rgb, sct.grab(monitor).size, output=filepath)

    def save_evidence_and_db(self, name, raw_text):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        station_dir = os.path.join(config.PMDT_DIR, name)
        if not os.path.exists(station_dir): os.makedirs(station_dir)
            
        evidence_file = os.path.join(station_dir, f"{name}_{timestamp}.png")
        self.take_screenshot(evidence_file)
        parsed = self.parse_text(raw_text)
        self.db.save_session(name, evidence_file, raw_text, parsed)
        
        log_ui(name, "Evidence & Data Saved", "DONE")

    def parse_text(self, text):
        data = {}
        current_sec = "General"
        for line in text.splitlines():
            line = line.strip()
            if not line or "Monitor" in line or "Integral" in line: continue
            if line in ["Course", "Clearance"]: current_sec = line; continue
            parts = re.split(r'\s{2,}', line)
            if len(parts) >= 3 and "/" not in parts[0]:
                key = f"{current_sec} - {parts[0]}"
                data[f"{key} (Mon1)"] = parts[1]
                data[f"{key} (Mon2)"] = parts[2]
        return data

# --------------------------------------------------------------------------------
# MAIN EXECUTION
# --------------------------------------------------------------------------------
if __name__ == "__main__":
    print_header()
    
    bot = HybridBatikRobot()
    
    try:
        bot.start_and_login()
        
        targets = [
            ("LOCALIZER",     "target_loc.png", "LOCALIZER"), 
            ("GLIDE PATH",    "target_gp.png",  "GLIDE"),     
            ("MIDDLE MARKER", "target_mm.png",  "MIDDLE"),    
            ("OUTER MARKER",  "target_om.png",  "OUTER")      
        ]
        
        for name, img, keyword in targets:
            is_connected = bot.find_and_connect(name, img, keyword)
            if is_connected:
                bot.collect_data_and_disconnect(name, keyword)
            else:
                pass
            time.sleep(1.0) 
        
        print("-" * 92)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] SYSTEM          | BATCH JOB COMPLETED                          | FINISH")
        print("=" * 92)

    except KeyboardInterrupt:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] SYSTEM          | OPERATION ABORTED BY USER                    | STOP")
    except Exception as e:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] SYSTEM          | CRITICAL ERROR                               | FAIL")
        logging.error(traceback.format_exc())
    finally:
        if bot.db: bot.db.close()