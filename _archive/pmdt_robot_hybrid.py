from pywinauto import Application, Desktop
import pyautogui
import time
import sys
import os
import json
import subprocess
import cv2
import numpy as np
import mss
import pytesseract
import win32gui
import win32con
from PIL import Image
from datetime import datetime
import re

# --- KONFIGURASI ---
PMDT_PATH = r"D:\ILS APP\PMDT v8.7.2.0\PMDT.exe"
COORD_FILE = "data_koordinat.json"
TESSERACT_CMD = r'D:\eman\Tesseract\tesseract.exe' 
EVIDENCE_FOLDER = "EVIDENCE_LOGS"

pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

if not os.path.exists(EVIDENCE_FOLDER):
    os.makedirs(EVIDENCE_FOLDER)

class PMDTFullRobot:
    def __init__(self):
        self.coords = self.load_coords()
        self.hwnd = 0 

    def load_coords(self):
        if not os.path.exists(COORD_FILE):
            return {}
        with open(COORD_FILE, 'r') as f:
            return json.load(f)

    def get_coord(self, key):
        if key in self.coords.get("buttons", {}):
            btn = self.coords["buttons"][key]
            return btn["x"], btn["y"]
        return None, None

    # --- 1. WINDOW CONTROL ---
    def bring_window_to_front(self):
        if self.hwnd:
            try:
                if win32gui.IsIconic(self.hwnd):
                    win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(self.hwnd)
                time.sleep(0.2)
                return True
            except: return False
        return False

    def check_state_and_prepare(self):
        print("🚀 [1/6] Cek Status PMDT...")
        self.hwnd = 0
        def callback(h, _):
            if win32gui.IsWindowVisible(h) and "PMDT" in win32gui.GetWindowText(h):
                self.hwnd = h
        win32gui.EnumWindows(callback, None)

        if self.hwnd == 0:
            print("   📂 Membuka Aplikasi Baru...")
            subprocess.Popen(["py", "src/meter_reader.py"])
            time.sleep(5)
            win32gui.EnumWindows(callback, None)
        else:
            print("   ✅ Aplikasi sudah berjalan.")
            self.bring_window_to_front()

        title = win32gui.GetWindowText(self.hwnd)
        if "INDONESIA SOLO" in title or "Localizer" in title:
            print("   ⏭️  SUDAH DI HALAMAN DATA! Skip Login.")
            return "READY_TO_READ"
        return "NEED_LOGIN"

    # --- 2. NAVIGASI ---
    def navigate_login(self):
        self.bring_window_to_front()
        print("📂 [2-4/6] Navigasi Login...")
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
                login_win.Edit1.set_text("q")
                login_win.Edit2.set_text("qqqq")
                try: login_win.OK.click()
                except: login_win.Button1.click()
                print("   ✅ Login Terkirim.")
                time.sleep(5) 
        except: pass

        print("📡 Buka Monitor Data...")
        self.bring_window_to_front()
        x, y = self.get_coord("Loc_klikkanan")
        if x: pyautogui.moveTo(x, y); time.sleep(0.5); pyautogui.rightClick(); time.sleep(1)
        x, y = self.get_coord("connect_to")
        if x: pyautogui.click(x, y); time.sleep(5) 
        x, y = self.get_coord("monitor")
        if x: pyautogui.click(x, y); time.sleep(0.5)
        x, y = self.get_coord("data")
        if x: pyautogui.click(x, y); time.sleep(2)

    # --- 3. CLEANING MINIMALIS ---
    def minimal_clean(self, text, is_status=False):
        # Hapus karakter sampah umum
        text = text.replace("|", "").replace("]", "").replace("[", "").replace("_", "").replace("—", "-")
        
        if is_status:
            # Biarkan huruf
            text = re.sub(r"[^a-zA-Z]", "", text)
        else:
            # Ganti koma jadi titik
            text = text.replace(",", ".")
            # Hapus spasi di tengah angka
            text = text.replace(" ", "")
        
        if not text: return "0"
        return text.strip()

    # --- 4. OCR ENGINE (BACK TO BASICS + TARGETED WHITELIST) ---
    def capture_evidence_and_read(self):
        print("📸 [5/6] MENGAMBIL EVIDENCE & OCR...")
        print("="*40)
        self.bring_window_to_front()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results = {}
        regions = self.coords.get("ocr_regions", {})

        # Evidence Screenshot
        if self.hwnd:
            rect = win32gui.GetWindowRect(self.hwnd)
            x, y, r, b = rect
            w = r - x; h = b - y
            evidence_filename = f"{EVIDENCE_FOLDER}/EVIDENCE_{timestamp}.png"
            with mss.mss() as sct:
                monitor = {"top": y, "left": x, "width": w, "height": h}
                sct_img = sct.grab(monitor)
                mss.tools.to_png(sct_img.rgb, sct_img.size, output=evidence_filename)
                print(f"   ✅ BUKTI TERSIMPAN: {evidence_filename}")
        else:
            evidence_filename = "ERR_NO_WINDOW"

        if not regions: return None, evidence_filename

        with mss.mss() as sct:
            for name, reg in regions.items():
                monitor = {"top": int(reg["y"]), "left": int(reg["x"]), "width": int(reg["w"]), "height": int(reg["h"])}
                img = np.array(sct.grab(monitor))
                
                # --- PROCESSING V10: The "Reference Script" Method ---
                # 1. Resize 5x Cubic
                roi = cv2.resize(img, None, fx=5, fy=5, interpolation=cv2.INTER_CUBIC)
                # 2. Grayscale Murni (NO THRESHOLD DIJAMIN TIDAK HITAM)
                gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                
                cv2.imwrite(f"{EVIDENCE_FOLDER}/DEBUG_{name}_{timestamp}.png", gray)
                pil_img = Image.fromarray(gray)
                
                # --- CONFIG: TARGETED WHITELIST (KUNCI UTAMA) ---
                name_lower = name.lower()
                is_status = False
                
                if "status" in name_lower or ("ident" in name_lower and "mod" not in name_lower):
                     # Kategori Status: Hanya Huruf (a-z, A-Z)
                     whitelist = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
                     is_status = True
                elif "ddm" in name_lower:
                     # Kategori DDM: Angka, Titik, DAN MINUS
                     whitelist = "0123456789.-"
                else:
                     # Kategori Lain (RF, SDM, Mod): Angka dan Titik SAJA. JANGAN CARI MINUS.
                     whitelist = "0123456789."
                
                config = f'--oem 3 --psm 7 -c tessedit_char_whitelist="{whitelist}"'
                
                try:
                    raw_text = pytesseract.image_to_string(pil_img, config=config).strip()
                    
                    # CLEANING MINIMALIS
                    final_text = self.minimal_clean(raw_text, is_status)
                    
                    print(f"   📊 {name:<20} : {final_text}")
                    results[name] = final_text
                except:
                    results[name] = "ERR"
        
        print("="*40)
        return results, evidence_filename

    def save_log(self, data, evidence_path):
        print("💾 [6/6] Menyimpan Log...")
        if not data: return
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"{timestamp} | EVIDENCE={evidence_path} | " + " | ".join([f"{k}={v}" for k, v in data.items()])
        with open("log_meter_reading.txt", "a") as f:
            f.write(log_line + "\n")
        print("✅ Log Tersimpan.")

if __name__ == "__main__":
    print("🤖 BATIK PMDT: FINAL V10 (Back to Basics + Targeted Config)")
    bot = PMDTFullRobot()
    status = bot.check_state_and_prepare()
    if status == "NEED_LOGIN":
        bot.navigate_login()
    data, evidence_path = bot.capture_evidence_and_read()
    bot.save_log(data, evidence_path)
    print("\n🎉 SELESAI.")