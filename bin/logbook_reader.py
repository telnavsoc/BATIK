# FILE: bin/logbook_reader.py
import gspread
import pandas as pd
import os

# --- SETUP KONEKSI ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_FILE = os.path.join(BASE_DIR, 'credentials.json')
MASTER_SPREADSHEET_NAME = "LOGBOOK_BATIK" 

def get_gspread_client():
    if not os.path.exists(CREDENTIALS_FILE):
        return None
    return gspread.service_account(filename=CREDENTIALS_FILE)

def fetch_data_from_last_sheet(tool_code):
    """
    Membaca Sheet Helper 'LAST_...' dengan cerdas.
    Memisahkan Info Header (Row 1-2) dengan Tabel Data (Row 4+).
    """
    try:
        gc = get_gspread_client()
        if not gc: return None, None, "Credentials missing."

        # 1. Buka Spreadsheet
        try:
            sh = gc.open(MASTER_SPREADSHEET_NAME)
        except:
            return None, None, f"File '{MASTER_SPREADSHEET_NAME}' tidak ditemukan."

        target_sheet_name = f"LAST_{tool_code}"
        try:
            worksheet = sh.worksheet(target_sheet_name)
        except:
            return None, None, f"Sheet '{target_sheet_name}' tidak ditemukan."

        # 2. Ambil Semua Data
        all_values = worksheet.get_all_values()
        if not all_values or len(all_values) < 5: 
            return None, None, "Sheet kosong atau format salah."

        # 3. Ekstrak Info Metadata (Baris 1 & 2)
        # Sesuai snippet Anda: 
        # Row 0: "Data Terakhir: 13:59..."
        # Row 1: "Active TX : 2"
        info_last_update = all_values[0][0] # Ambil sel pojok kiri atas
        info_active_tx = all_values[1][0]   # Ambil sel bawahnya
        
        # Gabungkan jadi satu string info
        full_info_str = f"{info_last_update} | {info_active_tx}"

        # 4. Cari Lokasi Tabel (Mencari baris yang diawali "NO")
        table_start_idx = -1
        for i, row in enumerate(all_values):
            if row[0].strip().upper() == "NO" and row[1].strip().upper() == "PARAMETER":
                table_start_idx = i
                break
        
        if table_start_idx == -1:
            return None, None, "Tidak menemukan header tabel (NO, PARAMETER)."

        # 5. Parsing Header Bertingkat (Untuk menghindari Duplicate Column Error)
        # Struktur Sheet Anda:
        # Row A (Start): NO, PARAMETER, TANGGAL...
        # Row B (Next) : ,, Tx 1, , Tx 2...
        # Row C (Next) : ,, Mon 1, Mon 2...
        
        row_a = all_values[table_start_idx]
        row_b = all_values[table_start_idx + 1]
        row_c = all_values[table_start_idx + 2]
        
        final_headers = []
        last_tx = ""
        
        for j in range(len(row_c)):
            col_a = row_a[j].strip() # NO / PARAMETER
            col_b = row_b[j].strip() # Tx 1 / Tx 2
            col_c = row_c[j].strip() # Mon 1 / Mon 2
            
            # Logika Nama Kolom Unik
            if col_a: 
                # Kolom NO atau PARAMETER
                final_headers.append(col_a)
            else:
                # Kolom Data
                if col_b: last_tx = col_b # Ingat Tx terakhir (Fill Forward)
                
                # Nama Kolom: "Tx 1 - Mon 1"
                if last_tx and col_c:
                    header_name = f"{last_tx} - {col_c}"
                elif col_c:
                    header_name = col_c
                else:
                    header_name = f"Col_{j}" # Jaga-jaga kolom kosong
                
                final_headers.append(header_name)

        # 6. Buat DataFrame
        # Data dimulai setelah 3 baris header tadi
        data_rows_start = table_start_idx + 3
        data_content = all_values[data_rows_start:]
        
        df = pd.DataFrame(data_content, columns=final_headers)
        
        # Bersihkan baris yang parameter-nya kosong
        if 'PARAMETER' in df.columns:
            df = df[df['PARAMETER'] != ""]

        return df, full_info_str, None

    except Exception as e:
        return None, None, f"Error: {str(e)}"