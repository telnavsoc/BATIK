# FILE: bin/safety_curtain.py
# ================================================================
# BATIK SAFETY CURTAIN V7.2 (CENTERED LAYOUT)
# ================================================================

import tkinter as tk
from tkinter import ttk
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
LOG_FILE = os.path.join(BASE_DIR, "live_monitor.log")
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
        self.root.attributes('-alpha', 0.85)

        self.screen_w = self.root.winfo_screenwidth()
        self.screen_h = self.root.winfo_screenheight()

        # 2. Background Image
        self.bg_photo = None
        if os.path.exists(BG_PATH):
            try:
                img = Image.open(BG_PATH)
                img = img.resize((self.screen_w, self.screen_h), Image.Resampling.LANCZOS)
                self.bg_photo = ImageTk.PhotoImage(img)
                tk.Label(self.root, image=self.bg_photo).place(x=0, y=0, relwidth=1, relheight=1)
            except: pass

        # 3. CONTAINER UTAMA (WRAPPER) - PUSAT TENGAH
        # Ini adalah wadah transparan yang menampung Kotak Judul & Terminal
        self.wrapper = tk.Frame(self.root, bg='black')
        # Trik agar wrapper transparan mengikuti alpha root, kita set bg sama dengan root
        # Anchor center memastikan wrapper benar-benar di tengah
        self.wrapper.place(relx=0.5, rely=0.5, anchor="center")

        # --- A. KOTAK JUDUL (ORIGINAL) ---
        # Dimasukkan ke dalam wrapper, side top
        self.frame = tk.Frame(self.wrapper, bg='#000000', bd=4, relief="ridge", padx=100, pady=30)
        self.frame.pack(side="top", fill="x")

        # Logo
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

        # Teks
        tk.Label(self.frame, text="Sedang Dilakukan Pembacaan Parameter Peralatan", 
                 font=("Segoe UI", 24, "bold"), fg="#FFFFFF", bg="black").pack(pady=(0, 10))
        
        tk.Label(self.frame, text="Harap Jangan Sentuh Mouse dan Keyboard", 
                 font=("Segoe UI", 16), fg="#FFAA00", bg="black").pack(pady=(0, 20))

        # Loading Bar
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Batik.Horizontal.TProgressbar", 
                        background="#FFAA00", troughcolor="#333333", 
                        bordercolor="#000000", lightcolor="#FFAA00", darkcolor="#FFAA00")
        
        self.pbar = ttk.Progressbar(self.frame, style="Batik.Horizontal.TProgressbar", 
                                    orient="horizontal", length=600, mode="indeterminate")
        self.pbar.pack(pady=(10, 20))
        self.pbar.start(15)

        # --- B. KOTAK TERMINAL (BARU) ---
        # Ditaruh di bawah kotak judul, di dalam wrapper yang sama
        # fill="x" memaksanya selebar kotak judul (karena kotak judul lebih lebar)
        self.term_frame = tk.Frame(self.wrapper, bg='#000000', bd=4, relief="ridge")
        self.term_frame.pack(side="top", fill="x", pady=(10, 0)) # Jarak 10px dari atas

        # Header Terminal
        tk.Label(self.term_frame, text=":: LIVE ACTIVITY LOG ::", font=("Consolas", 10, "bold"), 
                 fg="#888888", bg="black", anchor="w", padx=10, pady=5).pack(fill="x")

        # Text Area
        # Height=8 baris agar tidak terlalu tinggi
        self.term_text = tk.Text(self.term_frame, bg="black", fg="#00ff00", 
                                 font=("Consolas", 10), bd=0, padx=10, pady=5, 
                                 height=8, state=tk.DISABLED)
        self.term_text.pack(fill="both", expand=True)


        # --- FOOTER (TOMBOL BATAL) ---
        # Tetap di paling bawah layar
        self.status_label = tk.Label(self.root, text="Tekan [ESC] Untuk Membatalkan", 
                                     font=("Consolas", 14, "bold"), fg="white", bg="#AA0000", pady=15)
        self.status_label.pack(side="bottom", fill="x")

        # --- LOGIC ---
        self.clean_stop_signal()
        self.last_log_pos = 0
        
        self.monitor_thread = threading.Thread(target=self.global_esc_listener, daemon=True)
        self.monitor_thread.start()

        self.update_log_ui()
        self.root.after(100, self.set_click_through)

    def clean_stop_signal(self):
        if os.path.exists(STOP_FLAG):
            try: os.remove(STOP_FLAG)
            except: pass
        if os.path.exists(LOG_FILE):
             with open(LOG_FILE, "w") as f: f.write("")

    def set_click_through(self):
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

    def update_log_ui(self):
        try:
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, "r") as f:
                    f.seek(self.last_log_pos)
                    new_lines = f.readlines()
                    if new_lines:
                        self.last_log_pos = f.tell()
                        self.term_text.config(state=tk.NORMAL)
                        for line in new_lines:
                            if line.strip():
                                self.term_text.insert(tk.END, " > " + line.strip() + "\n")
                        self.term_text.see(tk.END)
                        self.term_text.config(state=tk.DISABLED)
        except: pass
        self.root.after(500, self.update_log_ui)

    def trigger_emergency_stop(self):
        with open(STOP_FLAG, "w") as f: f.write("STOP")
        self.root.after(0, lambda: self.status_label.config(
            text="!!! MEMBATALKAN PROSES... HARAP TUNGGU !!!", bg="red"))
        time.sleep(1.5)
        self.root.destroy()
        sys.exit(0)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = SafetyCurtain()
    app.run()