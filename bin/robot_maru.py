# FILE: bin/robot_maru.py
import sys
import os
import time
import sqlite3
import logging
from datetime import datetime
import pyautogui
import win32gui
import win32con
from pywinauto import Application

# Import Config Pusat
import config

# --- SETUP LOGGING ---
if not os.path.exists(config.LOG_DIR): os.makedirs(config.LOG_DIR)
logging.basicConfig(
    filename=os.path.join(config.LOG_DIR, 'robot_maru.log'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Safety
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.8

# --- DATABASE MANAGER ---
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
            data_tuples = []
            for key, val in parsed_data.items():
                data_tuples.append((session_id, key, val, "-"))
            self.cursor.executemany('INSERT INTO measurements (session_id, parameter_name, value_mon1, value_mon2) VALUES (?, ?, ?, ?)', data_tuples)
            self.conn.commit()
            print(f"   💾 [DB] Data {station_name} tersimpan.")
            logging.info(f"Data saved: {station_name}")
        except Exception as e:
            print(f"   ❌ [DB Error] {e}")
            logging.error(f"DB Error: {e}")

    def close(self): self.conn.close()

# --- INIT FOLDERS ---
def init_structure():
    dirs = [config.TEMP_DIR, config.DVOR_DIR, config.DME_DIR]
    for d in dirs:
        if not os.path.exists(d): 
            os.makedirs(d)

# --- ROBOT CLASS ---
class MaruRobot:
    def __init__(self):
        init_structure()
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
                win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(self.hwnd)
            except:
                pyautogui.press('alt')
                try: win32gui.SetForegroundWindow(self.hwnd)
                except: pass

    def process_queue(self, targets):
        for name, keyword, engine_type in targets:
            print(f"\n⚙️ MEMPROSES: {name}")
            logging.info(f"Processing: {name}")
            
            hwnd = self.find_window_strict(keyword)
            if hwnd == 0:
                print(f"   ❌ SKIP: Jendela '{keyword}' tidak ditemukan.")
                continue
            
            self.hwnd = hwnd
            try:
                self.app = Application(backend="win32").connect(handle=hwnd)
            except: pass

            self.force_focus()
            
            if engine_type == "220":
                self._logic_maru_220(name)
            elif engine_type == "320":
                self._logic_maru_320(name)
            
            time.sleep(config.DELAY_LONG)

    # === LOGIC 220 (DVOR) - REVISI WINDOW FOCUS ===
    def _logic_maru_220(self, station_name):
        # 1. PASTIKAN WINDOW TERBUKA (TIDAK MINIMIZE)
        print("      🔍 Memastikan Window Aktif...")
        try:
            if win32gui.IsIconic(self.hwnd): # Jika minimize
                win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
                time.sleep(1.0)
            
            win32gui.SetForegroundWindow(self.hwnd)
            time.sleep(0.5)
        except Exception as e:
            print(f"      ⚠️ Gagal fokus window: {e}")
            # Coba pakai metode Alt+Tab kasar jika gagal
            pyautogui.press('alt'); time.sleep(0.1)
            try: win32gui.SetForegroundWindow(self.hwnd)
            except: pass

        # Ambil posisi terbaru setelah restore
        rect = win32gui.GetWindowRect(self.hwnd)
        
        # 2. KLIK TOMBOL 'MAIN'
        # Koordinat +60, +80 diambil dari script lama (Toolbar Kiri Atas)
        print("      🖱️ Klik tombol 'Main'...")
        pyautogui.click(rect[0] + 60, rect[1] + 80)
        time.sleep(1.0) # Wajib jeda agar UI siap

        # 3. SAVE TXT
        print("      ⌨️ [220-TXT] Ctrl + P...")
        pyautogui.hotkey('ctrl', 'p')
        time.sleep(2.0) # Tunggu dialog muncul
        
        print("      💾 [220] Save TXT (Alt+S)...")
        pyautogui.hotkey('alt', 's')
        time.sleep(2.0)
        
        txt_path = os.path.join(config.TEMP_DIR, f"{station_name}_temp.txt")
        self._handle_save_with_focus(txt_path, is_txt=True)
        
        raw_data = self._read_txt_file(txt_path)
        if not raw_data:
            print("      ⚠️ PERINGATAN: File TXT kosong.")

        # 4. SAVE PDF
        # Fokus ulang lagi jaga-jaga dialog save txt memindah fokus
        self.force_focus()
        pyautogui.click(rect[0] + 60, rect[1] + 80) # Klik Main lagi biar aman
        time.sleep(0.5)
        
        print("      🖨️ [220-PDF] Print PDF...")
        pyautogui.hotkey('ctrl', 'p'); time.sleep(1.5)
        
        pyautogui.hotkey('alt', 'p'); time.sleep(2.0)
        pyautogui.write('microsoft print to pdf', interval=0.05)
        pyautogui.press('enter'); time.sleep(2.0)
        
        pdf_path = os.path.join(config.DVOR_DIR, f"{station_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        self._handle_save_with_focus(pdf_path, is_txt=False)

        if raw_data:
            self.db.save_session(station_name, pdf_path, raw_data, self.parse_maru_text(raw_data))

    # === LOGIC 320 (DME) - TETAP (CLOSE & REOPEN) ===
    # Logika ini sudah BENAR dan WORK di test sebelumnya
    def _logic_maru_320(self, station_name):
        rect = win32gui.GetWindowRect(self.hwnd)
        pyautogui.click(rect[0] + 60, rect[1] + 80); time.sleep(0.5)

        # 1. SAVE TXT
        print("      ⌨️ [320-TXT] Ctrl + P...")
        pyautogui.hotkey('ctrl', 'p'); time.sleep(2.0)
        pyautogui.hotkey('alt', 'a') # 320 PERLU Alt+A
        pyautogui.hotkey('alt', 's'); time.sleep(2.0)

        txt_path = os.path.join(config.TEMP_DIR, f"{station_name.replace(' ', '_')}_temp.txt")
        self._handle_save_with_focus(txt_path, is_txt=True)
        raw_data = self._read_txt_file(txt_path)

        # 2. CANCEL DIALOG
        print("      ❌ [320] Reset Dialog (ESC)...")
        pyautogui.press('esc'); time.sleep(1.5)
        self.force_focus()
        pyautogui.click(rect[0] + 60, rect[1] + 80)

        # 3. SAVE PDF
        print("      🖨️ [320-PDF] Reopen Print...")
        pyautogui.hotkey('ctrl', 'p'); time.sleep(2.5)
        
        # Ganti Printer
        pyautogui.press('f4'); time.sleep(0.5)
        pyautogui.press('m'); time.sleep(0.5)
        pyautogui.press('enter'); time.sleep(1.0)

        pyautogui.hotkey('alt', 'a'); time.sleep(0.5)
        pyautogui.hotkey('alt', 'o'); time.sleep(3.0)

        pdf_path = os.path.join(config.DME_DIR, f"{station_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        self._handle_save_with_focus(pdf_path, is_txt=False)

        if raw_data:
            self.db.save_session(station_name, pdf_path, raw_data, self.parse_maru_text(raw_data))

    def _handle_save_with_focus(self, full_path, is_txt):
        print(f"         📝 Saving: {os.path.basename(full_path)}")
        pyautogui.hotkey('alt', 'n'); time.sleep(0.5)
        pyautogui.hotkey('ctrl', 'a'); time.sleep(0.1); pyautogui.press('delete')
        pyautogui.write(full_path, interval=0.01); time.sleep(1.0)
        pyautogui.hotkey('alt', 's'); time.sleep(1.0)
        if is_txt:
            pyautogui.hotkey('alt', 'y'); time.sleep(1.0)
        else:
            time.sleep(5.0)

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

if __name__ == "__main__":
    print("🤖 BATIK ROBOT: MARU MODULE (CORRECTED V39)")
    bot = MaruRobot()
    targets = [
        ("MARU 320", "310/320", "320"),
        ("MARU 220", "MARU 220", "220") 
    ]
    bot.process_queue(targets)
    print("\n🎉 SEMUA SELESAI.")