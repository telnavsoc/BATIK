import pyautogui
import json
import os
import win32gui
import win32con
import time

# --- KONFIGURASI ---
FILE_JSON = "data_koordinat.json"
PMDT_WINDOW_TITLE = "PMDT" # Pastikan sebagian judul window benar
ANCHOR_X = 0; ANCHOR_Y = 0; ANCHOR_W = 1024; ANCHOR_H = 768

# Daftar tombol yang HARUS dimapping ulang
BUTTONS_TO_MAP = [
    "System", "btn_disconnect", # Tombol Menu Atas
    "tree_loc", "tree_gp", "tree_mm", "tree_om", # Pohon Navigasi (Klik Kanan Disini)
    "connect_to", # Tombol "Connect" di menu klik kanan
    "monitor", "data", # Tab Navigasi Data
    "btn_copy" # Tombol Copy Clipboard
]

def force_anchor_window():
    hwnd = 0
    def callback(h, _):
        if win32gui.IsWindowVisible(h) and PMDT_WINDOW_TITLE in win32gui.GetWindowText(h): 
            nonlocal hwnd
            hwnd = h
    win32gui.EnumWindows(callback, None)

    if hwnd:
        print(f"✅ Jendela ditemukan: {hex(hwnd)}")
        try:
            if win32gui.IsIconic(hwnd): win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            try: win32gui.SetForegroundWindow(hwnd)
            except: pyautogui.press('alt'); win32gui.SetForegroundWindow(hwnd)
            # KITA PAKSA POSISI SAMA PERSIS DENGAN SCRIPT ROBOT
            win32gui.MoveWindow(hwnd, ANCHOR_X, ANCHOR_Y, ANCHOR_W, ANCHOR_H, True)
            time.sleep(1)
            return True
        except Exception as e:
            print(f"❌ Gagal memindahkan jendela: {e}")
            return False
    else:
        print("❌ Jendela PMDT tidak ditemukan! Buka aplikasi dulu.")
        return False

def main():
    print("="*50)
    print("   BATIK COORDINATE MAPPER (RE-MAPPING TOOL)")
    print("="*50)
    print("Script ini akan memandu Anda mengambil koordinat baru.")
    print("Pastikan aplikasi PMDT sudah terbuka.\n")

    if not force_anchor_window():
        return

    new_coords = {"buttons": {}}
    
    # Load data lama jika ada (untuk backup)
    if os.path.exists(FILE_JSON):
        with open(FILE_JSON, 'r') as f:
            try: old_data = json.load(f)
            except: old_data = {}
            # Kita simpan region OCR lama biar gak hilang
            if "ocr_regions" in old_data:
                new_coords["ocr_regions"] = old_data["ocr_regions"]

    print("\n🚀 MULAI MAPPING...")
    print("Instruksi: Arahkan mouse ke tengah tombol yang diminta, JANGAN KLIK, tekan [ENTER] di keyboard.")
    
    for btn_name in BUTTONS_TO_MAP:
        input(f"\n👉 Arahkan mouse ke tombol: [{btn_name.upper()}] ... lalu tekan ENTER")
        
        # Ambil posisi mouse saat ini
        x, y = pyautogui.position()
        
        print(f"   ✅ Tersimpan: {btn_name} -> X:{x}, Y:{y}")
        new_coords["buttons"][btn_name] = {"x": x, "y": y}
        
        # Khusus untuk klik kanan, kita kasih jeda biar user bisa buka menu dulu
        if "tree" in btn_name:
            print("   (ℹ️  Sekarang Klik Kanan manual di situ biar menu muncul...)")
            time.sleep(2)
        
    print("\n" + "="*50)
    print("💾 MENYIMPAN DATA BARU...")
    with open(FILE_JSON, 'w') as f:
        json.dump(new_coords, f, indent=4)
    
    print(f"🎉 SUKSES! File {FILE_JSON} telah diperbarui.")
    print("Sekarang coba jalankan script robot utama Anda.")

if __name__ == "__main__":
    main()