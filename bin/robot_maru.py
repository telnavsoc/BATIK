# FILE: bin/robot_maru.py
# =============================================================================
# BATIK MARU ROBOT V29 (HEADER FOCUS & AUTO CLEANUP)
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
import re 
import zlib
from datetime import datetime

import win32gui
import win32con
import pyautogui
import pyperclip

import config

# Cek library pypdf
try:
    import pypdf
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

try:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    import batik_parser
    import sheet_handler
except ImportError:
    print("Warning: Modul Upload tidak ditemukan.")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "live_monitor.log")      
STATUS_FILE = os.path.join(BASE_DIR, "current_status.txt") 

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.5

def broadcast_log(module, msg, status="INFO"):
    t_str = time.strftime("%H:%M:%S")
    log_line = f"{t_str} | {module:<15} | {msg:<40} | {status}"
    print(log_line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
    except: pass

def is_admin():
    try: return ctypes.windll.shell32.IsUserAnAdmin()
    except: return False

if __name__ == "__main__":
    if not is_admin():
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        sys.exit()

warnings.simplefilter("ignore")
os.makedirs(config.LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(config.LOG_DIR, "robot_maru_debug.log"),
    level=logging.ERROR,
    format="%(asctime)s - %(message)s"
)

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
            rows = [(sid, k, v, "-") for k,v in parsed.items()]
            self.cursor.executemany("INSERT INTO measurements(session_id,parameter_name,value_mon1,value_mon2) VALUES(?,?,?,?)", rows)
            self.conn.commit()
            broadcast_log(station, "Database Saved (WAL)", "DONE")
        except Exception as e:
            broadcast_log(station, f"DB Error: {e}", "FAIL")

    def close(self):
        if self.conn: self.conn.close()

# --- FUNGSI EKSTRAKSI PDF (REVISI V29) ---

def extract_tx_with_pypdf(pdf_path):
    try:
        reader = pypdf.PdfReader(pdf_path)
        # HANYA AMBIL PAGE 1 (Header pasti di sini)
        if len(reader.pages) > 0:
            return reader.pages[0].extract_text()
        return ""
    except Exception as e:
        return ""

def extract_tx_brute_force_zlib(pdf_path):
    """Brute force ZLIB untuk membaca stream tersembunyi"""
    try:
        with open(pdf_path, "rb") as f:
            content = f.read(200000) # Baca 200KB awal saja, header pasti di depan

        extracted_chunks = []
        zlib_headers = [b'\x78\x9c', b'\x78\x01', b'\x78\xda']
        
        for header in zlib_headers:
            parts = content.split(header)
            # Ambil 5 part pertama saja agar tidak terlalu dalam membaca config lain
            for part in parts[1:6]: 
                try:
                    decompressed_data = zlib.decompress(header + part)
                    text = decompressed_data.decode('latin-1', errors='ignore')
                    extracted_chunks.append(text)
                except: pass
        
        return "\n".join(extracted_chunks)
    except Exception as e:
        return ""

def extract_tx_from_pdf_binary(pdf_path):
    """
    Membaca Header PDF DVOR.
    Logic: 'Active TX' ... 'SLO' ... 'TX(n)'
    """
    if not os.path.exists(pdf_path): return None
    
    # 1. Ekstraksi Teks
    if HAS_PYPDF:
        raw_text = extract_tx_with_pypdf(pdf_path)
    else:
        raw_text = extract_tx_brute_force_zlib(pdf_path)

    # Fallback ke raw read jika kosong
    if not raw_text or len(raw_text) < 10:
        with open(pdf_path, "rb") as f:
            raw_text = f.read(50000).decode('latin-1', errors='ignore')

    # 2. BERSIHKAN TEKS
    clean_text = re.sub(r'[\r\n\t\x00]', ' ', raw_text)
    clean_text = re.sub(r'\s+', ' ', clean_text)
    
    # 3. BATASI PENCARIAN (HEADER ONLY)
    # Kita hanya butuh 400 karakter pertama, karena infonya ada di baris pertama
    header_text = clean_text[:400]

    # --- DEBUG SEMENTARA (Tampil di Terminal, tidak disimpan ke file) ---
    print(f"   [PDF HEADER] ...{header_text}...")

    # 4. CARI POLA SPESIFIK (V29)
    # Format: Active TX [Date/Jam] SLO [TARGET]
    # Regex: Cari "Active TX", abaikan karakter tengah, ketemu "SLO", lalu ambil "TX" dan angkanya
    
    match = re.search(r"Active\s*TX.*?SLO\s*(TX\d)", header_text, re.IGNORECASE)
    if match:
        tx_str = match.group(1).upper() # Hasil: "TX1" atau "TX2"
        if "1" in tx_str: return 1
        if "2" in tx_str: return 2

    # Regex Cadangan (Jika formatnya: Active TX TX1)
    if re.search(r"Active\s*TX\s*TX\s*2", header_text, re.IGNORECASE): return 2
    if re.search(r"Active\s*TX\s*TX\s*1", header_text, re.IGNORECASE): return 1

    return None

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
            pyautogui.click(rect[0] + 50, rect[1] + 10)
            time.sleep(0.2)
            pyautogui.click(rect[0] + 60, rect[1] + 80)
            time.sleep(0.5)
            return True
        except: return False

    def save_dialog(self, full_path, is_txt):
        pyautogui.hotkey("alt", "n")
        time.sleep(0.3)
        pyperclip.copy(full_path)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.3)
        pyautogui.hotkey("alt", "s")
        time.sleep(0.8)
        if is_txt:
            pyautogui.hotkey("alt", "y")
            time.sleep(0.3)
        else:
            time.sleep(3.0)

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

        # 1. Save TXT
        self.focus_and_click_main()
        broadcast_log(self.station_name, "Saving Log (TXT)", "PROCESS")
        
        if "220" in self.mode:
            pyautogui.hotkey("ctrl", "p"); time.sleep(1.0)
            pyautogui.hotkey("alt", "s"); time.sleep(1.0)
        else:
            pyautogui.hotkey("ctrl", "p"); time.sleep(1.0)
            pyautogui.hotkey("alt", "a"); pyautogui.hotkey("alt", "s"); time.sleep(1.0)

        temp_txt_path = os.path.join(config.TEMP_DIR, self.temp_txt)
        self.save_dialog(temp_txt_path, True)
        raw = self.read_file(temp_txt_path)

        # 2. Print PDF
        broadcast_log(self.station_name, "Printing Evidence (PDF)", "PROCESS")
        pyautogui.press("esc"); time.sleep(0.5)
        self.focus_and_click_main()
        pyautogui.hotkey("ctrl", "p"); time.sleep(1.0)
        
        if "220" in self.mode:
            pyautogui.hotkey("alt", "p"); time.sleep(0.3)
            pyautogui.press(["f4", "m", "enter"]); time.sleep(0.3)
            pyautogui.press("enter"); time.sleep(1.5)
        else:
            pyautogui.press(["f4", "m", "enter"]); time.sleep(0.5)
            pyautogui.hotkey("alt", "a"); time.sleep(0.3)
            pyautogui.hotkey("alt", "o"); time.sleep(1.5)
        
        file_base = f"{self.station_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        pdf_path = os.path.join(self.out_dir, f"{file_base}.pdf")
        self.save_dialog(pdf_path, False)
        
        broadcast_log(self.station_name, "Finalizing PDF (5s)...", "WAIT")
        time.sleep(5.0) 

        # 3. Process & Upload
        if raw:
            # Hapus file temp txt setelah dicopy (Clean up)
            perm_txt = os.path.join(self.out_dir, f"{file_base}.txt")
            try: shutil.copy(temp_txt_path, perm_txt)
            except: pass
            
            self.db.save_session(self.station_name, pdf_path, raw, self.parse(raw))

            # --- PREPARE DATA ---
            content_for_parser = raw
            
            # [LOGIC DVOR: HEADER CHECK ONLY]
            if "DVOR" in self.station_name:
                pdf_tx = extract_tx_from_pdf_binary(pdf_path)
                
                if pdf_tx:
                    content_for_parser += f"\n\n# [PDF_EVIDENCE] Active TX: TX{pdf_tx}"
                    broadcast_log(self.station_name, f"Header Detect: TX {pdf_tx}", "INFO")
                else:
                    broadcast_log(self.station_name, "Header Detect: Failed", "WARN")

            # --- PARSING ---
            rows_parsed, active_tx = batik_parser.parse_maru_data(self.station_name, content_for_parser)
            
            print(f"   >>> PREVIEW: TX Active = {active_tx}")
            print(f"   >>> PREVIEW: Data Rows = {len(rows_parsed)} items")
            
            if rows_parsed:
                broadcast_log(self.station_name, "Uploading to Sheet...", "UPLOAD")
                sid, gid, err = sheet_handler.upload_data_to_sheet(
                    self.station_name, 
                    rows_parsed, 
                    datetime.now(), 
                    active_tx
                )
                if err: broadcast_log(self.station_name, f"Upload Failed: {err}", "ERROR")
                else: broadcast_log(self.station_name, f"Uploaded (Tx: {active_tx})", "SUCCESS")
            else:
                broadcast_log(self.station_name, "Parsed Data EMPTY", "SKIP")
        
        # Cleanup Temp Files (Agar folder output tidak penuh sampah)
        try:
            if os.path.exists(temp_txt_path): os.remove(temp_txt_path)
            # Hapus file debug dump jika ada
            debug_dump = pdf_path.replace(".pdf", "_decoded.txt")
            if os.path.exists(debug_dump): os.remove(debug_dump)
        except: pass
        
        broadcast_log(self.station_name, "Job Completed", "SUCCESS")

# --- ENTRY POINT ---
if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=" * 60)
    print(" BATIK SYSTEM | MARU ROBOT V29 (HEADER FIX)")
    print("=" * 60)
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--DVOR", action="store_true")
    parser.add_argument("--DME", action="store_true")
    args = parser.parse_args()
    
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