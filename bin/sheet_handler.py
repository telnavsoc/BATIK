# FILE: bin/sheet_handler.py
# ================================================================
# GOOGLE SHEET HANDLER FOR BATIK SOLO
# ================================================================

import gspread
import os

# NAMA FILE GOOGLE SHEET ANDA (Harus sama persis dengan di Google Drive)
SHEET_NAME = "LOGBOOK_BATIK"

# Path ke credentials.json (Asumsi ada di folder root project/parent dari bin)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")

def connect_gsheet():
    """Melakukan koneksi auth ke Google Cloud"""
    try:
        if not os.path.exists(CREDENTIALS_FILE):
            return None, f"File credentials.json tidak ditemukan di: {CREDENTIALS_FILE}"
        
        gc = gspread.service_account(filename=CREDENTIALS_FILE)
        sh = gc.open(SHEET_NAME)
        return sh, None
    except Exception as e:
        return None, str(e)

def upload_data_to_sheet(tool_name, rows_data):
    """
    Mengupload data hasil parsing ke Tab (Worksheet) spesifik.
    """
    sh, err = connect_gsheet()
    if err: return None, None, err

    # 1. Bersihkan Nama Tab (GSheet tidak suka karakter aneh)
    # Contoh: "LOC/15" -> "LOC_15"
    tab_title = tool_name.replace("/", "_").replace("\\", "_").replace(" ", "_").upper()
    tab_title = tab_title[:99] # Batas karakter nama tab

    # 2. Cari atau Buat Worksheet
    try:
        worksheet = sh.worksheet(tab_title)
    except:
        # Jika belum ada, buat baru dengan header dasar
        worksheet = sh.add_worksheet(title=tab_title, rows=100, cols=10)

    # 3. Konversi Data Parsing ke Format List-of-Lists (Matrix)
    # Format: [Col A, Col B, Col C]
    matrix = [['PARAMETER', 'MONITOR 1', 'MONITOR 2']] # Header Row
    
    for row in rows_data:
        p = row.get('Parameter', '')
        m1 = row.get('Monitor 1', '')
        m2 = row.get('Monitor 2', '')
        rtype = row.get('Type', 'Data')
        
        if rtype == 'Header':
            matrix.append([f"--- {p} ---", "", ""])
        elif rtype == 'Separator':
            matrix.append(["", "", ""])
        else:
            matrix.append([p, m1, m2])

    # 4. Upload Data
    # Kita pakai clear() agar data lama bersih, lalu update.
    # Note: Ini akan mereset formatting cell. Jika ingin formatting tetap,
    # hapus baris worksheet.clear() dan pastikan manual formatting di GSheet.
    worksheet.clear() 
    worksheet.update('A1', matrix)

    # 5. Return ID untuk Iframe
    return sh.id, worksheet.id, None