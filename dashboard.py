# FILE: dashboard.py
# ================================================================
# BATIK SOLO DASHBOARD V15 (REVISED PARSERS FOR LOC/GP/DME)
# ================================================================

import streamlit as st
import pandas as pd
import os
import sys
import subprocess
import time
import base64
from datetime import datetime
import sqlite3
import re

# --- CONFIG & PATHS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE_DIR, "bin"))
import config 

st.set_page_config(
    page_title="BATIK SOLO",
    page_icon="📒",
    layout="wide",
    initial_sidebar_state="expanded" 
)

LAUNCHER_SCRIPT = os.path.join(BASE_DIR, "bin", "run_with_curtain.py")
DB_PATH = config.DB_PATH

# --- SCHEMA DEFINITION (Untuk DVOR & Fallback) ---
SCHEMA_MARU = {
    "DVOR": [
        "Status", "IDENT Code", "CARRIER Frequency", "USB Frequency", "LSB Frequency",
        "CARRIER Output Power", "RF Input Level", "Azimuth", "9960Hz FM Index",
        "30Hz AM Modulation Depth", "9960Hz AM Modulation Depth", "1020Hz AM Modulation Depth"
    ]
}

# --- PARSER HELPER ---
def clean_val(v):
    """Membersihkan nilai dari whitespace berlebih"""
    if not v or v == "-": return ""
    return v.strip()

# --- PARSER MARU (DME / DVOR) ---
def parse_maru_data(tool_name, raw_text):
    """
    Revised: Menangani format DME spesifik (Section [Monitor]) dan DVOR.
    """
    rows = []
    
    # 1. DETEKSI FORMAT DME BARU (Sesuai Log yang Anda kirim)
    # Ciri: Ada [Monitor] dan TXP1 Measurement
    if "[Monitor]" in raw_text and "TXP1 Measurement" in raw_text:
        data_map = {}
        lines = raw_text.splitlines()
        in_monitor = False
        in_target = False # TXP1 Active
        
        # Parameter yang dicari untuk DME
        target_params = [
            "IDENT Code", "Output Power", "Frequency", "System Delay",
            "Reply Pulse Spacing", "Reply Efficiency", "Reply Pulse Rate",
            "Reply Pulse Rise Time", "Reply Pulse Decay Time", "Reply Pulse Duration"
        ]
        
        for line in lines:
            clean = line.strip()
            if clean == "[Monitor]":
                in_monitor = True; continue
            if not in_monitor: continue
            
            # Cari section active
            if "TXP1 Measurement" in clean and "Active" in clean:
                in_target = True; continue
            if "TXP2 Measurement" in clean: 
                in_target = False; break # Stop jika pindah ke TXP2
            
            if in_target:
                for param in target_params:
                    if clean.startswith(param):
                        # Ambil bagian nilai (hapus nama param)
                        val_part = clean.replace(param, "").strip()
                        # Ambil token non-whitespace. Format: Val1(M1) Val2(M2)
                        tokens = re.findall(r"(\S+)", val_part)
                        if len(tokens) >= 2:
                            # Token bisa berupa "100W" atau "SLO". Kita ambil raw stringnya.
                            data_map[param] = {"m1": tokens[0], "m2": tokens[1]}
        
        # Susun Rows
        for p in target_params:
            if p in data_map:
                rows.append({
                    "Parameter": p,
                    "Monitor 1": data_map[p]["m1"],
                    "Monitor 2": data_map[p]["m2"],
                    "Type": "Data"
                })
        
        # Tambahkan Status Umum jika ada
        if rows:
            return rows

    # 2. FALLBACK / LOGIC LAMA (Untuk DVOR atau Format Lama)
    data = {}
    lines = raw_text.splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith(";") or line.startswith("#") or line.startswith("["): continue
        
        parts = re.split(r'\s{2,}', line)
        if len(parts) >= 2:
            k = parts[0].strip()
            # Normalisasi
            if "Squitter" in k: k = "Reply Pulse Rate"
            if "Pulse Duration" in k: k = "Reply Pulse Duration"
            if "Output Power" in k and "CARRIER" not in k and "USB" not in k: k = "Output Power"
            
            v1 = parts[1].strip()
            v2 = parts[2].strip() if len(parts) > 2 else ""
            
            # Pisah unit
            if re.match(r'^[\d\.\-]+[a-zA-Z%]+$', v1):
                match = re.match(r'^([\d\.\-]+)([a-zA-Z%]+)$', v1)
                if match: v1 = f"{match.group(1)} {match.group(2)}"
            if re.match(r'^[\d\.\-]+[a-zA-Z%]+$', v2):
                match = re.match(r'^([\d\.\-]+)([a-zA-Z%]+)$', v2)
                if match: v2 = f"{match.group(1)} {match.group(2)}"

            data[k.lower()] = {"m1": v1, "m2": v2}

    tool_type = tool_name.upper().replace("_", " ")
    # Gunakan Schema DVOR jika cocok, atau default dump
    keys = SCHEMA_MARU.get(tool_type, [])
    if not keys: # Jika tidak ada di schema (misal DME format lama), tampilkan apa adanya
        keys = [k.title() for k in data.keys()]

    for req in keys:
        m1, m2 = "", ""
        for k_raw, vals in data.items():
            if req.lower() in k_raw:
                # Filter DVOR
                if "LSB" in req and "lsb" not in k_raw: continue
                if "USB" in req and "usb" not in k_raw: continue
                if "CARRIER" in req and "carrier" not in k_raw: continue
                m1, m2 = vals["m1"], vals["m2"]
                break
        if m1 or m2: # Hanya append jika data ditemukan
            rows.append({"Parameter": req, "Monitor 1": m1, "Monitor 2": m2, "Type": "Data"})
        
    return rows

# --- PARSER PMDT (MM / OM) ---
def parse_pmdt_mm_om(raw_text):
    mon1, mon2 = {}, {}
    curr_mon = 0
    lines = raw_text.splitlines()
    
    for line in lines:
        if "Monitor 1" in line: curr_mon = 1; continue
        if "Monitor 2" in line: curr_mon = 2; continue
        
        parts = line.split()
        if len(parts) > 4:
            unit = ""
            if parts[-1].isalpha() or parts[-1] == "%": unit = parts[-1]
            
            idx_num = -1
            for i, p in enumerate(parts):
                if re.match(r'^[-\d\.]+$', p): idx_num = i; break
            
            if idx_num != -1:
                param = " ".join(parts[:idx_num])
                try:
                    val = parts[idx_num + 2]
                    full = f"{val} {unit}".strip()
                    if curr_mon == 1: mon1[param] = full
                    elif curr_mon == 2: mon2[param] = full
                except: pass

    rows = []
    for req in ["RF Level", "Ident Modulation"]:
        rows.append({
            "Parameter": req, 
            "Monitor 1": mon1.get(req, ""), 
            "Monitor 2": mon2.get(req, ""),
            "Type": "Data"
        })
    return rows

# --- PARSER PMDT (LOC / GP) - REVISED ---
def parse_pmdt_loc_gp(tool_type, raw_text):
    """
    Revised: Parsing LOC/GP berdasarkan struktur Course/Clearance yang ketat
    dan penamaan parameter spesifik.
    """
    # Wadah data sementara
    data = {
        "Course": {},
        "Clearance": {},
        "RF Freq Difference": ["", ""],
        "Antenna Fault": ["", ""]
    }
    
    current_section = None
    lines = raw_text.splitlines()
    iterator = iter(lines)

    # Definisi Regex Pattern sesuai permintaan User
    # Format Tuple: (Nama Key di Dict, Regex Pattern)
    patterns = {
        "Course": [
            ("Centerline RF Level", r"Centerline RF Level\s+([\d\.]+)\s+([\d\.]+)"),
            ("Centerline DDM", r"Centerline DDM\s+([\d\.\-]+)\s+([\d\.\-]+)"),
            ("Centerline SDM", r"Centerline SDM\s+([\d\.]+)\s+([\d\.]+)"),
            ("Ident Mod Percent", r"Ident Mod Percent\s+([\d\.]+)\s+([\d\.]+)"),
            ("Width DDM", r"Width DDM\s+([\d\.]+)\s+([\d\.]+)"),
            ("Path RF Level", r"Path RF Level\s+([\d\.]+)\s+([\d\.]+)"), # GP
            ("Path DDM", r"Path DDM\s+([\d\.\-]+)\s+([\d\.\-]+)"),       # GP
            ("Path SDM", r"Path SDM\s+([\d\.]+)\s+([\d\.]+)"),           # GP
        ],
        "Clearance": [
            ("RF Level", r"RF Level\s+([\d\.]+)\s+([\d\.]+)"),
            ("Clearance 1 DDM", r"Clearance 1 DDM\s+([\d\.]+)\s+([\d\.]+)"),
            ("SDM", r"SDM\s+([\d\.]+)\s+([\d\.]+)"),
            ("Ident Mod Percent", r"Ident Mod Percent\s+([\d\.]+)\s+([\d\.]+)"),
            ("Clearance 2 DDM", r"Clearance 2 DDM\s+([\d\.]+)\s+([\d\.]+)"),
            ("150Hz Mod Percent", r"150Hz Mod Percent\s+([\d\.]+)\s+([\d\.]+)"), # GP
        ]
    }
    
    # Pattern Standalone (Global)
    standalone = [
        ("RF Freq Difference", r"RF Freq Difference\s+(\d+)\s+(\d+)"),
        ("Antenna Fault", r"Antenna Fault\s+(_|Normal|Alarm)\s+(_|Normal|Alarm)")
    ]

    # PROSES PARSING LINE-BY-LINE
    for line in iterator:
        clean_line = line.strip()
        
        # Deteksi Header Section
        if clean_line == "Course":
            current_section = "Course"
            continue
        elif clean_line == "Clearance":
            current_section = "Clearance"
            continue

        # Cek Standalone (General)
        for key, pat in standalone:
            match = re.search(pat, clean_line)
            if match:
                data[key] = [match.group(1), match.group(2)]

        # Cek Section Specific
        if current_section in patterns:
            for key, pat in patterns[current_section]:
                match = re.search(pat, clean_line)
                if match:
                    data[current_section][key] = [match.group(1), match.group(2)]

        # Special Case: Ident Status (Sering multiline atau inline)
        if "Ident Status" in clean_line and current_section:
            # Cek inline dulu
            inline_match = re.search(r"Ident Status\s+(Normal|Alarm)\s+(Normal|Alarm)", clean_line)
            if inline_match:
                 data[current_section]["Ident Status"] = [inline_match.group(1), inline_match.group(2)]
            else:
                # Coba intip baris selanjutnya jika inline gagal
                # (Sederhana: Kita asumsikan format log konsisten, jika kosong kita skip)
                try:
                    # Logic sederhana: Jika baris ini cuma "Ident Status", baris depan isinya status
                    # Namun karena iterator loop, agak tricky. Kita pakai regex multiline findall sederhana di baris ini
                    # Jika tidak ketemu, biarkan kosong.
                    pass
                except: pass
            
            # Special Handling manual untuk Log yang dikirim (Ident Status barisnya terpisah)
            # Karena file dibaca line by line, baris status "Normal Normal" akan dibaca iterasi berikutnya
            # Kita bisa pakai regex capture 'Normal' 'Normal' pada baris apapun jika belum assigned
            vals = re.findall(r"(Normal|Alarm)", clean_line)
            if len(vals) >= 2 and "Ident Status" not in clean_line:
                # Ini mungkin baris nilai status. Tapi berisiko salah tangkap.
                # Kita andalkan pattern matching ketat saja.
                pass
            
            # Fallback Ident Status (Inline check is safest for now based on log)
            # Kalau di log Anda: "Ident Status" (newline) "Normal Normal"
            # Kita tambah logic khusus:
            if clean_line.startswith("Ident Status"):
                # Cek line berikutnya manual? Tidak bisa di loop 'for line in iterator' standard dengan mudah.
                # Kita pakai regex global di akhir saja untuk Ident Status jika perlu.
                pass

    # KOREKSI IDENT STATUS (GLOBAL SEARCH) karena sifatnya multiline
    # Kita cari pattern: Ident Status \n ... Normal ... Normal
    # Menggunakan raw_text full
    matches_status = re.findall(r"Ident Status\s*\n\s*([a-zA-Z_]+)\s+([a-zA-Z_]+)", raw_text, re.MULTILINE)
    # Asumsi match pertama Course, kedua Clearance
    if len(matches_status) >= 1:
        data["Course"]["Ident Status"] = [matches_status[0][0], matches_status[0][1]]
    if len(matches_status) >= 2:
        data["Clearance"]["Ident Status"] = [matches_status[1][0], matches_status[1][1]]


    # MENYUSUN ROWS UNTUK UI (Urutan Sesuai Request)
    rows = []
    
    # 1. COURSE
    rows.append({"Parameter": "COURSE", "Monitor 1": "", "Monitor 2": "", "Type": "Header"})
    
    if tool_type == "LOCALIZER":
        # Daftar parameter LOC Course
        keys = ["Centerline RF Level", "Centerline DDM", "Centerline SDM", "Ident Mod Percent", "Width DDM", "Ident Status"]
        suffix_unit = {"Centerline RF Level": "%", "Centerline SDM": "%", "Ident Mod Percent": "%", "Centerline DDM": " DDM", "Width DDM": " DDM"}
    else: # GP
        keys = ["Path RF Level", "Path DDM", "Path SDM", "Width DDM"]
        suffix_unit = {"Path RF Level": "%", "Path SDM": "%", "Path DDM": " DDM", "Width DDM": " DDM"}
        
    for k in keys:
        if k in data["Course"]:
            vals = data["Course"][k]
            unit = suffix_unit.get(k, "")
            # Bersihkan value biar gak double unit
            m1, m2 = vals[0], vals[1]
            if unit and unit.strip() not in m1: m1 += unit
            if unit and unit.strip() not in m2: m2 += unit
            
            rows.append({"Parameter": k, "Monitor 1": m1, "Monitor 2": m2, "Type": "Data"})

    # 2. CLEARANCE
    rows.append({"Parameter": "CLEARANCE", "Monitor 1": "", "Monitor 2": "", "Type": "Header"})
    
    if tool_type == "LOCALIZER":
        keys_clr = ["RF Level", "Clearance 1 DDM", "SDM", "Ident Mod Percent", "Clearance 2 DDM", "Ident Status"]
        suffix_unit_clr = {"RF Level": "%", "SDM": "%", "Ident Mod Percent": "%", "Clearance 1 DDM": " DDM", "Clearance 2 DDM": " DDM"}
    else: # GP
        keys_clr = ["RF Level", "150Hz Mod Percent"]
        suffix_unit_clr = {"RF Level": "%", "150Hz Mod Percent": "%"}
        
    for k in keys_clr:
        if k in data["Clearance"]:
            vals = data["Clearance"][k]
            unit = suffix_unit_clr.get(k, "")
            m1, m2 = vals[0], vals[1]
            if unit and unit.strip() not in m1: m1 += unit
            if unit and unit.strip() not in m2: m2 += unit
            rows.append({"Parameter": k, "Monitor 1": m1, "Monitor 2": m2, "Type": "Data"})

    # 3. GENERAL (Separator & Other)
    rows.append({"Parameter": "", "Monitor 1": "", "Monitor 2": "", "Type": "Separator"})
    
    # RF Freq Diff
    if data["RF Freq Difference"][0]:
        rows.append({"Parameter": "RF Freq Difference", "Monitor 1": data["RF Freq Difference"][0] + " Hz", "Monitor 2": data["RF Freq Difference"][1] + " Hz", "Type": "Data"})
        
    # Antenna Fault (LOC Only)
    if tool_type == "LOCALIZER" and data["Antenna Fault"][0]:
         rows.append({"Parameter": "Antenna Fault", "Monitor 1": data["Antenna Fault"][0], "Monitor 2": data["Antenna Fault"][1], "Type": "Data"})

    return rows

# --- RENDER TABLE (UNIFIED DESIGN) ---
def render_table(rows):
    if not rows:
        st.warning("Data kosong atau format tidak dikenali.")
        return

    # CSS untuk tabel cantik full width
    st.markdown("""
        <style>
        .custom-table {
            width: 100%;
            border-collapse: collapse;
            font-family: sans-serif;
            color: #E0E0E0;
        }
        .custom-table th {
            background-color: #2E2E2E;
            color: #FFD700;
            padding: 10px;
            border: 1px solid #444;
            text-align: center;
            font-weight: bold;
        }
        .custom-table td {
            padding: 8px 12px;
            border: 1px solid #444;
        }
        .header-row td {
            background-color: #444;
            color: white;
            font-weight: bold;
            text-align: left;
            padding-left: 20px;
        }
        .separator-row td {
            background-color: transparent;
            border: none;
            height: 20px;
        }
        .data-row:nth-child(even) {
            background-color: #1E1E1E;
        }
        .data-row:nth-child(odd) {
            background-color: #262626;
        }
        </style>
    """, unsafe_allow_html=True)

    html = '<table class="custom-table">'
    html += '<thead><tr><th style="width:40%">PARAMETER</th><th style="width:30%">MONITOR 1</th><th style="width:30%">MONITOR 2</th></tr></thead>'
    html += '<tbody>'

    for row in rows:
        p = row['Parameter']
        m1 = row['Monitor 1']
        m2 = row['Monitor 2']
        rtype = row.get('Type', 'Data')

        if rtype == 'Header':
            html += f'<tr class="header-row"><td colspan="3">{p}</td></tr>'
        elif rtype == 'Separator':
            html += '<tr class="separator-row"><td colspan="3"></td></tr>'
        else:
            html += f'<tr class="data-row"><td>{p}</td><td style="text-align:center">{m1}</td><td style="text-align:center">{m2}</td></tr>'

    html += '</tbody></table>'
    st.markdown(html, unsafe_allow_html=True)

# --- HELPER LAIN ---
@st.cache_data
def get_img_as_base64(file_path):
    if not os.path.exists(file_path): return ""
    with open(file_path, "rb") as f: data = f.read()
    return base64.b64encode(data).decode()

header_bg = get_img_as_base64("background_lite.jpg") or get_img_as_base64("background.png")
logo_img = get_img_as_base64("logo.png")

def get_tools():
    tools = []
    for cat in ["MARU", "PMDT"]:
        p = os.path.join(config.OUTPUT_DIR, cat)
        if os.path.exists(p): tools.extend([d for d in os.listdir(p) if os.path.isdir(os.path.join(p, d))])
    return sorted(list(set(tools))) if tools else ["No Data"]

def find_raw(tool, date):
    dstr = date.strftime("%Y%m%d")
    for cat in ["MARU", "PMDT"]:
        ct = tool.replace("/", "_").replace("\\", "_")
        p = os.path.join(config.OUTPUT_DIR, cat, ct)
        if os.path.exists(p):
            fs = [f for f in os.listdir(p) if f.endswith(".txt") and dstr in f]
            if fs: return os.path.join(p, sorted(fs)[-1])
    return None

def find_evidence(tool, date):
    dstr = date.strftime("%Y%m%d")
    res = []
    for cat in ["MARU", "PMDT"]:
        ct = tool.replace("/", "_").replace("\\", "_")
        p = os.path.join(config.OUTPUT_DIR, cat, ct)
        if os.path.exists(p):
            # Ambil full path untuk semua file yang cocok
            candidates = [os.path.join(p, f) for f in os.listdir(p) if dstr in f and f.endswith(('.png','.jpg','.pdf'))]
            res.extend(candidates)
            
    # --- LOGIC SORTING (TERBARU DIATAS) ---
    # Menggunakan waktu modifikasi file (getmtime)
    # reverse=True artinya dari Besar ke Kecil (Waktu besar = Lebih baru)
    if res:
        res.sort(key=os.path.getmtime, reverse=True)
        
    return res

def load_live_db():
    try:
        if not os.path.exists(DB_PATH): return pd.DataFrame()
        c = sqlite3.connect(DB_PATH)
        c.execute("PRAGMA journal_mode=WAL;")
        df = pd.read_sql_query("SELECT station_name as station, MAX(timestamp) as timestamp FROM sessions GROUP BY station_name", c)
        c.close()
        if not df.empty: df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    except: return pd.DataFrame()

def run_robot(script, args):
    subprocess.Popen([sys.executable, LAUNCHER_SCRIPT, os.path.join(BASE_DIR, script)] + args)
    st.toast("🚀 Robot Start...", icon="⏳"); time.sleep(2); st.rerun()

# --- MAIN UI ---
st.markdown(f"""
    <style>
        /* FIX SIDEBAR ICON VISIBILITY */
        header[data-testid="stHeader"] {{ z-index: 1; }}
        footer {{visibility: hidden;}}
        .block-container {{ padding-top: 2rem; }}
        
        .visual-header {{
            background-image: url("data:image/jpg;base64,{header_bg}");
            background-repeat: repeat-x; background-size: auto 100%;
            background-position: center top; height: 280px; width: 100%;
            display: flex; flex-direction: row; justify-content: center;
            align-items: center; gap: 30px;
            box-shadow: inset 0 0 0 2000px rgba(10, 10, 15, 0.85); 
            margin-bottom: 30px; border-bottom: 6px solid #FFD700;
        }}
        .header-logo {{ height: 180px; width: auto; object-fit: contain; }}
        .text-container {{ display: flex; flex-direction: column; text-align: left; }}
        .batik-title-text {{ font-size: 2.8rem; color: #FFFFFF; font-weight: 700; margin: 0; }}
        .airnav-sub {{ font-family: 'Times New Roman', serif; font-size: 2.2rem; color: #FFD700; margin-top: 5px; }}
        section[data-testid="stSidebar"] {{ background-color: #1a1a1a; border-right: 1px solid #333; }}
        .stButton button {{ background-color: #007bff; color: white; }}
    </style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.image("logo.png", use_container_width=True)
    menu = st.radio("Menu", ["Meter Reading", "Data Meter Reading"], label_visibility="collapsed")

st.markdown(f"""
    <div class="visual-header">
        <img src="data:image/png;base64,{logo_img}" class="header-logo">
        <div class="text-container">
            <div class="batik-title-text">Buku Catatan Elektronik</div>
            <div class="airnav-sub">AirNav Solo</div>
        </div>
    </div>
""", unsafe_allow_html=True)

if menu == "Meter Reading":
    df_live = load_live_db()
    st.subheader("ILS (PMDT)")
    c1, c2, c3, c4 = st.columns(4)
    for i, (name, code) in enumerate([("Localizer", "LOC"), ("Glidepath", "GP"), ("Middle Marker", "MM"), ("Outer Marker", "OM")]):
        ts, status = "-", "🔴 BELUM UPDATE"
        if not df_live.empty:
            row = df_live[df_live['station'].str.contains(code, case=False)]
            if not row.empty:
                t = row.iloc[0]['timestamp']
                ts = t.strftime("%H:%M")
                if t.date() == datetime.now().date(): status = "🟢 UPDATED"
        with [c1, c2, c3, c4][i]:
            st.metric(name, status, f"Last: {ts}")
            if st.button(f"Read {name}", use_container_width=True): run_robot("bin/robot_pmdt.py", ["--target", code])

    st.markdown("---")
    st.subheader("DVOR/DME (MARU)")
    c1, c2 = st.columns(2)
    for i, (name, arg) in enumerate([("DVOR", "--DVOR"), ("DME", "--DME")]):
        ts, status = "-", "🔴 BELUM UPDATE"
        if not df_live.empty:
            row = df_live[df_live['station'].str.contains(name, case=False)]
            if not row.empty:
                t = row.iloc[0]['timestamp']
                ts = t.strftime("%H:%M")
                if t.date() == datetime.now().date(): status = "🟢 UPDATED"
        with [c1, c2][i]:
            st.metric(name, status, f"Last: {ts}")
            if st.button(f"Read {name}", use_container_width=True): run_robot("bin/robot_maru.py", [arg])

    st.markdown("---")
    if st.button("RUN ALL METER READING", use_container_width=True): run_robot("bin/run_all.py", [])

elif menu == "Data Meter Reading":
    st.markdown("### 📂 Laporan & Data")
    c1, c2, c3 = st.columns(3)
    with c1: s_date = st.date_input("Tanggal", datetime.today())
    with c2: s_tool = st.selectbox("Peralatan", get_tools())
    with c3: st.write("")
    
    st.markdown("---")
    
    if s_tool != "No Data":
        raw_file = find_raw(s_tool, s_date)
        if raw_file:
            content = ""
            try: 
                with open(raw_file, "r", encoding="utf-8", errors="replace") as f: content = f.read()
            except:
                with open(raw_file, "r", encoding="latin-1", errors="replace") as f: content = f.read()
            
            st.success(f"Data: {os.path.basename(raw_file)}")
            tool_up = s_tool.upper()
            rows_data = []
            
            # ROUTING PARSER BERDASARKAN JENIS ALAT
            if "LOC" in tool_up or "GLIDE" in tool_up or "GP" in tool_up:
                tool_type = "LOCALIZER" if "LOC" in tool_up else "GLIDEPATH"
                rows_data = parse_pmdt_loc_gp(tool_type, content)
            elif "MARKER" in tool_up or "MM" in tool_up or "OM" in tool_up:
                rows_data = parse_pmdt_mm_om(content)
            else:
                # MARU (DME / DVOR)
                rows_data = parse_maru_data(s_tool, content)
            
            if rows_data:
                render_table(rows_data)
                
                # CSV Export (Clean Data Only)
                clean_rows = [r for r in rows_data if r.get('Type') == 'Data']
                
                # --- FIX: Cek apakah clean_rows ada isinya sebelum buat DataFrame ---
                if clean_rows:
                    try:
                        df_exp = pd.DataFrame(clean_rows)
                        # Pastikan kolom ada sebelum filter
                        if set(["Parameter", "Monitor 1", "Monitor 2"]).issubset(df_exp.columns):
                            df_final = df_exp[["Parameter", "Monitor 1", "Monitor 2"]]
                            st.download_button("Download CSV", df_final.to_csv(index=False).encode(), f"Laporan_{s_tool}_{s_date}.csv", "text/csv")
                        else:
                            st.warning("Struktur data tidak lengkap untuk CSV.")
                    except Exception as e:
                        st.error(f"Gagal membuat CSV: {e}")
                else:
                    st.warning("Tidak ada data numerik yang terdeteksi untuk diunduh (Hanya Header).")
            else:
                st.error("Format data tidak dikenali atau kosong.")
        else:
            st.warning("Data Raw tidak ditemukan.")
            
        st.markdown("#### Bukti Evidence")
        # ... (sisanya sama) ...
        evs = find_evidence(s_tool, s_date)
        if evs:
            for e in evs:
                if e.endswith(".pdf"):
                    with open(e,"rb") as f: b64 = base64.b64encode(f.read()).decode()
                    st.markdown(f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="600"></iframe>', unsafe_allow_html=True)
                else:
                    st.image(e)
        else:
            st.info("Evidence belum tersedia.")