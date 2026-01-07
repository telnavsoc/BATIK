import pandas as pd
import os
from datetime import datetime

def simpan_ke_csv(data_dictionary):
    """
    Fungsi ini menerima data dalam bentuk Dictionary,
    lalu menyimpannya ke file laporan.csv (Mode Append/Nambah bawah)
    """
    
    # 1. Tentukan Lokasi Penyimpanan
    # Kita simpan di folder 'output_data' di dalam project
    lokasi_script = os.path.dirname(os.path.abspath(__file__))
    folder_project = os.path.dirname(lokasi_script)
    folder_output = os.path.join(folder_project, "output_data")
    
    # Buat folder output jika belum ada
    if not os.path.exists(folder_output):
        os.makedirs(folder_output)
        
    nama_file = os.path.join(folder_output, "laporan_harian.csv")

    # 2. Konversi Dictionary jadi DataFrame (Tabel)
    # Kita bungkus dictionary ke dalam list [] agar jadi satu baris
    df_baru = pd.DataFrame([data_dictionary])

    # 3. Simpan ke File
    if not os.path.exists(nama_file):
        # Jika file belum ada, buat baru dengan Header (Judul Kolom)
        df_baru.to_csv(nama_file, index=False, sep=',')
        print(f"📄 File baru dibuat: {nama_file}")
    else:
        # Jika file sudah ada, tempel di baris paling bawah (mode='a')
        # header=False artinya jangan tulis ulang judul kolomnya
        df_baru.to_csv(nama_file, mode='a', header=False, index=False, sep=',')
        print(f"💾 Data berhasil ditambahkan ke: {nama_file}")

# --- BLOK TEST (Jalankan ini di PC Rumah untuk tes buat file) ---
if __name__ == "__main__":
    # Pura-puranya ini data dari OCR
    data_palsu = {
        'Waktu_Scan': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'IDENT MODULATION': '80.5',
        'RF Level': '5.9'
    }
    
    print("Tes menyimpan data di PC Rumah...")
    simpan_ke_csv(data_palsu)