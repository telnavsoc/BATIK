# FILE: bin/robot_maru.py
# =============================================================================
# BATIK MARU ROBOT V32 (FOCUS FIX & ROBUST TXT SAVE)
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

# --- FUNGSI EKSTRAKSI PDF (TIDAK BERUBAH) ---

def extract_tx_with_pypdf(pdf_path):
    try:
        reader = pypdf.PdfReader(pdf_path)
        if len(reader.pages) > 0:
            return reader.pages[0].extract_text()
        return ""
    except Exception as e:
        return ""

def extract_tx_brute_force_zlib(pdf_path):
    try:
        with open(pdf_path, "rb") as f:
            content = f.read(200000)
        extracted_chunks = []
        zlib_headers = [b'\x78\x9c', b'\x78\x01', b'\x78\xda']
        for header in zlib_headers:
            parts = content.split(header)
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
    if not os.path.exists(pdf_path): return None
    if HAS_PYPDF: raw_text = extract_tx_with_pypdf(pdf_path)
    else: raw_text = extract_tx_brute_force_zlib(pdf_path)

    if not raw_text or len(raw_text) < 10:
        with open(pdf_path, "rb") as f:
            raw_text = f.read(50000).decode('latin-1', errors='ignore')

    clean_text = re.sub(r'[\r\n\t\x00]', ' ', raw_text)
    clean_text = re.sub(r'\s+', ' ', clean_text)
    header_text = clean_text[:400]
    print(f"   [PDF HEADER] ...{header_text}...")

    match = re.search(r"Active\s*TX.*?SLO\s*(TX\d)", header_text, re.IGNORECASE)
    if match:
        tx_str = match.group(1).upper()
        if "1" in tx_str: return 1
        if "2" in tx_str: return 2

    if re.search(r"Active\s*TX\s*TX\s*2", header_text, re.IGNORECASE): return 2
    if re.search(r"Active\s*TX\s*TX\s*1", header_text, re.IGNORECASE): return 1
    return None

class MaruRobot:
    def __init__(self, mode):
        self.mode = mode.upper()
        self.db = DatabaseManager()
        self.hwnd = 0
        
        # TARGET WINDOW TITLE YANG LEBIH SPESIFIK
        if "220" in self.mode:
            self.target_key = "MARU 220" # Updated from "220"
            self.station_name = "DVOR"
            self.temp_txt = "DVOR_temp.txt"
        else:
            self.target_key = "MARU 310" # Updated from "320" to match "MARU 310/320"
            self.station_name = "DME"
            self.temp_txt = "DME_temp.txt"

        self.out_dir = config.get_output_folder("MARU", self.station_name)
        os.makedirs(config.TEMP_DIR, exist_ok=True)

    def find_window(self):
        target = 0
        def cb(h, p):
            nonlocal target
            # Pencarian substring case-insensitive
            if win32gui.IsWindowVisible(h) and self.target_key.upper() in win32gui.GetWindowText(h).upper(): 
                target = h
        win32gui.EnumWindows(cb, None)
        return target

    def focus_and_click_main(self):
        # FUNGSI FOKUS YANG DIPERBAIKI (SAMA SEPERTI PMDT)
        if not self.hwnd: 
            # Coba cari ulang jika hwnd hilang/invalid
            self.hwnd = self.find_window()
            if not self.hwnd: return False

        try:
            if win32gui.IsIconic(self.hwnd): 
                win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
            
            # --- TRIK ALT UNTUK MEMAKSA FOKUS ---
            try:
                win32gui.SetForegroundWindow(self.hwnd)
            except:
                # Jika akses ditolak, tekan ALT lalu coba lagi (Trik ampuh Windows)
                pyautogui.press("alt")
                try:
                    win32gui.SetForegroundWindow(self.hwnd)
                except:
                    pass # Keep going, click might fix it
            
            time.sleep(0.5)
            
            # Update rect setelah restore/focus
            rect = win32gui.GetWindowRect(self.hwnd)
            
            # Klik Pancingan (Header)
            pyautogui.click(rect[0] + 50, rect[1] + 10)
            time.sleep(0.2)
            
            # Klik Tombol 'Main' (Asumsi posisi tombol Main)
            pyautogui.click(rect[0] + 60, rect[1] + 80)
            time.sleep(0.5)
            
            return True
        except Exception as e:
            broadcast_log(self.station_name, f"Focus Error: {e}", "WARN")
            return False

    def save_dialog(self, full_path, is_txt):
        # Dialog Save As Windows Standar
        pyautogui.hotkey("alt", "n") # Fokus ke kolom File Name
        time.sleep(0.5)
        pyperclip.copy(full_path)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.5)
        pyautogui.hotkey("alt", "s") # Tombol Save
        time.sleep(1.0)
        
        if is_txt:
            # Handle Confirm Overwrite jika file sudah ada
            pyautogui.hotkey("alt", "y") 
            time.sleep(0.5)
        else:
            time.sleep(3.0)

    def read_file(self, f):
        try: 
            if not os.path.exists(f): return ""
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
            broadcast_log(self.station_name, f"Window '{self.target_key}' Not Found", "MISSING")
            return

        # 1. Save TXT
        # PENTING: Fokus harus berhasil di sini agar Ctrl+P masuk ke aplikasi
        if not self.focus_and_click_main():
            broadcast_log(self.station_name, "Failed to Focus App", "ERROR")
            # Coba lanjut saja, siapa tahu sudah aktif
        
        broadcast_log(self.station_name, "Saving Log (TXT)", "PROCESS")
        
        # Kirim command Print (Ctrl+P)
        pyautogui.hotkey("ctrl", "p")
        time.sleep(1.5) # Beri waktu dialog muncul
        
        # Navigasi di Dialog Print milik MARU
        if "220" in self.mode:
            # MARU 220: Langsung Alt+S untuk Save TXT (berdasarkan script lama)
            pyautogui.hotkey("alt", "s")
            time.sleep(1.0)
        else:
            # MARU 310/320: Alt+A (All Pages) -> Alt+S (Save)
            pyautogui.hotkey("alt", "a")
            time.sleep(0.5)
            pyautogui.hotkey("alt", "s")
            time.sleep(1.0)

        # Proses Simpan File TXT
        temp_txt_path = os.path.join(config.TEMP_DIR, self.temp_txt)
        # Hapus file lama jika ada agar tidak bingung
        if os.path.exists(temp_txt_path):
            os.remove(temp_txt_path)
            
        self.save_dialog(temp_txt_path, True)
        
        # Validasi apakah file terbentuk
        if not os.path.exists(temp_txt_path):
            broadcast_log(self.station_name, "Gagal Mengambil Data TXT (File Not Created)", "ERROR")
            # Jangan return, coba lanjut ke PDF siapa tahu berhasil
        else:
            broadcast_log(self.station_name, "TXT File Created", "OK")

        raw = self.read_file(temp_txt_path)

        # 2. Print PDF
        broadcast_log(self.station_name, "Printing Evidence (PDF)", "PROCESS")
        pyautogui.press("esc") # Tutup dialog sebelumnya jika nyangkut
        time.sleep(0.5)
        
        self.focus_and_click_main() # Fokus ulang
        pyautogui.hotkey("ctrl", "p")
        time.sleep(1.5)
        
        if "220" in self.mode:
            pyautogui.hotkey("alt", "p") # Printer Select
            time.sleep(0.5)
            pyautogui.press(["f4", "m", "enter"]) # Pilih MS Print to PDF
            time.sleep(0.5)
            pyautogui.press("enter") # Klik Print
            time.sleep(1.5)
        else:
            pyautogui.press(["f4", "m", "enter"]) # Pilih MS Print to PDF
            time.sleep(0.5)
            pyautogui.hotkey("alt", "a")
            time.sleep(0.3)
            pyautogui.hotkey("alt", "o") # OK / Print
            time.sleep(1.5)
        
        file_base = f"{self.station_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        pdf_path = os.path.join(self.out_dir, f"{file_base}.pdf")
        self.save_dialog(pdf_path, False)
        
        broadcast_log(self.station_name, "Finalizing PDF (5s)...", "WAIT")
        time.sleep(5.0) 

        # 3. Process & Upload
        if raw:
            perm_txt = os.path.join(self.out_dir, f"{file_base}.txt")
            try: shutil.copy(temp_txt_path, perm_txt)
            except: pass
            
            self.db.save_session(self.station_name, pdf_path, raw, self.parse(raw))
            content_for_parser = raw
            
            if "DVOR" in self.station_name:
                pdf_tx = extract_tx_from_pdf_binary(pdf_path)
                if pdf_tx:
                    content_for_parser += f"\n\n# [PDF_EVIDENCE] Active TX: TX{pdf_tx}"
                    broadcast_log(self.station_name, f"Header Detect: TX {pdf_tx}", "INFO")
                else:
                    broadcast_log(self.station_name, "Header Detect: Failed", "WARN")

            rows_parsed, active_tx = batik_parser.parse_maru_data(self.station_name, content_for_parser)
            
            print(f"   >>> PREVIEW: TX Active = {active_tx}")
            print(f"   >>> PREVIEW: Data Rows = {len(rows_parsed)} items")
            
            if rows_parsed:
                # ====== METODE BARU: RAW DATA UPLOAD ONLY ======
                broadcast_log(self.station_name, "Uploading to Database...", "UPLOAD")
                
                status_raw, err_raw = sheet_handler.upload_raw_data(
                    self.station_name,
                    rows_parsed,
                    datetime.now(),
                    active_tx
                )
                
                if status_raw == "Success":
                    broadcast_log(self.station_name, "Raw Database Updated", "SUCCESS")
                else:
                    broadcast_log(self.station_name, f"Upload Error: {err_raw}", "ERROR")
            else:
                broadcast_log(self.station_name, "Parsed Data EMPTY", "SKIP")
        else:
            broadcast_log(self.station_name, "RAW DATA EMPTY - Skipping Upload", "WARN")
        
        try:
            if os.path.exists(temp_txt_path): os.remove(temp_txt_path)
            debug_dump = pdf_path.replace(".pdf", "_decoded.txt")
            if os.path.exists(debug_dump): os.remove(debug_dump)
        except: pass
        
        broadcast_log(self.station_name, "Job Completed", "SUCCESS")

if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=" * 60)
    print(" BATIK SYSTEM | MARU ROBOT V32 (RAW MODE)")
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