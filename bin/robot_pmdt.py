# =============================================================================
# BATIK PMDT ROBOT (V14.0 - OPENCV MULTIMONITOR + STABLE STRUCTURE)
# =============================================================================

import sys
import os

# -----------------------------
# STDERR FILTER
# -----------------------------
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

# -----------------------------
# IMPORTS
# -----------------------------
import warnings
warnings.simplefilter("ignore")

import logging
import time
import json
import re
import sqlite3
import csv
import traceback
from datetime import datetime

import pyautogui
import win32gui
import win32con

from pywinauto import Application, Desktop
import mss
import cv2
import numpy as np
import pyperclip

import config

# =============================================================================
# LOGGING
# =============================================================================
logging.basicConfig(
    filename=os.path.join(config.LOG_DIR, 'robot_pmdt.log'),
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

# =============================================================================
# KONFIGURASI
# =============================================================================
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.5

TARGET_MAP = {
    "LOC": ("LOCALIZER", "target_loc.png", "LOCALIZER"),
    "GP": ("GLIDE PATH", "target_gp.png", "GLIDE"),
    "MM": ("MIDDLE MARKER", "target_mm.png", "MIDDLE"),
    "OM": ("OUTER MARKER", "target_om.png", "OUTER"),
}

# posisi anchor PMDT di monitor 2
PMDT_X = 2379
PMDT_Y = -1052
PMDT_W = 1024
PMDT_H = 768

# =============================================================================
# UI UTILITIES
# =============================================================================

def print_header():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=" * 92)
    print(" BATIK SYSTEM | PMDT AUTOMATION | V14.0 (OPENCV MULTIMONITOR)")
    print("=" * 92)
    print(f"{'TIME':<10} | {'STATION':<15} | {'ACTION':<45} | STATUS")
    print("-" * 92)

def log_ui(station, action, status="..."):
    t = datetime.now().strftime("%H:%M:%S")
    print(f"{t:<10} | {station:<15} | {action:<45} | {status}")

# =============================================================================
# DATABASE MANAGER
# =============================================================================

class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect(config.DB_PATH)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                station_name TEXT,
                timestamp DATETIME,
                evidence_path TEXT,
                raw_clipboard TEXT
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS measurements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                parameter_name TEXT,
                value_mon1 TEXT,
                value_mon2 TEXT,
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            )
        """)

        self.conn.commit()

    def save_to_csv_backup(self, station_name, parsed):
        try:
            csv_path = os.path.join(config.BASE_DIR, "output", "monitor_live.csv")
            row = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "station": station_name
            }
            for k, v in parsed.items():
                clean = k.replace(" ", "_").replace("(", "").replace(")", "").replace("-", "")
                row[clean] = v

            exists = os.path.isfile(csv_path)
            with open(csv_path, "a", newline="") as f:
                w = csv.DictWriter(f, fieldnames=row.keys())
                if not exists:
                    w.writeheader()
                w.writerow(row)
        except:
            pass

    def save_session(self, station, evidence, raw, parsed):
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.cursor.execute(
                "INSERT INTO sessions (station_name, timestamp, evidence_path, raw_clipboard) VALUES (?, ?, ?, ?)",
                (station, ts, evidence, raw)
            )
            session_id = self.cursor.lastrowid

            temp = {}
            for full_key, val in parsed.items():
                base = full_key.replace(" (Mon1)", "").replace(" (Mon2)", "")
                if base not in temp:
                    temp[base] = {}
                if "(Mon1)" in full_key:
                    temp[base]["m1"] = val
                else:
                    temp[base]["m2"] = val

            rows = [(session_id, k, v.get("m1", "0"), v.get("m2", "0")) for k, v in temp.items()]

            self.cursor.executemany(
                "INSERT INTO measurements (session_id, parameter_name, value_mon1, value_mon2) VALUES (?, ?, ?, ?)",
                rows
            )
            self.conn.commit()

            self.save_to_csv_backup(station, parsed)
        except:
            log_ui(station, "DB Error", "FAIL")

    def close(self):
        if self.conn:
            self.conn.close()

# =============================================================================
# OPENCV TEMPLATE MATCHING
# =============================================================================

def locate_in_window(hwnd, template_path, threshold=0.55):
    """Template matching langsung dalam window PMDT."""

    if not os.path.exists(template_path):
        return None

    try:
        x1, y1, x2, y2 = win32gui.GetWindowRect(hwnd)
        w = x2 - x1
        h = y2 - y1
    except:
        return None

    # screenshot window
    with mss.mss() as sct:
        grab = sct.grab({"left": x1, "top": y1, "width": w, "height": h})
        img = np.array(grab)[:, :, :3]  # BGR

    tpl = cv2.imread(template_path, cv2.IMREAD_COLOR)
    if tpl is None:
        return None

    res = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)

    if max_val < threshold:
        return None

    ih, iw = tpl.shape[:2]
    px = max_loc[0] + x1 + iw // 2
    py = max_loc[1] + y1 + ih // 2
    return (px, py)
# =============================================================================
# HYBRID BATIK ROBOT (PMDT V14)
# =============================================================================

class HybridBatikRobot:
    def __init__(self):
        self.db = DatabaseManager()
        self.coords = self.load_coords()
        self.hwnd = 0
        self.app = None
        self.main_win = None

    # -------------------------------------------------------------------------
    # LOAD CONFIG
    # -------------------------------------------------------------------------
    def load_coords(self):
        if not os.path.exists(config.COORD_FILE):
            return {}
        with open(config.COORD_FILE, "r") as f:
            return json.load(f)

    def get_coord(self, key):
        if key in self.coords.get("buttons", {}):
            c = self.coords["buttons"][key]
            return c["x"], c["y"]
        return None, None

    # -------------------------------------------------------------------------
    # FIND PMDT WINDOW + RELOCATE TO MONITOR 2
    # -------------------------------------------------------------------------
    def force_anchor_window(self):
        self.hwnd = 0

        def cb(h, _):
            title = win32gui.GetWindowText(h)
            if win32gui.IsWindowVisible(h) and ("PMDT" in title or "Selex" in title):
                if "About" not in title:
                    self.hwnd = h

        win32gui.EnumWindows(cb, None)

        if not self.hwnd:
            return False

        try:
            if win32gui.IsIconic(self.hwnd):
                win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)

            try:
                win32gui.SetForegroundWindow(self.hwnd)
            except:
                pyautogui.press("alt")
                win32gui.SetForegroundWindow(self.hwnd)

            win32gui.MoveWindow(
                self.hwnd,
                PMDT_X,
                PMDT_Y,
                PMDT_W,
                PMDT_H,
                True
            )
            return True

        except:
            return False

    # -------------------------------------------------------------------------
    def handle_unexpected_popup(self):
        try:
            d = Desktop(backend="win32")
            if d.window(title="About").exists():
                try:
                    d.window(title="About").OK.click()
                except:
                    pyautogui.press("enter")
                    pyautogui.press("esc")
                time.sleep(0.3)
        except:
            pass

    # -------------------------------------------------------------------------
    # START & LOGIN
    # -------------------------------------------------------------------------
    def start_and_login(self):
        log_ui("SYSTEM", "Starting PMDT", "INIT")

        try:
            self.app = Application(backend="win32").connect(path=config.PATH_PMDT)
            self.force_anchor_window()
        except:
            try:
                self.app = Application(backend="win32").start(config.PATH_PMDT)
            except:
                try:
                    os.startfile(config.PATH_PMDT)
                    time.sleep(5)
                    self.app = Application(backend="win32").connect(path=config.PATH_PMDT)
                except:
                    log_ui("SYSTEM", "Cannot open PMDT EXE", "FAIL")
                    return

        # tunggu window muncul
        for _ in range(15):
            if self.force_anchor_window():
                break
            time.sleep(1)

        self.handle_unexpected_popup()

        try:
            self.main_win = self.app.window(title_re=".*PMDT.*")
        except:
            self.main_win = None

        # LOGIN
        if self.main_win and "No Connection" in self.main_win.window_text():
            log_ui("SYSTEM", "Login Required", "PROCESS")

            try:
                self.main_win.menu_select("System->Connect->Network")
            except:
                pyautogui.press("alt")
                pyautogui.press("s")
                pyautogui.press("c")
                pyautogui.press("n")

            time.sleep(2)
            desk = Desktop(backend="win32")

            if desk.window(title=" System Directory").exists():
                dlg = desk.window(title=" System Directory")
                try:
                    dlg.Connect.click()
                except:
                    dlg.Button5.click()

            time.sleep(1)

            if desk.window(title="Login").exists():
                dlg = desk.window(title="Login")
                dlg.Edit1.set_text("q")
                dlg.Edit2.set_text("qqqq")
                dlg.OK.click()

            time.sleep(3)
            log_ui("SYSTEM", "Login Successful", "OK")
        else:
            log_ui("SYSTEM", "Application Ready", "OK")

    # -------------------------------------------------------------------------
    # CONNECT TARGET (OpenCV)
    # -------------------------------------------------------------------------
    def find_and_connect(self, station, image_file, expected_keyword):
        self.force_anchor_window()
        self.handle_unexpected_popup()

        # skip jika sudah connect
        if expected_keyword.upper() in win32gui.GetWindowText(self.hwnd).upper():
            log_ui(station, "Already Connected", "CONNECTED")
            return True

        log_ui(station, "Scanning target...", "SEARCH")
        img_path = os.path.join(config.ASSETS_DIR, image_file)

        for _ in range(2):
            pos = locate_in_window(self.hwnd, img_path, threshold=0.55)
            if pos:
                px, py = pos
                pyautogui.moveTo(px, py)
                pyautogui.click()
                time.sleep(0.3)

                pyautogui.rightClick()
                time.sleep(0.4)

                pyautogui.press("down")
                time.sleep(0.15)
                pyautogui.press("enter")

                for __ in range(16):
                    title = win32gui.GetWindowText(self.hwnd).upper()
                    if expected_keyword.upper() in title:
                        log_ui(station, "Connection Established", "SUCCESS")
                        return True

                    self.handle_unexpected_popup()
                    time.sleep(0.4)

            time.sleep(1)

        log_ui(station, "Target Not Found", "FAIL")
        return False

    # -------------------------------------------------------------------------
    # COLLECT DATA
    # -------------------------------------------------------------------------
    def collect_data_and_disconnect(self, station, expected_keyword):
        x_mon, y_mon = self.get_coord("monitor")
        x_dat, y_dat = self.get_coord("data")
        x_copy, y_copy = self.get_coord("btn_copy")

        if not all([x_mon, y_mon, x_dat, y_dat, x_copy, y_copy]):
            log_ui(station, "Missing button coords", "ERROR")
            return

        pyautogui.click(x_mon, y_mon)
        time.sleep(1.5)

        pyautogui.click(x_dat, y_dat)

        t0 = datetime.now().strftime("%H:%M:%S")
        prefix = f"{t0:<10} | {station:<15} | {'Stabilizing 8s':<45} | "
        print(prefix, end="", flush=True)

        for i in range(8, 0, -1):
            print(f"{i}..", end="", flush=True)
            time.sleep(1)
        print("OK")

        pyperclip.copy("")
        pyautogui.click(x_copy, y_copy)
        time.sleep(2)

        raw = pyperclip.paste()

        if raw and len(raw) > 20:
            self.save_evidence_and_db(station, raw)
        else:
            log_ui(station, "Clipboard empty", "WARN")

        self.clean_disconnect()

    # -------------------------------------------------------------------------
    def clean_disconnect(self):
        self.force_anchor_window()
        self.handle_unexpected_popup()

        pyautogui.press("esc")
        time.sleep(0.4)

        x_sys, y_sys = self.get_coord("System")
        x_disc, y_disc = self.get_coord("btn_disconnect")

        if x_sys and y_sys and x_disc and y_disc:
            pyautogui.click(x_sys, y_sys)
            time.sleep(0.25)
            pyautogui.click(x_disc, y_disc)

        time.sleep(2)

    # -------------------------------------------------------------------------
    def take_screenshot(self, filepath):
        if not self.hwnd:
            return

        x1, y1, x2, y2 = win32gui.GetWindowRect(self.hwnd)

        with mss.mss() as sct:
            grab = sct.grab({
                "left": x1,
                "top": y1,
                "width": x2 - x1,
                "height": y2 - y1
            })
            mss.tools.to_png(grab.rgb, grab.size, output=filepath)

    # -------------------------------------------------------------------------
    def save_evidence_and_db(self, station, raw):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder = os.path.join(config.PMDT_DIR, station)
        os.makedirs(folder, exist_ok=True)

        out = os.path.join(folder, f"{station}_{ts}.png")
        self.take_screenshot(out)

        parsed = self.parse_text(raw)
        self.db.save_session(station, out, raw, parsed)

        log_ui(station, "Evidence saved", "OK")

    # -------------------------------------------------------------------------
    def parse_text(self, text):
        data = {}
        section = "General"

        for line in text.splitlines():
            line = line.strip()
            if not line or "Monitor" in line or "Integral" in line:
                continue

            if line in ["Course", "Clearance"]:
                section = line
                continue

            parts = re.split(r"\s{2,}", line)
            if len(parts) >= 3 and "/" not in parts[0]:
                key = f"{section} - {parts[0]}"
                data[f"{key} (Mon1)"] = parts[1]
                data[f"{key} (Mon2)"] = parts[2]

        return data
# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True, help="LOC | GP | MM | OM")
    args = parser.parse_args()

    target = args.target.upper()

    if target not in TARGET_MAP:
        print("[ERROR] Invalid target. Valid targets: LOC, GP, MM, OM")
        sys.exit(1)

    station_name, image_file, expected_keyword = TARGET_MAP[target]

    print_header()

    bot = HybridBatikRobot()

    try:
        # 1. Start PMDT + login jika perlu
        bot.start_and_login()
        time.sleep(1)

        # 2. Connect ke target yang dipilih
        ok = bot.find_and_connect(station_name, image_file, expected_keyword)
        if not ok:
            log_ui(station_name, "Connection Failed", "FAIL")
            bot.db.close()
            sys.exit(2)

        # 3. Collect data + auto-disconnect
        bot.collect_data_and_disconnect(station_name, expected_keyword)

        log_ui(station_name, "TASK COMPLETED", "FINISH")

    except KeyboardInterrupt:
        print("\n[!] User aborted")

    except Exception as e:
        print("\n[!] CRITICAL ERROR:", e)
        logging.error(traceback.format_exc())

    finally:
        bot.db.close()
