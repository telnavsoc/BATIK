import cv2
import os
import glob

# --- CONFIG ---
BASE_DIR = r'F:\BATIK\Project_BATIK'
INPUT_FOLDER = os.path.join(BASE_DIR, 'evidence')
OUTPUT_FILE = os.path.join(BASE_DIR, 'calibration_result_v3.jpg')

def draw_boxes(image_path):
    img = cv2.imread(image_path)
    if img is None:
        print("❌ Gambar tidak ditemukan!")
        return

    h, w = img.shape[:2]
    print(f"📏 Dimensi: {w}x{h}")

    # --- KOORDINAT REVISI V3 (TARGET MONITOR 2 - TENGAH) ---
    # Analisis visual dari gambar 'edited-image.png'
    
    # Lebar (X): Kolom 'Data' berada kira-kira di tengah (sedikit ke kanan)
    # Estimasi X: 49% s/d 55%
    x_start = int(w * 0.49)
    x_end = int(w * 0.56)

    # Tinggi (Y): 
    # Monitor 2 RF Level ada di sekitar pertengahan vertikal.
    # Estimasi Y RF: 48% s/d 52%
    rf_y1 = int(h * 0.48)
    rf_y2 = int(h * 0.525)
    
    # Monitor 2 Ident Mod ada tepat di bawahnya.
    # Estimasi Y Ident: 52.5% s/d 57%
    id_y1 = int(h * 0.525)
    id_y2 = int(h * 0.57)

    # --- GAMBAR KOTAK ---
    
    # 1. RF LEVEL (Monitor 2) - MERAH
    cv2.rectangle(img, (x_start, rf_y1), (x_end, rf_y2), (0, 0, 255), 2)
    cv2.putText(img, "MONITOR 2 RF", (x_start - 100, rf_y1 + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    # 2. IDENT MOD (Monitor 2) - BIRU
    cv2.rectangle(img, (x_start, id_y1), (x_end, id_y2), (255, 0, 0), 2)
    cv2.putText(img, "MONITOR 2 IDENT", (x_start - 120, id_y2 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

    # Simpan
    cv2.imwrite(OUTPUT_FILE, img)
    print(f"✅ Hasil V3 disimpan di: {OUTPUT_FILE}")
    print("👉 Silakan cek apakah kotak merah & biru sudah pas di angka hijau?")

def main():
    files = glob.glob(os.path.join(INPUT_FOLDER, '*.jpg')) + \
            glob.glob(os.path.join(INPUT_FOLDER, '*.png')) + \
            glob.glob(os.path.join(INPUT_FOLDER, '*.jpeg'))
            
    if not files:
        print("⚠️ Folder evidence kosong!")
        return

    print(f"📂 Menggunakan file: {files[0]}")
    draw_boxes(files[0])

if __name__ == "__main__":
    main()