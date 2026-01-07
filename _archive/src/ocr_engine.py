import cv2
import pytesseract
import pandas as pd
import datetime
import os
import glob
import shutil
from PIL import Image

# --- CONFIG ---
# Pastikan path ini sesuai dengan lokasi install Tesseract di PC Anda
pytesseract.pytesseract.tesseract_cmd = r'F:\BATIK\Tesseract-OCR\tesseract.exe'

BASE_DIR = r'F:\BATIK\Project_BATIK'
INPUT_FOLDER = os.path.join(BASE_DIR, 'evidence')
PROCESSED_FOLDER = os.path.join(BASE_DIR, 'processed')
OUTPUT_CSV = os.path.join(BASE_DIR, 'output_data', 'laporan_harian.csv')
DEBUG_FOLDER = os.path.join(BASE_DIR, 'debug_crops')

# Pastikan semua folder yang dibutuhkan sudah tersedia
for folder in [PROCESSED_FOLDER, os.path.dirname(OUTPUT_CSV), DEBUG_FOLDER]:
    os.makedirs(folder, exist_ok=True)

def baca_angka_akurat(img_crop, nama_debug):
    """
    Memproses potongan gambar dengan Zoom 5x dan Grayscale, 
    lalu dibaca menggunakan Tesseract dengan Whitelist Angka.
    """
    # 1. ZOOM 5X (CUBIC) - Membuat angka kecil menjadi besar dan halus
    roi = cv2.resize(img_crop, None, fx=5, fy=5, interpolation=cv2.INTER_CUBIC)
    
    # 2. GRAYSCALE - Menghilangkan gangguan warna
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    
    # 3. CONVERT KE PIL IMAGE - Menjamin stabilitas pembacaan di semua format file (JPG/PNG/JPEG)
    pil_img = Image.fromarray(gray)
    
    # Simpan hasil pemrosesan untuk pengecekan (Debug)
    cv2.imwrite(os.path.join(DEBUG_FOLDER, f"FINAL_{nama_debug}.jpg"), gray)

    # 4. KONFIGURASI OCR - Whitelist hanya angka (0-9) dan titik (.)
    custom_config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789.'
    
    try:
        hasil = pytesseract.image_to_string(pil_img, config=custom_config)
        return hasil.strip()
    except:
        return ""

def clean_logic(raw_text, limit):
    """
    Fungsi untuk membersihkan teks hasil OCR dan memperbaiki posisi desimal jika perlu.
    """
    try:
        val = float(raw_text)
        # Jika angka terlalu besar (misal 805 padahal harusnya 80.5), bagi dengan 10
        if val > limit: 
            val = val / 10
        return str(val)
    except:
        return "0"

def main():
    print("🚀 MENJALANKAN ULTIMATE TESSERACT (FULL BATCH)...")
    
    # Ambil semua file gambar di folder evidence
    files = glob.glob(os.path.join(INPUT_FOLDER, "*.*"))
    files = [f for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    
    if not files:
        print("⚠️ Folder 'evidence' kosong. Tidak ada yang diproses.")
        return

    print(f"📂 Ditemukan {len(files)} file.\n")
    all_data = []

    for f in files:
        fname = os.path.basename(f)
        print(f"👉 Memproses: {fname}...", end=" ")
        
        img = cv2.imread(f)
        if img is None:
            print("❌ Gambar tidak bisa dibaca.")
            continue
        
        # --- KOORDINAT PIXEL KERAMAT ---
        # Diambil dari data yang sudah terbukti sukses (Monitor 2)
        # Format: img[y1:y2, x1:x2]
        crop_id = img[321:333, 436:458] # Ident Modulation
        crop_rf = img[300:313, 436:457] # RF Level
        
        # Eksekusi OCR
        raw_id = baca_angka_akurat(crop_id, f"ID_{fname}")
        raw_rf = baca_angka_akurat(crop_rf, f"RF_{fname}")

        # Pembersihan Data
        val_id = clean_logic(raw_id, 100)
        val_rf = clean_logic(raw_rf, 20)

        print(f"✅ Hasil -> ID: {val_id} | RF: {val_rf}")
        
        # Masukkan ke daftar data
        all_data.append({
            'Timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'Filename': fname,
            'Ident_Modulation': val_id,
            'RF_Level': val_rf
        })

        # --- OTOMATISASI PINDAH FILE ---
        # Memindahkan file yang sudah diproses ke folder 'processed'
        dest_path = os.path.join(PROCESSED_FOLDER, fname)
        if os.path.exists(dest_path):
            os.remove(dest_path) # Hapus jika sudah ada file lama
        shutil.move(f, dest_path)

    # Simpan semua hasil scan ke satu file CSV
    if all_data:
        df = pd.DataFrame(all_data)
        file_exists = os.path.isfile(OUTPUT_CSV)
        df.to_csv(OUTPUT_CSV, mode='a', header=not file_exists, index=False)
        print(f"\n📊 Data berhasil disimpan di: {OUTPUT_CSV}")

    print(f"🏁 Selesai. Folder 'evidence' sekarang kosong.")

if __name__ == "__main__":
    main()