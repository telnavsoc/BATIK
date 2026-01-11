# FILE: bin/compress_bg.py
from PIL import Image
import os

# Path
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
input_path = os.path.join(base_dir, "background.png")
output_path = os.path.join(base_dir, "background_lite.jpg") # Kita ubah ke JPG agar ringan

print(f"Mengompres: {input_path}")

try:
    with Image.open(input_path) as img:
        # 1. Resize jika terlalu besar (Max lebar 1920px)
        if img.width > 1920:
            ratio = 1920 / float(img.width)
            h_size = int((float(img.height) * float(ratio)))
            img = img.resize((1920, h_size), Image.Resampling.LANCZOS)
        
        # 2. Convert ke RGB (jika PNG transparan) agar bisa jadi JPG
        rgb_im = img.convert('RGB')
        
        # 3. Simpan dengan kualitas 75% (Cukup untuk background)
        rgb_im.save(output_path, "JPEG", quality=75, optimize=True)
        
    print(f"✅ Sukses! File baru tersimpan di: {output_path}")
    print("Ukuran file sekarang jauh lebih kecil.")
    
except Exception as e:
    print(f"❌ Error: {e}")