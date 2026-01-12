# FILE: dashboard.py
# ================================================================
# BATIK SOLO DASHBOARD V9 (FILE BASED + EVIDENCE VIEWER)
# ================================================================

import streamlit as st
import pandas as pd
import os
import sys
import subprocess
import time
import base64
from datetime import datetime, timedelta
import glob

# --- 1. KONFIGURASI PAGE ---
st.set_page_config(
    page_title="BATIK SOLO",
    page_icon="📒",
    layout="wide",
    initial_sidebar_state="expanded" 
)

# --- 2. SETUP PATH ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_LIVE_PATH = os.path.join(BASE_DIR, "output", "monitor_live.csv")
TEMP_RAW_DIR = os.path.join(BASE_DIR, "output", "temp_raw")
EVIDENCE_DIR = os.path.join(BASE_DIR, "output", "evidence_log")
LAUNCHER_SCRIPT = os.path.join(BASE_DIR, "bin", "run_with_curtain.py")

# --- 3. FUNGSI HELPER ---
@st.cache_data
def get_img_as_base64(file_path):
    if not os.path.exists(file_path): return ""
    with open(file_path, "rb") as f: data = f.read()
    return base64.b64encode(data).decode()

header_bg = get_img_as_base64("background_lite.jpg")
if not header_bg: header_bg = get_img_as_base64("background.png")
logo_img = get_img_as_base64("logo.png")

def load_live_data():
    try:
        if not os.path.exists(CSV_LIVE_PATH): return pd.DataFrame()
        df = pd.read_csv(CSV_LIVE_PATH, encoding='utf-8', encoding_errors='replace')
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            df = df.dropna(subset=['timestamp'])
        return df
    except: return pd.DataFrame()

def get_equipment_from_files():
    """Scan folder temp_raw untuk mendapatkan list alat yang tersedia"""
    if not os.path.exists(TEMP_RAW_DIR): return ["Tidak Ada Data"]
    # Cari file berakhiran _temp.txt
    files = glob.glob(os.path.join(TEMP_RAW_DIR, "*_temp.txt"))
    equip_names = []
    for f in files:
        # Ambil nama file saja, buang path dan akhiran _temp.txt
        fname = os.path.basename(f).replace("_temp.txt", "")
        equip_names.append(fname)
    
    return sorted(list(set(equip_names))) if equip_names else ["Tidak Ada Data"]

def read_temp_raw_file(equip_name):
    """Membaca file txt dari temp_raw dan mengubahnya jadi DataFrame"""
    file_path = os.path.join(TEMP_RAW_DIR, f"{equip_name}_temp.txt")
    if not os.path.exists(file_path): return None
    
    try:
        # Coba baca sebagai key-value (Parameter : Nilai) atau CSV sederhana
        # Asumsi format raw text biasa, kita baca per baris
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        data = []
        for line in lines:
            parts = line.strip().split(":", 1)
            if len(parts) == 2:
                data.append({"Parameter": parts[0].strip(), "Nilai Terbaca": parts[1].strip()})
            else:
                if line.strip(): # Jika baris tidak kosong tapi tidak ada titik dua
                    data.append({"Parameter": "Info", "Nilai Terbaca": line.strip()})
        
        if not data: return pd.DataFrame(["File Kosong"], columns=["Info"])
        return pd.DataFrame(data)
    except Exception as e:
        return pd.DataFrame([f"Error membaca file: {e}"], columns=["Error"])

def find_evidence_files(equip_name, selected_date):
    """Mencari file evidence berdasarkan nama alat dan tanggal (YYYYMMDD)"""
    if not os.path.exists(EVIDENCE_DIR): return []
    
    date_str = selected_date.strftime("%Y%m%d") # Format tanggal di nama file: 20260111
    found_files = []
    
    # Evidence ada di folder: output/evidence_log/STATION/EQUIPMENT/File
    # Kita crawl semua folder di dalam evidence_log
    for root, dirs, files in os.walk(EVIDENCE_DIR):
        # Cek apakah folder ini adalah folder peralatan yang dipilih (case insensitive)
        if os.path.basename(root).lower() == equip_name.lower():
            for file in files:
                # Cek apakah nama file mengandung tanggal yang dipilih
                if date_str in file:
                    found_files.append(os.path.join(root, file))
    
    return found_files

def run_robot(script_path, args_list, is_run_all=False):
    full_path = os.path.join(BASE_DIR, script_path)
    cmd = [sys.executable, LAUNCHER_SCRIPT, full_path] + args_list
    subprocess.Popen(cmd)
    st.toast("🚀 Robot Berjalan...", icon="⏳")
    time.sleep(2)
    st.rerun()

def get_status_by_schedule(last_ts):
    if pd.isna(last_ts): return "🔴", "BELUM UPDATE", "inverse"
    if last_ts.date() == datetime.now().date(): return "🟢", "UPDATED", "normal"
    return "🔴", "BELUM UPDATE", "inverse"

# --- 4. CSS CUSTOM (FIXED) ---
st.markdown(f"""
    <style>
        /* HIDE FOOTER & HEADER DECORATION */
        footer {{visibility: hidden;}}
        .block-container {{ padding-top: 2rem; padding-bottom: 2rem; }}

        /* HIDE FULLSCREEN BUTTON ON IMAGES (LOGO) */
        button[title="View fullscreen"] {{
            visibility: hidden !important;
            display: none !important;
        }}

        /* SIDEBAR STYLE */
        section[data-testid="stSidebar"] {{ background-color: #1a1a1a; border-right: 1px solid #333; }}
        .stRadio label {{ color: #e0e0e0; padding: 10px; border-radius: 5px; cursor: pointer; transition: 0.3s; }}
        .stRadio label:hover {{ background-color: #333; color: #FFD700; border-left: 3px solid #FFD700; }}
        .stRadio div[role="radiogroup"] > label[data-baseweb="radio"] > div:first-child {{ background-color: #FFD700 !important; }}

        /* HEADER STYLE */
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
        
        /* TOMBOL LIHAT */
        .stButton button {{ background-color: #007bff; color: white; border-radius: 5px; }}
        .stButton button:hover {{ background-color: #0056b3; border-color: white; }}
    </style>
""", unsafe_allow_html=True)

# --- 5. SIDEBAR MENU ---
with st.sidebar:
    st.image("logo.png", use_container_width=True)
    st.markdown("<div style='text-align: center; color: #888; margin-bottom: 20px;'>Navigation Menu</div>", unsafe_allow_html=True)
    selected_menu = st.radio("Pilih Menu:", ["Meter Reading", "Data Meter Reading"], label_visibility="collapsed")
    st.markdown("---")
    st.caption("© 2026 TelNavSoc Automation")

# --- 6. HEADER UTAMA ---
logo_html = f'<img src="data:image/png;base64,{logo_img}" class="header-logo">' if logo_img else ''
st.markdown(f'<div class="visual-header">{logo_html}<div class="text-container"><div class="batik-title-text">Buku Catatan Elektronik</div><div class="airnav-sub">AirNav Solo</div></div></div>', unsafe_allow_html=True)

# ================= HALAMAN 1: MONITORING LIVE =================
if selected_menu == "Meter Reading":
    df = load_live_data()
    # Definisi Grup Alat
    groups = {
        "ILS": {
            "Localizer": ("bin/robot_pmdt.py", ["--target", "LOC"], ["LOCALIZER", "LOC"]),
            "GP": ("bin/robot_pmdt.py", ["--target", "GP"], ["GLIDE", "GP"]),
            "MM": ("bin/robot_pmdt.py", ["--target", "MM"], ["MIDDLE", "MM"]),
            "OM": ("bin/robot_pmdt.py", ["--target", "OM"], ["OUTER", "OM"]),
        },
        "DVOR/DME": {
            "DVOR": ("bin/robot_maru.py", ["--DVOR"], ["DVOR", "220"]),
            "DME": ("bin/robot_maru.py", ["--DME"], ["DME", "320"]),
        }
    }

    for group_name, tools in groups.items():
        st.markdown(f"<h3 style='color:#81C784; border-bottom:2px solid #333;'>{group_name}</h3>", unsafe_allow_html=True)
        cols = st.columns(len(tools))
        for idx, (tool_name, (script, args, keywords)) in enumerate(tools.items()):
            last_ts, last_update_str = pd.NaT, "-"
            if not df.empty and 'station' in df.columns:
                mask = df['station'].str.upper().apply(lambda x: any(k in str(x) for k in keywords))
                tool_df = df[mask]
                if not tool_df.empty:
                    last_ts = tool_df['timestamp'].max()
                    last_update_str = last_ts.strftime("%H:%M")
            
            icon, status, color = get_status_by_schedule(last_ts)
            with cols[idx]:
                st.metric(label=tool_name, value=f"{icon} {status}", delta=f"Last: {last_update_str}", delta_color=color)
                if st.button(f"Meter Reading {tool_name}", key=f"btn_{tool_name}", use_container_width=True):
                    run_robot(script, args)

    st.markdown("---")
    col_l, col_m, col_r = st.columns([1, 2, 1])
    with col_m:
        if st.button("RUN ALL METER READING", use_container_width=True):
            run_robot("bin/run_all.py", [], is_run_all=True)

# ================= HALAMAN 2: DATA METER READING =================
elif selected_menu == "Data Meter Reading":
    st.markdown("<h2 style='color: white;'>📂 Data Meter Reading</h2>", unsafe_allow_html=True)
    st.write("Lihat hasil pembacaan mentah (Raw Data) dan bukti foto (Evidence).")
    
    # --- FILTER (TANPA EXPANDER) ---
    st.markdown("#### 🔍 Filter Pencarian")
    
    c1, c2, c3 = st.columns([1, 1, 1])
    
    with c1:
        # Pilih Tanggal (Untuk mencari evidence)
        selected_date = st.date_input("Pilih Tanggal", value=datetime.today())
    
    with c2:
        # Pilih Alat (Dari file temp_raw yang ada)
        available_equips = get_equipment_from_files()
        selected_equip = st.selectbox("Pilih Peralatan", available_equips)
        
    with c3:
        st.write("") # Spacer agar tombol sejajar dengan input
        st.write("") 
        # Tombol Lihat
        tombol_lihat = st.button("👁️ Lihat Data", use_container_width=True)

    st.markdown("---")

    # --- TAMPILAN DATA (Hanya muncul jika tombol ditekan) ---
    if tombol_lihat:
        if selected_equip == "Tidak Ada Data":
            st.error("Tidak ada data tersimpan di folder output/temp_raw.")
        else:
            # 1. TAMPILKAN TABEL RAW DATA
            st.subheader(f"📄 Data Pembacaan: {selected_equip}")
            
            df_raw = read_temp_raw_file(selected_equip)
            
            if df_raw is not None:
                st.dataframe(df_raw, use_container_width=True, hide_index=True)
                
                # Tombol Download Tabel
                csv = df_raw.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="🖨️ Download / Print Tabel (CSV)",
                    data=csv,
                    file_name=f"Data_{selected_equip}_{selected_date}.csv",
                    mime='text/csv'
                )
            else:
                st.warning(f"File data raw untuk {selected_equip} tidak ditemukan.")

            st.markdown("---")

            # 2. TAMPILKAN EVIDENCE
            st.subheader(f"📷 Evidence (Bukti Foto/PDF)")
            
            evidence_files = find_evidence_files(selected_equip, selected_date)
            
            if evidence_files:
                for ev_file in evidence_files:
                    fname = os.path.basename(ev_file)
                    st.markdown(f"**File:** `{fname}`")
                    
                    # Cek tipe file
                    if ev_file.lower().endswith(('.png', '.jpg', '.jpeg')):
                        st.image(ev_file, caption=fname, use_container_width=True)
                    elif ev_file.lower().endswith('.pdf'):
                        # Tampilkan PDF (Embed atau Link)
                        with open(ev_file, "rb") as pdf_file:
                            base64_pdf = base64.b64encode(pdf_file.read()).decode('utf-8')
                        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="500px"></iframe>'
                        st.markdown(pdf_display, unsafe_allow_html=True)
                    
                    # Tombol Download Evidence
                    with open(ev_file, "rb") as file_data:
                        st.download_button(
                            label=f"🖨️ Download Evidence ({fname})",
                            data=file_data,
                            file_name=fname,
                            mime="application/octet-stream"
                        )
                    st.write("") # Spacer antar file
            else:
                st.info(f"Tidak ditemukan evidence untuk {selected_equip} pada tanggal {selected_date.strftime('%d-%m-%Y')}.")

st.write("")
st.caption("BATIK System v9 | Developed for AirNav Solo")