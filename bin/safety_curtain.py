# FILE: bin/safety_curtain.py
# ================================================================
# BATIK SAFETY CURTAIN V2 (GLOBAL LISTENER)
# Bisa mendeteksi ESC walau tidak fokus
# ================================================================

import tkinter as tk
import sys
import threading
import time
import os
import ctypes

# PATH CONFIG
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STOP_FLAG = os.path.join(BASE_DIR, "STOP_SIGNAL")

class SafetyCurtain:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("BATIK SAFETY MODE")
        
        # UI Setup (Tetap Sama)
        self.root.attributes('-fullscreen', True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', 0.85)
        self.root.configure(bg='black')
        self.root.overrideredirect(True)

        tk.Label(self.root, text="⚠️ ROBOT SEDANG BEKERJA ⚠️", font=("Segoe UI", 30, "bold"), fg="#FF5555", bg="black").pack(expand=True)
        tk.Label(self.root, text="JANGAN SENTUH MOUSE DAN KEYBOARD", font=("Segoe UI", 14), fg="white", bg="black").pack(pady=(0, 50))
        
        self.status_label = tk.Label(self.root, text="TEKAN [ESC] UNTUK EMERGENCY STOP", font=("Consolas", 12), fg="yellow", bg="black")
        self.status_label.pack(side="bottom", pady=20)

        # Hapus file stop lama jika ada
        if os.path.exists(STOP_FLAG):
            try: os.remove(STOP_FLAG)
            except: pass

        # Jalankan Global Listener di Thread terpisah
        self.monitor_thread = threading.Thread(target=self.global_esc_listener, daemon=True)
        self.monitor_thread.start()

    def global_esc_listener(self):
        """
        Mendeteksi tombol ESC menggunakan Windows API (ctypes).
        Bekerja global walau fokus ada di aplikasi lain.
        """
        VK_ESCAPE = 0x1B
        
        while True:
            # Cek status tombol ESC (AsyncKeyState)
            # Jika bit paling signifikan aktif, berarti tombol sedang ditekan
            if ctypes.windll.user32.GetAsyncKeyState(VK_ESCAPE) & 0x8000:
                self.trigger_emergency_stop()
                break
            time.sleep(0.05) # Cek 20 kali per detik

    def trigger_emergency_stop(self):
        # 1. Buat File Sinyal (Untuk dibaca oleh Launcher)
        with open(STOP_FLAG, "w") as f:
            f.write("STOP")
        
        # 2. Update UI (Visual Feedback)
        try:
            self.status_label.config(text="!!! STOPPING ROBOT... PLEASE WAIT !!!", fg="red")
            self.root.update()
        except: pass
        
        print("[CURTAIN] ESC DETECTED! STOP SIGNAL SENT.")
        time.sleep(1) # Beri waktu launcher membaca file
        self.root.destroy()
        sys.exit(0)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = SafetyCurtain()
    app.run()