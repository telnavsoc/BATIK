# FILE: bin/robot_maru.py
# ================================================================
# BATIK SYSTEM - MARU ROBOT V3.5 (MANUAL ADMIN CHECK)
# ================================================================

import sys, os, time, logging, sqlite3, traceback, argparse, ctypes
import win32gui, win32con
import pyautogui, pyperclip
from datetime import datetime
import config

# ================================================================
# 1. ADMIN CHECK (MODE PASIF)
# ================================================================
def is_admin():
    try: return ctypes.windll.shell32.IsUserAnAdmin()
    except: return False

if __name__ == "__main__":
    # JANGAN RESTART OTOMATIS! ITU MEMBUNUH CURTAIN.
    # Cukup beri peringatan keras jika user lupa.
    if not is_admin():
        os.system('cls' if os.name=='nt' else 'clear')
        print("\n" + "!"*60)
        print(" [ERROR] AKSES DITOLAK / ACCESS DENIED")
        print("!"*60)
        print(" Script ini WAJIB dijalankan sebagai ADMINISTRATOR.")
        print(" Robot tidak bisa mengetik/klik di aplikasi MARU tanpa izin Admin.")
        print("-" * 60)
        print(" SOLUSI:")
        print(" 1. Tutup Terminal ini.")
        print(" 2. Klik Kanan VS Code / PowerShell -> 'Run as Administrator'")
        print(" 3. Jalankan perintah lagi.")
        print("!"*60 + "\n")
        time.sleep(5) # Biar user sempat baca
        sys.exit(1)

# ================================================================
# SETUP & LOGGING
# ================================================================
class StderrFilter:
    def __init__(self, orig): self.o = orig
    def write(self, m):
        if "32-bit" in m or "UserWarning" in m: return
        self.o.write(m)
    def flush(self): self.o.flush()
    def __getattr__(self, a): return getattr(self.o, a)

sys.stderr = StderrFilter(sys.stderr)

os.makedirs(config.LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(config.LOG_DIR, "robot_maru.log"),
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.5

def print_header():
    os.system('cls' if os.name=='nt' else 'clear')
    print("="*92)
    print(" BATIK SYSTEM | MARU AUTOMATION | V3.5 (MANUAL ADMIN)")
    print("="*92)
    print(f"{'TIME':<10} | {'STATION':<15} | {'ACTION':<45} | STATUS")
    print("-"*92)

def ui(st, act, stat="..."):
    t = datetime.now().strftime("%H:%M:%S")
    print(f"{t:<10} | {st:<15} | {act:<45} | {stat}")

# ================================================================
# DATABASE
# ================================================================
class DB:
    def __init__(self):
        self.conn = sqlite3.connect(config.DB_PATH)
        self.cur  = self.conn.cursor()
        self.cur.execute("""CREATE TABLE IF NOT EXISTS sessions(id INTEGER PRIMARY KEY AUTOINCREMENT, station_name TEXT, timestamp DATETIME, evidence_path TEXT, raw_clipboard TEXT)""")
        self.cur.execute("""CREATE TABLE IF NOT EXISTS measurements(id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER, parameter_name TEXT, value_mon1 TEXT, value_mon2 TEXT)""")
        self.conn.commit()

    def save(self, station, pdf, raw, parsed):
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.cur.execute("INSERT INTO sessions(station_name,timestamp,evidence_path,raw_clipboard) VALUES(?,?,?,?)", (station, ts, pdf, raw))
            sid = self.cur.lastrowid
            rows = [(sid, k, v, "-") for k,v in parsed.items()]
            self.cur.executemany("INSERT INTO measurements(session_id,parameter_name,value_mon1,value_mon2) VALUES(?,?,?,?)", rows)
            self.conn.commit()
            ui(station, "DB Saved", "DONE")
        except Exception as e:
            ui(station, f"DB Error: {e}", "FAIL")

    def close(self):
        if self.conn: self.conn.close()

# ================================================================
# ROBOT CLASS
# ================================================================
class MaruRobot:
    def __init__(self, mode):
        self.mode = mode.upper()
        self.db   = DB()
        self.hwnd = 0
        
        if "220" in self.mode:
            self.target_key = "220"
            self.out_dir = config.DVOR_DIR
            self.station_name = "MARU 220"
            self.temp_txt = "DVOR_temp.txt"
        else:
            self.target_key = "320"
            self.out_dir = config.DME_DIR
            self.station_name = "MARU 320"
            self.temp_txt = "DME_temp.txt"

        os.makedirs(self.out_dir, exist_ok=True)
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
            pyautogui.click(rect[0] + 50, rect[1] + 10) # Pancingan Title Bar
            time.sleep(0.2)
            pyautogui.click(rect[0] + 60, rect[1] + 80) # Main Button
            time.sleep(0.5)
            return True
        except:
            pyautogui.press("alt")
            return False

    def save_dialog(self, full, is_txt):
        pyautogui.hotkey("alt","n"); time.sleep(0.3)
        pyperclip.copy(full)
        pyautogui.hotkey("ctrl","v"); time.sleep(0.3)
        pyautogui.hotkey("alt","s"); time.sleep(0.8)
        if is_txt: pyautogui.hotkey("alt","y"); time.sleep(0.3)
        else: time.sleep(2.0)

    def read_file(self, f):
        try:
            with open(f,"r") as x: return x.read()
        except: return ""

    def parse(self, raw):
        out = {}
        for line in raw.splitlines():
            if ":" in line:
                k,v = line.split(":",1)
                out[k.strip()] = v.strip()
        return out

    def run_job(self):
        ui(self.station_name, "Finding Window...", "SEARCH")
        self.hwnd = self.find_window()
        if not self.hwnd: 
            ui(self.station_name, "Window Not Found", "MISSING"); return

        # --- STEP 1: SAVE TXT ---
        self.focus_and_click_main()
        ui(self.station_name, "Saving Log (TXT)", "...")

        if "220" in self.mode:
            pyautogui.hotkey("ctrl","p"); time.sleep(1.0)
            pyautogui.hotkey("alt","s"); time.sleep(1.0)
        else:
            pyautogui.hotkey("ctrl","p"); time.sleep(1.0)
            pyautogui.hotkey("alt","a"); pyautogui.hotkey("alt","s"); time.sleep(1.0)

        txt_path = os.path.join(config.TEMP_DIR, self.temp_txt)
        self.save_dialog(txt_path, True)
        raw = self.read_file(txt_path)

        # --- STEP 2: PRINT PDF ---
        ui(self.station_name, "Printing Evidence (PDF)", "...")
        pyautogui.press("esc"); time.sleep(0.5)
        
        self.focus_and_click_main()
        pyautogui.hotkey("ctrl","p"); time.sleep(1.0)
        
        if "220" in self.mode:
            pyautogui.hotkey("alt","p"); time.sleep(0.3)
            pyautogui.press(["f4","m","enter"]); time.sleep(0.3)
            pyautogui.press("enter"); time.sleep(1.5)
        else:
            pyautogui.press(["f4","m","enter"]); time.sleep(0.5)
            pyautogui.hotkey("alt","a"); time.sleep(0.3)
            pyautogui.hotkey("alt","o"); time.sleep(1.5)

        pdf_path = os.path.join(self.out_dir, f"{self.station_name.replace(' ','_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        self.save_dialog(pdf_path, False)

        if raw: self.db.save(self.station_name, pdf_path, raw, self.parse(raw))
        ui(self.station_name, "Job Completed", "SUCCESS")

# ================================================================
# MAIN EXECUTION
# ================================================================
if __name__ == "__main__":
    print_header()
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--DVOR", action="store_true", help="Run only MARU 220")
    parser.add_argument("--DME", action="store_true", help="Run only MARU 320")
    args = parser.parse_args()
    
    run_all = False
    if not args.DVOR and not args.DME:
        run_all = True

    try:
        if args.DVOR or run_all:
            bot1 = MaruRobot("220")
            bot1.run_job()
            if args.DME or run_all: time.sleep(2)

        if args.DME or run_all:
            bot2 = MaruRobot("320")
            bot2.run_job()
            
    except KeyboardInterrupt:
        print("\n[!] Stopped by User")
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        logging.error(traceback.format_exc())