from pywinauto import Application, Desktop
import time
import sys

# Konfigurasi Path PMDT
PMDT_PATH = r"D:\ILS APP\PMDT v8.7.2.0\PMDT.exe"

def print_structure_delayed(window_title_part, delay=5):
    print("="*50)
    print(f"   ⏳ JEDA {delay} DETIK...")
    print(f"   👉 Silakan pindah ke PMDT dan buka bagian '{window_title_part}' sekarang!")
    print("="*50)
    
    # Hitung mundur
    for i in range(delay, 0, -1):
        print(f"   {i}...", end="\r")
        time.sleep(1)
    print("   📸 CEKREK! Mengambil struktur GUI...")

    try:
        # Sambungkan ke aplikasi
        app = Application(backend="win32").connect(path=PMDT_PATH)
        
        # Cari jendela
        dlg = app.window(title_re=f".*{window_title_part}.*")
        
        if not dlg.exists():
            print(f"❌ Jendela dengan judul mengandung '{window_title_part}' TIDAK DITEMUKAN.")
            print("   Tips: Pastikan jendela/popup tersebut sudah muncul di layar.")
            return

        # Print struktur
        dlg.print_control_identifiers()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("ALAT INSPEKSI GUI (DENGAN TIMER)")
    print("--------------------------------")
    print("1. Inspeksi Popup Koneksi ('System Directory')")
    print("2. Inspeksi Popup Login ('Login')")
    print("3. Inspeksi Localizer ('Localizer')")
    
    pilih = input("\nPilih (1-3): ")
    
    if pilih == '1':
        # Kita cari jendela yang judulnya 'System Directory'
        # Atau 'No Connection' jika popupnya nempel di induk (kita coba System Directory dulu)
        print_structure_delayed("System Directory", delay=8) 
        
    elif pilih == '2':
        print_structure_delayed("Login", delay=8)
        
    elif pilih == '3':
        print_structure_delayed("Localizer", delay=5)