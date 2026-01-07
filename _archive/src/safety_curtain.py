import tkinter as tk
import sys

def nyalakan_tirai_pengaman():
    """
    Fungsi ini membuat layar menjadi hitam transparan (blocker)
    dengan peringatan agar user tidak mengganggu proses.
    """
    # 1. Setup Jendela Utama
    root = tk.Tk()
    root.title("BATIK Safety Curtain")
    
    # 2. Bikin Fullscreen & Selalu di Atas
    root.attributes('-fullscreen', True)
    root.attributes('-topmost', True) # Agar tidak tertutup aplikasi lain
    
    # 3. Warna & Transparansi (Alpha)
    # Alpha 0.7 artinya 70% hitam, 30% tembus pandang
    root.configure(bg='black')
    root.attributes('-alpha', 0.85) 

    # 4. Tambahkan Teks Peringatan
    label_judul = tk.Label(root, 
                     text="⚠️ SISTEM BATIK SEDANG BEKERJA ⚠️", 
                     font=("Arial", 40, "bold"), 
                     fg="yellow", bg="black")
    label_judul.pack(expand=True)

    label_sub = tk.Label(root, 
                     text="Mohon JANGAN sentuh Mouse & Keyboard.\nRobot sedang mengambil data meter reading...", 
                     font=("Arial", 20), 
                     fg="white", bg="black")
    label_sub.pack(pady=20)

    label_info = tk.Label(root, 
                     text="(Tekan tombol 'ESC' di keyboard untuk membatalkan paksa)", 
                     font=("Arial", 12, "italic"), 
                     fg="gray", bg="black")
    label_info.pack(side="bottom", pady=50)

    # 5. Fungsi Tombol Darurat (ESC untuk keluar)
    def matikan_tirai(event):
        print("Tirai dimatikan oleh User.")
        root.destroy()
        sys.exit() # Hentikan script python

    root.bind('<Escape>', matikan_tirai)

    # Jalankan Jendela
    root.mainloop()

# Bagian ini hanya jalan jika file ini dijalankan langsung (bukan dipanggil)
if __name__ == "__main__":
    print("Menyalakan Safety Curtain...")
    nyalakan_tirai_pengaman()