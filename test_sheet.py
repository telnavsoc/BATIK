import gspread

# 1. Koneksi menggunakan file JSON tadi
gc = gspread.service_account(filename='credentials.json')

# 2. Buka Sheet berdasarkan Judul File
# Pastikan nama ini SAMA PERSIS dengan nama file di Google Sheet
sh = gc.open("LOGBOOK_BATIK") 

# 3. Pilih Worksheet pertama (Sheet1)
worksheet = sh.sheet1

# 4. Coba tulis sesuatu di kotak A1
worksheet.update_acell('A1', 'Tes Koneksi Sukses!')
worksheet.update_acell('B1', 'Halo Pak ATSEP!')

print("Berhasil nulis di Google Sheet! Coba cek di browser.")