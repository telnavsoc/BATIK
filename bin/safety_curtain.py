# FILE: bin/safety_curtain.py
# ================================================================
# BATIK SAFETY CURTAIN V7 (WITH LOADING ANIMATION)
# Visual: Wide Frame, Transparent, + Moving Loading Bar
# Mouse: Tembus (Ghost Mode)
# ================================================================

import tkinter as tk
from tkinter import ttk  # Wajib import ini untuk Progress Bar
import sys
import threading
import time
import os
from ctypes import windll
from PIL import Image, ImageTk 

# --- KONFIGURASI PATH ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR) 

STOP_FLAG = os.path.join(BASE_DIR, "STOP_SIGNAL")
LOGO_PATH = os.path.join(PROJECT_ROOT, "logo.png")

BG_PATH = os.path.join(PROJECT_ROOT, "background.png")
if not os.path.exists(BG_PATH):
    BG_PATH = os.path.join(PROJECT_ROOT, "background_lite.jpg")

# --- KONSTANTA WINDOWS ---
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
VK_ESCAPE = 0x1B

class SafetyCurtain:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("BATIK SAFETY MODE")
        
        # 1. Setup Fullscreen & Transparent
        self.root.attributes('-fullscreen', True)
        self.root.attributes('-topmost', True)
        self.root.configure(bg='black')
        self.root.attributes('-alpha', 0.75) # Transparansi 75%

        self.screen_w = self.root.winfo_screenwidth()
        self.screen_h = self.root.winfo_screenheight()

        # 2. Setup Background
        self.bg_photo = None
        if os.path.exists(BG_PATH):
            try:
                img = Image.open(BG_PATH)
                img = img.resize((self.screen_w, self.screen_h), Image.Resampling.LANCZOS)
                self.bg_photo = ImageTk.PhotoImage(img)
                tk.Label(self.root, image=self.bg_photo).place(x=0, y=0, relwidth=1, relheight=1)
            except: pass

        # 3. Setup Container Tengah (Frame Utama)
        # padx diperbesar agar frame lebar
        self.frame = tk.Frame(self.root, bg='#000000', bd=4, relief="ridge", padx=100, pady=30)
        self.frame.place(relx=0.5, rely=0.5, anchor="center")

        # 4. Logo
        if os.path.exists(LOGO_PATH):
            try:
                logo_raw = Image.open(LOGO_PATH)
                base_width = 300 
                w_pct = (base_width / float(logo_raw.size[0]))
                h_size = int((float(logo_raw.size[1]) * float(w_pct)))
                logo_resized = logo_raw.resize((base_width, h_size), Image.Resampling.LANCZOS)
                self.logo_photo = ImageTk.PhotoImage(logo_resized)
                tk.Label(self.frame, image=self.logo_photo, bg='black').pack(pady=(0, 20))
            except: pass

        # 5. Teks Judul
        tk.Label(self.frame, text="Sedang Dilakukan Pembacaan Parameter Peralatan", 
                 font=("Segoe UI", 24, "bold"), fg="#FFFFFF", bg="black").pack(pady=(0, 10))
        
        tk.Label(self.frame, text="Harap Jangan Sentuh Mouse dan Keyboard", 
                 font=("Segoe UI", 16), fg="#FFAA00", bg="black").pack(pady=(0, 20))

        # --- FITUR BARU: ANIMASI LOADING ---
        # Kita buat style custom agar barnya berwarna Oranye (sesuai tema peringatan)
        style = ttk.Style()
        style.theme_use('clam') # Tema 'clam' lebih mudah dikustomisasi warnanya
        style.configure("Batik.Horizontal.TProgressbar", 
                        background="#FFAA00",  # Warna balok yang bergerak (Oranye)
                        troughcolor="#333333", # Warna jalur lintasan (Abu Gelap)
                        bordercolor="#000000", 
                        lightcolor="#FFAA00", 
                        darkcolor="#FFAA00")
        
        # Buat Bar
        self.pbar = ttk.Progressbar(self.frame, style="Batik.Horizontal.TProgressbar", 
                                    orient="horizontal", length=600, mode="indeterminate")
        self.pbar.pack(pady=(10, 20))
        
        # Jalankan Animasi (Angka 15 = kecepatan milidetik, makin kecil makin ngebut)
        self.pbar.start(15) 
        # -----------------------------------

        # Footer (Tombol Batal)
        self.status_label = tk.Label(self.root, text="Tekan [ESC] Untuk Membatalkan", 
                                     font=("Consolas", 14, "bold"), fg="white", bg="#AA0000", pady=15)
        self.status_label.pack(side="bottom", fill="x")

        # 6. Jalankan System Listener
        self.clean_stop_signal()
        self.monitor_thread = threading.Thread(target=self.global_esc_listener, daemon=True)
        self.monitor_thread.start()

        # 7. Aktifkan Ghost Mode
        self.root.after(100, self.set_click_through)

    def clean_stop_signal(self):
        if os.path.exists(STOP_FLAG):
            try: os.remove(STOP_FLAG)
            except: pass

    def set_click_through(self):
        """Membuat window tembus klik mouse"""
        try:
            hwnd = windll.user32.GetParent(self.root.winfo_id())
            style = windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = style | WS_EX_LAYERED | WS_EX_TRANSPARENT
            windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        except: pass

    def global_esc_listener(self):
        while True:
            if windll.user32.GetAsyncKeyState(VK_ESCAPE) & 0x8000:
                self.trigger_emergency_stop()
                break
            time.sleep(0.05)

    def trigger_emergency_stop(self):
        with open(STOP_FLAG, "w") as f:
            f.write("STOP")
        
        self.root.after(0, lambda: self.status_label.config(
            text="!!! MEMBATALKAN PROSES... HARAP TUNGGU !!!", bg="red"
        ))
        
        time.sleep(1.5)
        self.root.destroy()
        sys.exit(0)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = SafetyCurtain()
    app.run()