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
import sqlite3
from datetime import datetime

# --- KONFIGURASI ---
PMDT_PATH = r"D:\ILS APP\PMDT v8.7.2.0\PMDT.exe"
COORD_FILE = "data_koordinat.json"
EVIDENCE_FOLDER = "EVIDENCE_LOGS"
DB_FILE = "pmdt_database.db"

# Anchor Jendela
ANCHOR_X = 0; ANCHOR_Y = 0; ANCHOR_W = 1024; ANCHOR_H = 768

if not os.path.exists(EVIDENCE_FOLDER): os.makedirs(EVIDENCE_FOLDER)

# --- DAFTAR ALAT YANG AKAN DI-SCAN ---
# Format: [Nama Alat, Key di JSON untuk Pohon Navigasi]
STATION_TARGETS = [
    ("LOCALIZER", "tree_loc"),
    ("GLIDE PATH", "tree_gp"),
    ("MIDDLE MARKER", "tree_mm"),
    ("OUTER MARKER", "tree_om")
]

# --- CLASS MANAJEMEN DATABASE ---
class DatabaseManager:
    def __init__(self, db_name):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        # Tambah kolom station_name agar kita tahu ini data punya siapa
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                station_name TEXT,
                timestamp DATETIME,
                evidence_path TEXT,
                raw_clipboard TEXT
            )
        ''')
        
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

    def save_session(self, station_name, evidence_path, raw_text, parsed_data):
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.cursor.execute('''
                INSERT INTO sessions (station_name, timestamp, evidence_path, raw_clipboard)
                VALUES (?, ?, ?, ?)
            ''', (station_name, timestamp, evidence_path, raw_text))
            
            session_id = self.cursor.lastrowid
            
            temp_storage = {} 
            for full_key, value in parsed_data.items():
                if "(Mon1)" in full_key:
                    param_name = full_key.replace(" (Mon1)", "")
                    if param_name not in temp_storage: temp_storage[param_name] = {}
                    temp_storage[param_name]['mon1'] = value
                elif "(Mon2)" in full_key:
                    param_name = full_key.replace(" (Mon2)", "")
                    if param_name not in temp_storage: temp_storage[param_name] = {}
                    temp_storage[param_name]['mon2'] = value

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
            print(f"   💾 [DB] Data {station_name} tersimpan (ID: {session_id})")
        except Exception as e:
            print(f"   ❌ [DB Error] {e}")

    def close(self):
        self.conn.close()

# --- CLASS ROBOT UTAMA ---
class PMDTClipboardRobot:
    def __init__(self):
        self.coords = self.load_coords()
        self.db = DatabaseManager(DB_FILE)
        self.hwnd = 0 

    def load_coords(self):
        if not os.path.exists(COORD_FILE): return {}
        with open(COORD_FILE, 'r') as f: return json.load(f)

    def get_coord(self, key):
        if key in self.coords.get("buttons", {}):
            btn = self.coords["buttons"][key]
            return btn["x"], btn["y"]
        return None, None

    def force_anchor_window(self):
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
            subprocess.Popen([PMDT_PATH]) # Pastikan path benar atau gunakan argumen list
            time.sleep(8) 
            self.force_anchor_window()

        # Cek apakah butuh Login
        desktop = Desktop(backend="win32")
        if desktop.window(title="Login").exists():
             return "NEED_LOGIN"
        
        return "READY"

    # --- FUNGSI 1: LOGIN SAJA (Tanpa Navigasi) ---
    def do_login_only(self):
        print("🔐 [LOGIN] Melakukan Login...")
        self.force_anchor_window()
        
        # 1. Buka Menu Connect (Manual via Click Coordinate untuk memancing window Login)
        for menu in ["System", "Connect", "Network"]:
            x, y = self.get_coord(menu)
            if x: pyautogui.click(x, y); time.sleep(0.5)

        # 2. Handle Window Login (Pakai Pywinauto yg sudah terbukti ampuh)
        try:
            desktop = Desktop(backend="win32")
            # Coba cari window System Directory dulu
            if desktop.window(title=" System Directory").exists():
                 w = desktop.window(title=" System Directory")
                 try: w.Connect.click()
                 except: w.Button5.click()
                 time.sleep(1)

            # Isi Password
            if desktop.window(title="Login").exists():
                login_win = desktop.window(title="Login")
                login_win.Edit1.set_text("q")
                login_win.Edit2.set_text("qqqq")
                try: login_win.OK.click()
                except: login_win.Button1.click()
                print("   ✅ Password Terkirim.")
                time.sleep(3)
        except Exception as e:
            print(f"   ⚠️ Warning Login: {e}")

    # --- FUNGSI 2: DISCONNECT ---
    def do_disconnect(self):
        print("🔌 [NAV] Disconnecting...")
        self.force_anchor_window()
        
        # Sesuai instruksi: Klik "System" -> Klik "btn_disconnect"
        x_sys, y_sys = self.get_coord("System")
        if x_sys: pyautogui.click(x_sys, y_sys); time.sleep(0.5)
        
        x_disc, y_disc = self.get_coord("btn_disconnect")
        if x_disc: pyautogui.click(x_disc, y_disc); time.sleep(2)
        else: print("   ⚠️ Tombol disconnect tidak ketemu!")

    # --- FUNGSI 3: NAVIGASI KE ALAT & BACA DATA ---
    def process_station(self, station_name, tree_key):
        print(f"\n🚀 [PROSES] Membaca: {station_name}")
        self.force_anchor_window()

        # 1. DISCONNECT DULU
        self.do_disconnect()

        # 2. KLIK KANAN PADA TREE
        print(f"   👉 Klik Kanan: {tree_key}")
        x_tree, y_tree = self.get_coord(tree_key)
        if not x_tree:
            print(f"   ❌ Koordinat {tree_key} SALAH/TIDAK ADA!"); return
        
        pyautogui.moveTo(x_tree, y_tree)
        time.sleep(0.5)
        pyautogui.rightClick()
        time.sleep(1)

        # 3. KLIK CONNECT
        x_conn, y_conn = self.get_coord("connect_to")
        if x_conn: 
            pyautogui.click(x_conn, y_conn)
            print("   ⏳ Menunggu koneksi (5 detik)...")
            time.sleep(5)
        else: print("   ❌ Koordinat 'connect_to' hilang!"); return

        # 4. KLIK MONITOR -> DATA
        print("   📊 Membuka Monitor Data...")
        x_mon, y_mon = self.get_coord("monitor")
        pyautogui.click(x_mon, y_mon); time.sleep(0.5)
        
        x_dat, y_dat = self.get_coord("data")
        pyautogui.click(x_dat, y_dat); time.sleep(2)

        # 5. COPY & SAVE (Pakai fungsi yang sudah ada)
        self.get_data_process_and_save(station_name)

    def get_data_process_and_save(self, station_name):
        print("   📸 Mengambil Data & Screenshot...")
        self.force_anchor_window()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Evidence
        evidence_filename = f"{EVIDENCE_FOLDER}/{station_name}_{timestamp}.png"
        if self.hwnd:
            rect = win32gui.GetWindowRect(self.hwnd)
            x, y, r, b = rect; w = r - x; h = b - y
            with mss.mss() as sct:
                monitor = {"top": y, "left": x, "width": w, "height": h}
                mss.tools.to_png(sct.grab(monitor).rgb, sct.grab(monitor).size, output=evidence_filename)
        
        # Copy Clipboard
        x_copy, y_copy = self.get_coord("btn_copy")
        pyperclip.copy("")
        pyautogui.click(x_copy, y_copy)
        time.sleep(0.5)
        raw_text = pyperclip.paste()
        
        if not raw_text:
            print("   ❌ Clipboard kosong!")
            return

        # Parsing & Saving
        parsed_data = self.parse_dynamic_text(raw_text)
        
        # Simpan ke Text File
        timestamp_human = datetime.now().strftime("%d-%b-%Y %H:%M:%S")
        log_entry = (
            f"\n{'='*60}\n  BATIK REPORT: {station_name}\n  Waktu    : {timestamp_human}\n"
            f"  Evidence : {evidence_filename}\n{'='*60}\n{raw_text}\n{'-'*60}\n"
            f"  STATUS: VALIDATED\n{'='*60}\n\n"
        )
        with open("Daily_Logbook.txt", "a", encoding="utf-8") as f: f.write(log_entry)
        
        # Simpan ke Database
        self.db.save_session(station_name, evidence_filename, raw_text, parsed_data)
        print("   ✅ Data Selesai Disimpan.")

    def parse_dynamic_text(self, text):
        # (Fungsi parsing sama persis dengan yang lama)
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

# --- MAIN PROGRAM (MODIFIKASI UTAMA DISINI) ---
if __name__ == "__main__":
    print("🤖 BATIK PMDT: FULL AUTOMATION (LOC -> GP -> MM -> OM)")
    bot = PMDTClipboardRobot()
    
    # 1. Persiapan Awal
    status = bot.check_state_and_prepare()
    
    # 2. Login (Hanya jika dibutuhkan)
    if status == "NEED_LOGIN":
        bot.do_login_only()
    
    # 3. LOOPING UNTUK SEMUA ALAT
    # Ini akan mengerjakan LOC, lalu GP, lalu MM, lalu OM
    for alat in STATION_TARGETS:
        nama_alat = alat[0]  # Contoh: "LOCALIZER"
        key_json = alat[1]   # Contoh: "tree_loc"
        
        bot.process_station(nama_alat, key_json)
        
        print("   ⏸️ Istirahat 3 detik sebelum lanjut...")
        time.sleep(3)

    print("\n🎉 SEMUA ALAT SELESAI. KERJA BAGUS!")