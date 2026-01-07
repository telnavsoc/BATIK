import pyautogui
import json
import os
import time
import mss
import cv2
import numpy as np
from pynput import mouse, keyboard

# File untuk menyimpan database koordinat
CONFIG_FILE = "data_koordinat.json"

class CalibrationTool:
    def __init__(self):
        self.data = {}
        self.load_data()
        self.current_pos = (0, 0)
        self.start_pos = None
        self.is_dragging = False

    def load_data(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                self.data = json.load(f)
        else:
            self.data = {"buttons": {}, "ocr_regions": {}}

    def save_data(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.data, f, indent=4)
        print(f"💾 Data tersimpan di {CONFIG_FILE}")

    def get_mouse_pos(self):
        return pyautogui.position()

    def record_point(self, name):
        """Merekam satu titik klik (untuk tombol)"""
        print(f"\n👉 Arahkan mouse ke tombol '{name}'.")
        print("   Tekan 'ENTER' di terminal ini untuk menyimpan posisi.")
        input("   (Tekan Enter jika posisi sudah pas...)")
        
        x, y = self.get_mouse_pos()
        self.data["buttons"][name] = {"x": x, "y": y}
        print(f"   ✅ Tersimpan: {name} di ({x}, {y})")
        self.save_data()

    def record_region(self, name):
        """Merekam area kotak (untuk OCR)"""
        print(f"\n📐 KITA AKAN MEREKAM AREA: '{name}'")
        print("   1. Arahkan mouse ke POJOK KIRI ATAS kotak.")
        input("   -> Tekan ENTER untuk kunci Titik Awal...")
        x1, y1 = self.get_mouse_pos()
        print(f"      Titik Awal: {x1}, {y1}")

        print("   2. Arahkan mouse ke POJOK KANAN BAWAH kotak.")
        input("   -> Tekan ENTER untuk kunci Titik Akhir...")
        x2, y2 = self.get_mouse_pos()
        
        # Hitung x, y, width, height
        x = min(x1, x2)
        y = min(y1, y2)
        w = abs(x2 - x1)
        h = abs(y2 - y1)

        self.data["ocr_regions"][name] = {"x": x, "y": y, "w": w, "h": h}
        
        # Preview gambar agar user yakin
        print("   📸 Mengambil preview gambar...")
        with mss.mss() as sct:
            region = {"top": y, "left": x, "width": w, "height": h}
            img = np.array(sct.grab(region))
            cv2.imshow(f"PREVIEW: {name} (Tekan Spasi utk Tutup)", img)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

        print(f"   ✅ Tersimpan: {name}")
        self.save_data()

    def menu(self):
        while True:
            print("\n--- MENU KALIBRASI PMDT ---")
            print("1. Rekam Tombol (Navigasi)")
            print("2. Rekam Area Data (OCR)")
            print("3. Lihat Data Tersimpan")
            print("4. Keluar")
            pilih = input("Pilih (1-4): ")

            if pilih == '1':
                nama = input("Masukkan nama tombol (misal: btn_connect): ")
                self.record_point(nama)
            elif pilih == '2':
                nama = input("Masukkan nama data (misal: val_rf_level): ")
                self.record_region(nama)
            elif pilih == '3':
                print(json.dumps(self.data, indent=4))
            elif pilih == '4':
                break

if __name__ == "__main__":
    tool = CalibrationTool()
    tool.menu()