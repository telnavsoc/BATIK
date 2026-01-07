from pywinauto import Application, Desktop
import pyautogui
import time
import sys
import os
import json
import subprocess
import win32gui
import win32con
import mss
import mss.tools
import pyperclip
import re
import sqlite3 # Database Library
from datetime import datetime

# --- KONFIGURASI ---
PMDT_PATH = r"D:\ILS APP\PMDT v8.7.2.0\PMDT.exe"
COORD_FILE = "data_koordinat.json"
EVIDENCE_FOLDER = "EVIDENCE_LOGS"
DB_FILE = "pmdt_database.db" # File Database Kita

# Anchor Jendela
ANCHOR_X = 0; ANCHOR_Y = 0; ANCHOR_W = 1024; ANCHOR_H = 768

if not os.path.exists(EVIDENCE_FOLDER): os.makedirs(EVIDENCE_FOLDER)

# --- CLASS MANAJEMEN DATABASE ---
class DatabaseManager:
    def __init__(self, db_name):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        # 1. Tabel Sessions (Menyimpan Waktu & Bukti)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                evidence_path TEXT,
                raw_clipboard TEXT
            )
        ''')
        
        # 2. Tabel Measurements (Menyimpan Nilai Parameter)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS measurements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                parameter_name TEXT,
                value_mon1 TEXT,
                value_mon2 TEXT,
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            )
        ''')
        self.conn.commit()

    def save_session(self, evidence_path, raw_text, parsed_data):
        try:
            # A. Simpan Sesi
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.cursor.execute('''
                INSERT INTO sessions (timestamp, evidence_path, raw_clipboard)
                VALUES (?, ?, ?)
            ''', (timestamp, evidence_path, raw_text))
            
            session_id = self.cursor.lastrowid # Ambil ID sesi yang baru dibuat
            
            # B. Simpan Detail Data
            # Format parsed_data dari script sebelumnya: {"Key (Mon1)": "Val", "Key (Mon2)": "Val"}
            # Kita perlu merapikan agar tersimpan per parameter
            
            # Grouping data sementara
            temp_storage = {} 
            for full_key, value in parsed_data.items():
                # full_key contoh: "Course - RF Level (Mon1)"
                # Kita pecah stringnya
                if "(Mon1)" in full_key:
                    param_name = full_key.replace(" (Mon1)", "")
                    if param_name not in temp_storage: temp_storage[param_name] = {}
                    temp_storage[param_name]['mon1'] = value
                elif "(Mon2)" in full_key:
                    param_name = full_key.replace(" (Mon2)", "")
                    if param_name not in temp_storage: temp_storage[param_name] = {}
                    temp_storage[param_name]['mon2'] = value

            # Insert ke Database
            data_tuples = []
            for param, vals in temp_storage.items():
                val1 = vals.get('mon1', '0')
                val2 = vals.get('mon2', '0')
                data_tuples.append((session_id, param, val1, val2))

            self.cursor.executemany('''
                INSERT INTO measurements (session_id, parameter_name, value_mon1, value_mon2)
                VALUES (?, ?, ?, ?)
            ''', data_tuples)
            
            self.conn.commit()
            print(f"   💾 [DB] Data tersimpan di Database (Session ID: {session_id})")
            
        except Exception as e:
            print(f"   ❌ [DB Error] Gagal menyimpan ke database: {e}")

    def close(self):
        self.conn.close()

# --- CLASS ROBOT UTAMA ---
class PMDTClipboardRobot:
    def __init__(self):
        self.coords = self.load_coords()
        self.db = DatabaseManager(DB_FILE) # Inisialisasi DB
        self.hwnd = 0 

    def load_coords(self):
        if not os.path.exists(COORD_FILE): return {}
        with open(COORD_FILE, 'r') as f: return json.load(f)

    def get_coord(self, key):
        if key in self.coords.get("buttons", {}):
            btn = self.coords["buttons"][key]
            return btn["x"], btn["y"]
        return None, None

    # --- WINDOW CONTROL ---
    def force_anchor_window(self):
        print("⚓ [1/5] Mengunci Posisi Jendela...")
        self.hwnd = 0
        def callback(h, _):
            if win32gui.IsWindowVisible(h) and "PMDT" in win32gui.GetWindowText(h): self.hwnd = h
        win32gui.EnumWindows(callback, None)

        if self.hwnd:
            try:
                if win32gui.IsIconic(self.hwnd): win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
                try: win32gui.SetForegroundWindow(self.hwnd)
                except: pyautogui.press('alt'); win32gui.SetForegroundWindow(self.hwnd)
                win32gui.MoveWindow(self.hwnd, ANCHOR_X, ANCHOR_Y, ANCHOR_W, ANCHOR_H, True)
                time.sleep(0.5)
                return True
            except: return False
        return False

    def check_state_and_prepare(self):
        self.force_anchor_window()
        if not self.hwnd:
            print("   📂 Membuka Aplikasi Baru...")
            subprocess.Popen(["py", "src/meter_reader.py"])
            time.sleep(8) 
            self.force_anchor_window()

        title = win32gui.GetWindowText(self.hwnd)
        if "INDONESIA SOLO" in title or "Localizer" in title:
            print("   ⏭️  SUDAH SIAP! Lanjut ambil data.")
            return "READY_TO_READ"
        return "NEED_LOGIN"

    # --- NAVIGASI ---
    def navigate_login(self):
        self.force_anchor_window()
        print("📂 [2/5] Navigasi Login...")
        for menu in ["System", "Connect", "Network"]:
            x, y = self.get_coord(menu)
            if x: pyautogui.click(x, y); time.sleep(0.5)

        try:
            desktop = Desktop(backend="win32")
            for _ in range(5):
                if desktop.window(title=" System Directory").exists():
                    w = desktop.window(title=" System Directory")
                    try: w.Connect.click()
                    except: w.Button5.click()
                    break
                time.sleep(1)
            
            login_win = None
            for _ in range(10):
                if desktop.window(title="Login").exists():
                    login_win = desktop.window(title="Login")
                    break
                time.sleep(1)
            
            if login_win:
                login_win.Edit1.set_text("q"); login_win.Edit2.set_text("qqqq")
                try: login_win.OK.click()
                except: login_win.Button1.click()
                print("   ✅ Login Terkirim.")
                time.sleep(5) 
        except: pass

        print("📡 Buka Monitor Data...")
        self.force_anchor_window()
        x, y = self.get_coord("Loc_klikkanan")
        if x: pyautogui.moveTo(x, y); time.sleep(0.5); pyautogui.rightClick(); time.sleep(1)
        x, y = self.get_coord("connect_to")
        if x: pyautogui.click(x, y); time.sleep(5) 
        x, y = self.get_coord("monitor"); pyautogui.click(x, y); time.sleep(0.5)
        x, y = self.get_coord("data"); pyautogui.click(x, y); time.sleep(2)

    # --- AMBIL DATA ---
    def get_data_process(self):
        print("📸 [3/5] Copy Data Clipboard...")
        self.force_anchor_window()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Evidence
        if self.hwnd:
            rect = win32gui.GetWindowRect(self.hwnd)
            x, y, r, b = rect; w = r - x; h = b - y
            evidence_filename = f"{EVIDENCE_FOLDER}/EVIDENCE_{timestamp}.png"
            with mss.mss() as sct:
                monitor = {"top": y, "left": x, "width": w, "height": h}
                mss.tools.to_png(sct.grab(monitor).rgb, sct.grab(monitor).size, output=evidence_filename)
            print(f"   ✅ Visual Evidence: {evidence_filename}")
        else: evidence_filename = "ERR_NO_WINDOW"

        # Copy
        x_copy, y_copy = self.get_coord("btn_copy")
        if not x_copy:
            print("❌ ERROR: Mapping btn_copy hilang!"); return None, {}, evidence_filename
        
        pyperclip.copy(""); pyautogui.click(x_copy, y_copy); time.sleep(0.5) 
        raw_text = pyperclip.paste()
        
        if not raw_text: print("❌ Clipboard kosong!"); return None, {}, evidence_filename
            
        print("   ✅ Teks berhasil diambil.")
        return raw_text, self.parse_dynamic_text(raw_text), evidence_filename

    # --- PARSER ---
    def parse_dynamic_text(self, text):
        print("📊 [4/5] Parsing...")
        data = {}
        current_section = "General"
        for line in text.splitlines():
            line = line.strip()
            if not line: continue
            if line == "Course": current_section = "Course"; continue
            elif line == "Clearance": current_section = "Clearance"; continue
            if "Monitor 1" in line or "Integral" in line or "All Monitor Data" in line: continue

            parts = re.split(r'\s{2,}', line)
            if len(parts) >= 3:
                label = parts[0].strip(); val1 = parts[1].strip(); val2 = parts[2].strip()
                if "/" in label and ":" in label: continue 
                
                key_base = f"{current_section} - {label}"
                data[f"{key_base} (Mon1)"] = val1
                data[f"{key_base} (Mon2)"] = val2
        return data

    # --- PENYIMPANAN GANDA (TEXT + DB) ---
    def save_all(self, raw_text, parsed_data, evidence_path):
        print("💾 [5/5] Menyimpan Data...")
        
        # 1. Simpan ke Text File (Human Readable)
        if raw_text:
            timestamp_human = datetime.now().strftime("%d-%b-%Y %H:%M:%S")
            log_entry = (
                f"\n{'='*60}\n  BATIK METER READING REPORT\n  Waktu    : {timestamp_human}\n"
                f"  Evidence : {evidence_path}\n{'='*60}\n{raw_text}\n{'-'*60}\n"
                f"  STATUS: VALIDATED BY SYSTEM\n{'='*60}\n\n"
            )
            with open("Daily_Logbook.txt", "a", encoding="utf-8") as f: f.write(log_entry)
            print("   ✅ [TXT] Laporan Human-Readable tersimpan.")

        # 2. Simpan ke Database (Machine Readable)
        if parsed_data:
            self.db.save_session(evidence_path, raw_text, parsed_data)

if __name__ == "__main__":
    print("🤖 BATIK PMDT: DATABASE EDITION")
    bot = PMDTClipboardRobot()
    
    status = bot.check_state_and_prepare()
    if status == "NEED_LOGIN": bot.navigate_login()
    
    raw, parsed, evidence = bot.get_data_process()
    if raw:
        bot.save_all(raw, parsed, evidence)
    
    print("\n🎉 SELESAI.")