from pywinauto import Application
import pyautogui
import time
import sys
import os
import win32gui
import win32con
import sqlite3
from datetime import datetime

# --- KONFIGURASI ---
BASE_EVIDENCE = r"D:\eman\BATIK\EVIDENCE_LOGS"
TEMP_FOLDER = r"D:\eman\BATIK\TEMP_DATA"
DB_FILE = "pmdt_database_v2.db"

# Safety
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.8 

# --- INIT FOLDER ---
def init_folders():
    if not os.path.exists(BASE_EVIDENCE): os.makedirs(BASE_EVIDENCE)
    if not os.path.exists(TEMP_FOLDER): os.makedirs(TEMP_FOLDER)
    
    maru_root = os.path.join(BASE_EVIDENCE, "MARU")
    if not os.path.exists(maru_root): os.makedirs(maru_root)
    
    dvor_dir = os.path.join(maru_root, "DVOR")
    dme_dir = os.path.join(maru_root, "DME")
    
    if not os.path.exists(dvor_dir): os.makedirs(dvor_dir)
    if not os.path.exists(dme_dir): os.makedirs(dme_dir)
    
    return dvor_dir, dme_dir

# --- DATABASE ---
class DatabaseManager:
    def __init__(self, db_name):
        self.conn = sqlite3.connect(db_name)
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
        except Exception as e: print(f"   ❌ [DB Error] {e}")

    def close(self): self.conn.close()

# --- ROBOT ---
class MaruRobot:
    def __init__(self):
        self.db = DatabaseManager(DB_FILE)
        self.dvor_folder, self.dme_folder = init_folders()
        self.app = None
        self.main_win = None
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
            print(f"\n⚙️ MEMPROSES: {name} (Engine: {engine_type})")
            hwnd = self.find_window_strict(keyword)
            if hwnd == 0:
                print(f"   ❌ SKIP: Jendela '{keyword}' tidak ditemukan.")
                continue
            
            print(f"   ✅ Target Lock: [{win32gui.GetWindowText(hwnd)}]")
            self.hwnd = hwnd
            try:
                self.app = Application(backend="win32").connect(handle=hwnd)
                self.main_win = self.app.window(handle=hwnd)
            except: pass

            self.force_focus()
            
            if engine_type == "220":
                self._logic_maru_220(name)
            elif engine_type == "320":
                self._logic_maru_320(name)
            
            time.sleep(3) 

    # === LOGIKA 220 (DVOR) ===
    def _logic_maru_220(self, station_name):
        rect = win32gui.GetWindowRect(self.hwnd)
        pyautogui.click(rect[0] + 60, rect[1] + 80)
        time.sleep(0.5)
        pyautogui.hotkey('ctrl', 'p')
        time.sleep(1.5)
        
        # Save TXT
        pyautogui.hotkey('alt', 's') 
        time.sleep(2)
        txt_path = os.path.join(TEMP_FOLDER, f"{station_name}_temp.txt")
        self._handle_save_with_focus(txt_path, is_txt=True)
        raw_data = self._read_txt_file(txt_path)

        # Save PDF
        self.force_focus()
        pyautogui.click(rect[0] + 60, rect[1] + 80)
        pyautogui.hotkey('ctrl', 'p')
        time.sleep(1.5)
        pyautogui.hotkey('alt', 'p')
        time.sleep(2)
        pyautogui.write('microsoft print to pdf', interval=0.05)
        pyautogui.press('enter'); time.sleep(2)
        pdf_path = os.path.join(self.dvor_folder, f"{station_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        self._handle_save_with_focus(pdf_path, is_txt=False)

        if raw_data:
            self.db.save_session(station_name, pdf_path, raw_data, self.parse_maru_text(raw_data))

    # === LOGIKA 320 (DME) - FRESH REOPEN ===
    def _logic_maru_320(self, station_name):
        # 1. Klik Main Window agar fokus
        rect = win32gui.GetWindowRect(self.hwnd)
        pyautogui.click(rect[0] + 60, rect[1] + 80)
        time.sleep(0.5)

        # ---------------------------------------------------------
        # FASE 1: SAVE TXT
        # ---------------------------------------------------------
        print("      ⌨️ [320-TXT] Ctrl + P (Membuka Dialog)...")
        pyautogui.hotkey('ctrl', 'p')
        time.sleep(2.0)

        # Klik All (Alt+A)
        pyautogui.hotkey('alt', 'a')
        
        # Save to file (Alt+S)
        print("      💾 [320-TXT] Save to File (Alt+S)...")
        pyautogui.hotkey('alt', 's') 
        time.sleep(2.0)

        # Proses Simpan Nama File TXT
        txt_path = os.path.join(TEMP_FOLDER, f"{station_name.replace(' ', '_')}_temp.txt")
        self._handle_save_with_focus(txt_path, is_txt=True)
        
        # Baca Data
        raw_data = self._read_txt_file(txt_path)

        # ---------------------------------------------------------
        # FASE 2: CLOSE DIALOG (CANCEL)
        # ---------------------------------------------------------
        print("      ❌ [320] Menutup Dialog Print (CANCEL/ESC)...")
        # Kita tekan ESC untuk menutup sisa dialog print yang masih terbuka
        # agar kita bisa mulai dari awal untuk PDF
        pyautogui.press('esc') 
        time.sleep(1.5) # Tunggu sampai dialog benar-benar hilang

        # Pastikan fokus kembali ke window utama
        self.force_focus()
        pyautogui.click(rect[0] + 60, rect[1] + 80)
        time.sleep(0.5)

        # ---------------------------------------------------------
        # FASE 3: SAVE PDF (FRESH START)
        # ---------------------------------------------------------
        print("      🖨️ [320-PDF] Membuka Ulang Dialog Print...")
        pyautogui.hotkey('ctrl', 'p')
        time.sleep(2.5) # Beri waktu lebih agar window load sempurna

        # GANTI PRINTER (Sesuai Request: F4 -> M -> Enter)
        print("      🔧 [320-PDF] Ganti Printer (F4 -> M -> Enter)...")
        pyautogui.press('f4')
        time.sleep(0.5)
        pyautogui.press('m') # Memilih printer berawalan M (Misal: Microsoft Print to PDF)
        time.sleep(0.5)
        pyautogui.press('enter')
        time.sleep(1.0) # Tunggu dropdown tertutup/terpilih

        # Klik All (Alt+A)
        print("      ✅ [320-PDF] Klik All (Alt+A)...")
        pyautogui.hotkey('alt', 'a')
        time.sleep(0.5)

        # Klik OK (Alt+O) -> Akan memunculkan dialog Save As PDF
        print("      📄 [320-PDF] Klik OK (Alt+O)...")
        pyautogui.hotkey('alt', 'o')
        time.sleep(3.0) # Tunggu dialog Save PDF Windows muncul

        # Proses Simpan Nama File PDF
        pdf_path = os.path.join(self.dme_folder, f"{station_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        self._handle_save_with_focus(pdf_path, is_txt=False)

        # Simpan ke DB
        if raw_data:
            self.db.save_session(station_name, pdf_path, raw_data, self.parse_maru_text(raw_data))

    # --- FUNGSI SAVE (FOCUS LOCK) ---
    def _handle_save_with_focus(self, full_path, is_txt):
        print(f"         📝 Mengunci Fokus 'File Name' (Alt+N)...")
        pyautogui.hotkey('alt', 'n')
        time.sleep(0.5)
        pyautogui.hotkey('ctrl', 'a'); time.sleep(0.1); pyautogui.press('delete')
        time.sleep(0.2)
        print(f"         ⌨️ Mengetik: {full_path}")
        pyautogui.write(full_path, interval=0.01)
        time.sleep(1.0)
        pyautogui.hotkey('alt', 's') 
        time.sleep(1.0)
        if is_txt:
            # Handle overwrite prompt jika ada (Yes)
            pyautogui.hotkey('alt', 'y') 
            time.sleep(1.0)
        else:
            time.sleep(5.0) # Waktu tunggu save PDF lebih lama

    def _read_txt_file(self, path):
        try:
            if not os.path.exists(path):
                print(f"         ⚠️ File belum muncul...")
                time.sleep(2)
            with open(path, 'r') as f: content = f.read()
            print("         ✅ File TXT Terbaca.")
            return content
        except Exception as e:
            print(f"         ❌ Gagal baca TXT: {e}")
            return ""

    def parse_maru_text(self, text):
        data = {}
        for line in text.splitlines():
            if ":" in line:
                parts = line.split(":", 1)
                data[parts[0].strip()] = parts[1].strip()
        return data

if __name__ == "__main__":
    print("🤖 BATIK ROBOT: MARU V38 (CLOSE & REOPEN STRATEGY)")
    bot = MaruRobot()
    targets = [
        ("MARU 220", "MARU 220", "220"),
        ("MARU 320", "310/320", "320")
    ]
    bot.process_queue(targets)
    print("\n🎉 SEMUA SELESAI.")