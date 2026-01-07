import pyautogui
import json
import time
import os
import cv2
import numpy as np
import mss
import pytesseract

# --- KONFIGURASI ---
CONFIG_FILE = "data_koordinat.json"

# Lokasi Tesseract (Sesuai info Anda)
# Biasanya file exe ada di dalam folder tersebut
TESSERACT_CMD = r'D:\eman\Tesseract\tesseract.exe'
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

class PMDTRobot:
    def __init__(self):
        self.coords = self.load_coords()
        
    def load_coords(self):
        if not os.path.exists(CONFIG_FILE):
            print("❌ File data_koordinat.json tidak ditemukan!")
            return {}
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)

    def click(self, key_name, double=False, right=False):
        """Klik tombol berdasarkan nama di JSON"""
        if key_name not in self.coords.get("buttons", {}):
            print(f"⚠️ SKIP: Koordinat '{key_name}' belum dimapping.")
            return False

        pos = self.coords["buttons"][key_name]
        x, y = pos["x"], pos["y"]
        
        # Gerakan mouse natural
        pyautogui.moveTo(x, y, duration=0.5)
        
        if right:
            pyautogui.click(button='right')
            print(f"   🖱️ Klik Kanan: {key_name}")
        elif double:
            pyautogui.doubleClick()
            print(f"   🖱️ Double Klik: {key_name}")
        else:
            pyautogui.click()
            print(f"   🖱️ Klik Kiri: {key_name}")
        
        time.sleep(1) 
        return True

    def type_text(self, text):
        """Mengetik teks"""
        print(f"   ⌨️ Mengetik: {text}")
        pyautogui.write(text, interval=0.1)
        time.sleep(0.5)

    def read_value(self, region_name):
        """Membaca angka dari layar (OCR)"""
        if region_name not in self.coords.get("ocr_regions", {}):
            return None

        if not os.path.exists(TESSERACT_CMD):
            print("⚠️ Path Tesseract salah/tidak ditemukan.")
            return "ERR"

        reg = self.coords["ocr_regions"][region_name]
        monitor = {"top": reg["y"], "left": reg["x"], "width": reg["w"], "height": reg["h"]}

        # 1. Capture Area
        with mss.mss() as sct:
            img = np.array(sct.grab(monitor))

        # 2. Image Processing (Penting untuk akurasi)
        # Ubah ke grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Upscale gambar agar angka kecil lebih terbaca (2x lipat)
        gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        
        # Thresholding (Hitam Putih tegas)
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV) 

        # 3. Tesseract Config
        # psm 7 = Single text line
        # whitelist = hanya baca angka, titik, dan minus
        config = "--psm 7 -c tessedit_char_whitelist=0123456789.-" 
        
        try:
            text = pytesseract.image_to_string(thresh, config=config)
            clean_text = text.strip()
            print(f"   👁️ {region_name}: {clean_text}")
            return clean_text
        except Exception as e:
            print(f"   ❌ Error OCR {region_name}: {e}")
            return "ERR"

# --- ALUR UTAMA (Sesuai Mapping JSON Anda) ---

def run_test():
    bot = PMDTRobot()
    print("🤖 BATIK PMDT ROBOT: TESTING LOCALIZER")
    print("--------------------------------------")

    # 1. KONEKSI SYSTEM
    print("\n[1/4] Membuka Menu Network...")
    bot.click("System")
    bot.click("Network")
    # Klik tombol 'Connect' yang ada di tengah popup (Sys_connect di JSON)
    bot.click("Sys_connect") 

    # 2. LOGIN
    print("\n[2/4] Login User...")
    if bot.click("userid"): 
        bot.type_text("q")
    
    if bot.click("password"):
        bot.type_text("qqqq")

    bot.click("ok_login")
    time.sleep(3) # Tunggu loading masuk

    # 3. MASUK LOCALIZER
    print("\n[3/4] Connect Localizer...")
    # Klik Kanan icon Localizer
    bot.click("Loc_klikkanan", right=True) 
    # Pilih menu connect
    bot.click("connect_to") 
    time.sleep(5) # Tunggu koneksi hijau

    # 4. BUKA DATA
    print("\n[4/4] Buka Monitor Data...")
    bot.click("monitor")
    bot.click("data")
    time.sleep(2)

    # 5. BACA OCR (Semua region di JSON)
    print("\n[5/5] Membaca Parameter...")
    print("-" * 30)
    
    # Loop semua region yang ada di JSON
    results = {}
    for key in bot.coords.get("ocr_regions", {}):
        val = bot.read_value(key)
        results[key] = val

    print("-" * 30)
    print("✅ Selesai.")

if __name__ == "__main__":
    pyautogui.FAILSAFE = True 
    run_test()