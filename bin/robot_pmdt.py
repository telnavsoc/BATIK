# FILE: bin/robot_pmdt.py
from pywinauto import Application, Desktop
import pyautogui
import time
import sys
import os
import json
import win32gui
import win32con
import mss
import mss.tools
import pyperclip
import re
import sqlite3
import logging
from datetime import datetime

# Import Config Pusat
import config

# Setup Logging
logging.basicConfig(filename=os.path.join(config.LOG_DIR, 'robot_pmdt.log'), level=logging.INFO, format='%(asctime)s - %(message)s')

# Safety
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.8 

# Pastikan folder output PMDT ada
if not os.path.exists(config.PMDT_DIR): os.makedirs(config.PMDT_DIR)

# --- DATABASE ---
class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect(config.DB_PATH)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, station_name TEXT, timestamp DATETIME, evidence_path TEXT, raw_clipboard TEXT)''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS measurements (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER, parameter_name TEXT, value_mon1 TEXT, value_mon2 TEXT, FOREIGN KEY(session_id) REFERENCES sessions(id))''')
        self.conn.commit()

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
            print(f"   💾 [DB] Data {station_name} tersimpan.")
            logging.info(f"Data saved: {station_name}")
        except Exception as e: 
            print(f"   ❌ [DB Error] {e}")
            logging.error(f"DB Error: {e}")

    def close(self): self.conn.close()

# --- ROBOT ---
class HybridBatikRobot:
    def __init__(self):
        self.db = DatabaseManager()
        self.coords = self.load_coords()
        self.app = None
        self.main_win = None
        self.hwnd = 0

    def load_coords(self):
        if not os.path.exists(config.COORD_FILE): 
            print(f"⚠️ Warning: Config file not found: {config.COORD_FILE}")
            return {}
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
                print("   ⚠️ POPUP DETECTED: Menutup paksa...")
                try: desktop.window(title="About").OK.click()
                except: pyautogui.press('enter'); pyautogui.press('esc')
                time.sleep(1)
        except Exception: pass

    def start_and_login(self):
        print("🚀 Memulai Aplikasi PMDT...")
        self.force_anchor_window()
        try:
            self.app = Application(backend="win32").connect(path=config.PATH_PMDT)
        except:
            print(f"   Launching from: {config.PATH_PMDT}")
            self.app = Application(backend="win32").start(config.PATH_PMDT)
            time.sleep(10)
        
        self.handle_unexpected_popup()
        try:
            self.main_win = self.app.window(title_re=".*PMDT.*")
        except: pass
        
        # --- LOGIN LOGIC (RESTORED FROM FINAL VERSION) ---
        if self.main_win and "No Connection" in self.main_win.window_text():
            print("🔐 Melakukan Login System...")
            try: self.main_win.menu_select("System->Connect->Network")
            except: pyautogui.press(['alt', 's', 'c', 'n'])
            
            time.sleep(2)
            desktop = Desktop(backend="win32")
            
            # --- BAGIAN YANG HILANG KEMARIN (KLIK CONNECT) ---
            if desktop.window(title=" System Directory").exists():
                dlg = desktop.window(title=" System Directory")
                print("   🖱️ Klik tombol Connect di System Directory...")
                try: dlg.Connect.click()
                except: dlg.Button5.click()
            
            time.sleep(1)
            if desktop.window(title="Login").exists():
                dlg = desktop.window(title="Login")
                dlg.Edit1.set_text("q"); dlg.Edit2.set_text("qqqq")
                dlg.OK.click()
                print("   ✅ Login Credentials Dikirim.")
                time.sleep(5)

    def find_and_connect(self, station_name, image_file, expected_keyword):
        print(f"\n⚙️ MEMPROSES: {station_name}")
        self.force_anchor_window()
        self.handle_unexpected_popup()
        
        for attempt in range(3):
            title_now = win32gui.GetWindowText(self.hwnd).upper()
            if expected_keyword.upper() in title_now:
                 print(f"      ℹ️ Sudah terkoneksi ke {station_name}.")
                 return True

            print(f"   🔎 Percobaan #{attempt+1}...")
            # Path gambar dari config yang sudah diperbaiki
            img_path = os.path.join(config.ASSETS_DIR, image_file)
            
            if not os.path.exists(img_path):
                print(f"   ❌ ERROR: File gambar tidak ditemukan: {img_path}")
                return False

            search_region = (0, 100, 300, 600) 
            location = pyautogui.locateCenterOnScreen(img_path, confidence=0.7, grayscale=True, region=search_region)
            
            if location and location.x < 300:
                print(f"      📍 Ditemukan di {location}")
                pyautogui.moveTo(location)
                pyautogui.click()       
                time.sleep(0.5)         
                pyautogui.rightClick()  
                time.sleep(1.0) 
                
                print("      ⌨️ Memilih menu Connect...")
                pyautogui.press('down'); time.sleep(0.2); pyautogui.press('enter')
                
                print("   ⏳ Menunggu loading (8s)...")
                time.sleep(8) 
                
                self.handle_unexpected_popup()
                final_title = win32gui.GetWindowText(self.hwnd).upper()
                
                if expected_keyword.upper() in final_title:
                    print(f"      ✅ Sukses Masuk.")
                    return True
                else:
                    print(f"      ❌ GAGAL: Judul '{final_title}' tidak sesuai.")
                    pyautogui.click(10, 200) 
            else:
                print(f"   ❌ Gambar target tidak terdeteksi.")
                time.sleep(2)
        return False

    def collect_data_and_disconnect(self, station_name, expected_keyword):
        current_title = win32gui.GetWindowText(self.hwnd).upper()
        if "PC REMOTE" in current_title or "NO CONNECTION" in current_title:
            print(f"   ⛔ SAFETY STOP: Disconnected.")
            self.clean_disconnect() 
            return

        print("   📊 Membuka Data Monitor...")
        x_mon, y_mon = self.get_coord("monitor")
        x_dat, y_dat = self.get_coord("data")
        x_copy, y_copy = self.get_coord("btn_copy")

        if x_mon and x_dat and x_copy:
            pyautogui.click(x_mon, y_mon); time.sleep(1)
            pyautogui.click(x_dat, y_dat)
            time.sleep(8) # Tunggu data stabil
            
            self.handle_unexpected_popup()
            pyperclip.copy("") 
            pyautogui.click(x_copy, y_copy); time.sleep(1)
            
            raw_text = pyperclip.paste()
            if raw_text and len(raw_text) > 20:
                self.save_evidence_and_db(station_name, raw_text)
            else:
                print(f"   ❌ Clipboard kosong.")
        else:
            print("   ❌ Koordinat Data hilang. Cek data_koordinat.json")

        self.clean_disconnect()

    def clean_disconnect(self):
        print("   🔌 Disconnecting...")
        self.force_anchor_window()
        self.handle_unexpected_popup()
        pyautogui.moveTo(10, 10) 
        
        x_sys, y_sys = self.get_coord("System")
        x_disc, y_disc = self.get_coord("btn_disconnect")
        
        if x_sys and y_sys and x_disc and y_disc:
            pyautogui.click(x_sys, y_sys); time.sleep(0.5) 
            pyautogui.click(x_disc, y_disc)
            pyautogui.moveTo(5, 5) 
            
            max_wait = 10
            start_wait = time.time()
            while time.time() - start_wait < max_wait:
                current_title = win32gui.GetWindowText(self.hwnd).upper()
                if "PC REMOTE" in current_title or "NO CONNECTION" in current_title:
                    break
                time.sleep(0.5)
        else:
            print("      ⚠️ Koordinat Disconnect tidak ada!")

    def take_screenshot(self, filepath):
        if self.hwnd:
            rect = win32gui.GetWindowRect(self.hwnd)
            with mss.mss() as sct:
                monitor = {"top": rect[1], "left": rect[0], "width": rect[2]-rect[0], "height": rect[3]-rect[1]}
                mss.tools.to_png(sct.grab(monitor).rgb, sct.grab(monitor).size, output=filepath)

    def save_evidence_and_db(self, name, raw_text):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Simpan screenshot di folder khusus PMDT
        evidence_file = os.path.join(config.PMDT_DIR, f"{name}_{timestamp}.png")
        
        self.take_screenshot(evidence_file)
        parsed = self.parse_text(raw_text)
        self.db.save_session(name, evidence_file, raw_text, parsed)
        
        print("   ✅ Data Tersimpan.")

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

if __name__ == "__main__":
    print("🤖 BATIK ROBOT: PMDT MODULE (FINAL RESTORED)")
    print("⚠️ RUN AS ADMINISTRATOR")
    bot = HybridBatikRobot()
    
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
            print(f"   ⛔ SKIP {name} karena gagal koneksi.")
        time.sleep(1) 
    
    print("\n🎉 SEMUA SELESAI.")