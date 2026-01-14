# FILE: bin/sheet_handler.py
# ================================================================
# GOOGLE SHEET HANDLER - V8 (FINAL CALIBRATION)
# ================================================================

import gspread
import os
import re
from datetime import datetime

SHEET_NAME = "LOGBOOK_BATIK"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")

# --- KALIBRASI SMART OFFSET ---
OFFSET_CONFIG = {
    # KELOMPOK NAIK 1 BARIS (Offset dikurangi jadi 3)
    "DVOR": 3,
    "MM":   3,
    "OM":   3,
    
    # KELOMPOK SUDAH OK (Offset tetap 3 & 4)
    "DME":  3, 
    "LOC":  4, 
    "GP":   4  
}

BULAN_ID = {
    1: "JANUARI", 2: "FEBRUARI", 3: "MARET", 4: "APRIL",
    5: "MEI", 6: "JUNI", 7: "JULI", 8: "AGUSTUS",
    9: "SEPTEMBER", 10: "OKTOBER", 11: "NOVEMBER", 12: "DESEMBER"
}

# --- MAPPING PARAMETER ---
PARAM_MAP = {
    "DVOR": {
        "Status": 1, "IDENT Code": 2, "CARRIER Frequency": 3, "USB Frequency": 4, 
        "LSB Frequency": 5, "CARRIER Output Power": 6, "RF Input Level": 7, 
        "Azimuth": 8, "9960Hz FM Index": 9, "30Hz AM Modulation Depth": 10,
        "9960Hz AM Modulation Depth": 11, "1020Hz AM Modulation Depth": 12
    },
    "DME": {
        "IDENT Code": 1, "Output Power": 2, "Frequency": 3, "System Delay": 4,
        "Reply Pulse Spacing": 5, "Reply Efficiency": 6, "Reply Pulse Rate": 7,
        "Reply Pulse Rise Time": 8, "Reply Pulse Decay Time": 9, "Reply Pulse Duration": 10
    },
    "LOC": {
        "Centerline RF Level": 1, "Centerline DDM": 2, "Centerline SDM": 3, 
        "Ident Mod Percent": 4, "Width DDM": 5, "Ident Status": 6,
        "RF Level": 8, "Clearance 1 DDM": 9, "SDM": 10, 
        "Ident Mod Percent": 11, "Clearance 2 DDM": 12, "Ident Status": 13,
        "RF Freq Difference": 14 
    },
    "GP": {
        "Path RF Level": 1, "Path DDM": 2, "Path SDM": 3, "Width DDM": 4,
        "RF Level": 6, "150Hz Mod Percent": 7, "RF Freq Difference": 8
    },
    "MM": { "RF Level": 1, "Ident Modulation": 2 },
    "OM": { "RF Level": 1, "Ident Modulation": 2 }
}

def connect_gsheet():
    try:
        if not os.path.exists(CREDENTIALS_FILE): return None, "Credential hilang."
        gc = gspread.service_account(filename=CREDENTIALS_FILE)
        sh = gc.open(SHEET_NAME)
        return sh, None
    except Exception as e: return None, str(e)

def get_tool_type(tool_name):
    t = tool_name.upper()
    if "DVOR" in t: return "DVOR"
    if "DME" in t: return "DME"
    if "LOC" in t: return "LOC"
    if "GLIDE" in t or "GP" in t: return "GP"
    if "MM" in t or "MIDDLE" in t: return "MM"
    if "OM" in t or "OUTER" in t: return "OM"
    return "DVOR"

def update_period_label(worksheet, date_obj):
    text = f": {BULAN_ID[date_obj.month]} {date_obj.year}"
    try: worksheet.update_acell('D5', text)
    except: pass

def get_or_create_monthly_sheet(sh, tool_type, date_obj):
    month_str = date_obj.strftime("%b %Y").upper()
    tab_name = f"{tool_type} {month_str}"
    template_name = f"TEMPLATE_{tool_type}"
    try:
        ws = sh.worksheet(tab_name)
        return ws, None
    except:
        try:
            template = sh.worksheet(template_name)
            new_sheet = sh.duplicate_sheet(template.id, insert_sheet_index=0, new_sheet_name=tab_name)
            update_period_label(new_sheet, date_obj)
            return new_sheet, None
        except: return None, f"Template {template_name} tidak ditemukan."

def find_safe_anchor(worksheet, day):
    try:
        header_keyword_cells = worksheet.findall("TANGGAL")
        if not header_keyword_cells: return None, "Header TANGGAL tidak ditemukan."

        valid_rows = []
        for cell in header_keyword_cells:
            valid_rows.append(cell.row)
            valid_rows.append(cell.row + 1)

        start_day_of_block = ((day - 1) // 4) * 4 + 1
        target_str = str(start_day_of_block)
        regex_day = re.compile(r"^" + target_str + r"$")
        
        candidate_cells = worksheet.findall(regex_day)
        final_anchor = None
        for cand in candidate_cells:
            if cand.row in valid_rows:
                final_anchor = cand
                break
        
        if final_anchor: return final_anchor, None
        else: return None, f"Tanggal {target_str} tidak ditemukan di Header."

    except Exception as e: return None, str(e)

def upload_data_to_sheet(tool_raw_name, rows_data, target_date=None, active_tx=1):
    sh, err = connect_gsheet()
    if err: return None, None, err

    tool_type = get_tool_type(tool_raw_name)
    current_date = target_date if target_date else datetime.now()
    day = current_date.day

    ws, err = get_or_create_monthly_sheet(sh, tool_type, current_date)
    if err: return None, None, err
    
    update_period_label(ws, current_date)

    anchor_cell, err_msg = find_safe_anchor(ws, day)
    if not anchor_cell: return None, None, f"Error Layout: {err_msg}"

    offset = OFFSET_CONFIG.get(tool_type, 4)
    base_row = anchor_cell.row + offset
    
    start_day_of_block = ((day - 1) // 4) * 4 + 1
    day_diff = day - start_day_of_block
    
    col_start_today = anchor_cell.col + (day_diff * 4)
    tx_shift = 0 if active_tx == 1 else 2
    target_col_final = col_start_today + tx_shift

    updates = []
    mapping = PARAM_MAP.get(tool_type, {})
    is_clearance = False

    for row in rows_data:
        p = row.get('Parameter')
        # Logic Deteksi Section LOC/GP
        if tool_type in ["LOC", "GP"] and "RF Level" in p and "Path" not in p and "Centerline" not in p: 
             is_clearance = True
        
        idx = 0
        if tool_type == "LOC":
            if "Ident Mod Percent" in p: idx = 11 if is_clearance else 4
            elif "Ident Status" in p: idx = 13 if is_clearance else 6
            elif p in mapping: idx = mapping[p]
            else:
                for k in mapping: 
                    if k in p: idx = mapping[k]; break
        else:
            if p in mapping: idx = mapping[p]
            else:
                for k in mapping: 
                    if k in p: idx = mapping[k]; break

        if idx > 0:
            r = base_row + (idx - 1)
            c = target_col_final
            updates.append({'range': gspread.utils.rowcol_to_a1(r, c), 'values': [[row.get('Monitor 1', '-')]]})
            updates.append({'range': gspread.utils.rowcol_to_a1(r, c+1), 'values': [[row.get('Monitor 2', '-')]]})

    if updates: ws.batch_update(updates)
    return sh.id, ws.id, None