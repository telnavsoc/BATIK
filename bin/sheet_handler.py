# FILE: bin/sheet_handler.py
# ================================================================
# GOOGLE SHEET HANDLER - V10.0 (CLEAN RAW DATA MODE)
# ================================================================

import gspread
import os
from datetime import datetime

SHEET_NAME = "LOGBOOK_BATIK"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")

def connect_gsheet():
    try:
        if not os.path.exists(CREDENTIALS_FILE): return None, "Credential hilang."
        gc = gspread.service_account(filename=CREDENTIALS_FILE)
        sh = gc.open(SHEET_NAME)
        return sh, None
    except Exception as e: return None, str(e)

def get_tool_type(tool_name):
    """Normalisasi nama alat."""
    t = tool_name.upper()
    if "DVOR" in t: return "DVOR"
    if "DME" in t: return "DME"
    if "LOC" in t: return "LOC"
    if "GLIDE" in t or "GP" in t: return "GP"
    if "MM" in t or "MIDDLE" in t: return "MM"
    if "OM" in t or "OUTER" in t: return "OM"
    return "UNKNOWN"

def upload_raw_data(tool_name, rows_data, timestamp, active_tx):
    """
    FUNGSI TUNGGAL: Upload ke Sheet RAW Tahunan (Hidden).
    Sheet Name otomatis: RAW_DVOR_2026, RAW_GP_2026, dst.
    """
    sh, err = connect_gsheet()
    if err:
        return None, f"Connection Error: {err}"

    # 1. Tentukan Nama Sheet Unik per Alat & Tahun
    tool_type = get_tool_type(tool_name)
    current_year = timestamp.year
    raw_sheet_title = f"RAW_{tool_type}_{current_year}"

    ws = None
    try:
        # Coba buka sheet yang sudah ada
        ws = sh.worksheet(raw_sheet_title)
    except gspread.WorksheetNotFound:
        try:
            # Jika belum ada, BUAT BARU
            ws = sh.add_worksheet(title=raw_sheet_title, rows=1000, cols=10)
            
            # --- LANGSUNG SEMBUNYIKAN (HIDE) ---
            try:
                sh.batch_update({
                    "requests": [{
                        "updateSheetProperties": {
                            "properties": {"sheetId": ws.id, "hidden": True},
                            "fields": "hidden"
                        }
                    }]
                })
                print(f"[INFO] Sheet Database '{raw_sheet_title}' dibuat dan disembunyikan.")
            except: pass
            
            # Buat Header Database
            header = ["TIMESTAMP", "TANGGAL", "JAM", "PARAMETER", "MONITOR 1", "MONITOR 2", "ACTIVE TX", "SOURCE"]
            ws.append_row(header)
            ws.freeze(rows=1) 
            
        except Exception as e:
            return None, f"Gagal membuat sheet RAW: {str(e)}"

    # 2. Siapkan Payload Data
    payload = []
    date_str = timestamp.strftime("%Y-%m-%d") # Format ISO
    time_str = timestamp.strftime("%H:%M:%S")
    
    for row in rows_data:
        param = row.get('Parameter', 'Unknown')
        val1 = row.get('Monitor 1', '-')
        val2 = row.get('Monitor 2', '-')
        
        # Format Database: Baris per Baris
        payload.append([
            str(timestamp),  # Col A
            date_str,        # Col B (Kunci Rumus)
            time_str,        # Col C
            param,           # Col D (Kunci Rumus)
            val1,            # Col E
            val2,            # Col F
            active_tx,       # Col G
            "ROBOT_AUTO"     # Col H
        ])

    # 3. Eksekusi Append (Cepat & Hemat API)
    try:
        ws.append_rows(payload)
        return "Success", None
    except Exception as e:
        return None, f"Error appending RAW data: {str(e)}"