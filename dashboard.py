# FILE: dashboard.py
# ================================================================
# BATIK SOLO DASHBOARD V7.1 (HORIZONTAL LAYOUT & PRECISE BG)
# ================================================================

import streamlit as st
import pandas as pd
import os
import sys
import subprocess
from datetime import datetime, time as dt_time, timedelta
import time
import base64
from PIL import Image

# --- 1. KONFIGURASI PAGE ---
st.set_page_config(
    page_title="BATIK SOLO",
    page_icon="📒",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. FUNGSI HELPER GAMBAR ---
@st.cache_data
def get_img_as_base64(file_path):
    if not os.path.exists(file_path):
        return ""
    with open(file_path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()

# Load Gambar
header_bg = get_img_as_base64("background_lite.jpg")
if not header_bg:
    header_bg = get_img_as_base64("background.png")
    
logo_img = get_img_as_base64("logo.png")

# --- 3. CSS CUSTOM (LAYOUT BARU) ---
st.markdown(f"""
    <style>
        /* RESET */
        header[data-testid="stHeader"], footer {{visibility: hidden;}}
        .block-container {{
            padding-top: 0rem; 
            padding-bottom: 2rem;
        }}

        /* === CONTAINER HEADER === */
        .visual-header {{
            /* Background Settings */
            background-image: url("data:image/jpg;base64,{header_bg}");
            background-repeat: repeat-x;     /* Hanya ulang menyamping */
            background-size: auto 100%;      /* Tinggi fix, lebar menyesuaikan */
            background-position: center top;
            
            /* Dimensi */
            height: 280px; /* Tinggi fix agar pas 1 baris background */
            width: 100%;
            
            /* Layout Flexbox untuk Isi (Logo + Teks) */
            display: flex;
            flex-direction: row; /* Menyamping */
            justify-content: center; /* Di tengah secara horizontal */
            align-items: center;     /* Di tengah secara vertikal */
            gap: 30px;               /* Jarak antara Logo dan Teks */
            
            /* Overlay Gelap */
            box-shadow: inset 0 0 0 2000px rgba(10, 10, 15, 0.85); 
            
            margin-bottom: 30px;
            border-bottom: 6px solid #FFD700;
        }}

        /* LOGO */
        .header-logo {{
            height: 180px; /* Ukuran proporsional */
            width: auto;
            object-fit: contain;
            filter: drop-shadow(0 0 15px rgba(255,255,255,0.1));
        }}

        /* CONTAINER TEKS (Sebelah Kanan Logo) */
        .text-container {{
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: flex-start; /* Rata kiri terhadap container teks */
            text-align: left;
        }}

        /* TEKS 1: Buku Catatan Elektronik */
        .batik-title-text {{
            font-family: 'Segoe UI', sans-serif;
            font-size: 2.8rem; /* Lebih besar */
            color: #FFFFFF;
            font-weight: 700;
            margin: 0;
            line-height: 1.1;
            text-shadow: 2px 2px 5px rgba(0,0,0,1);
        }}

        /* TEKS 2: AirNav Solo */
        .airnav-sub {{
            font-family: 'Times New Roman', serif;
            font-size: 2.2rem;
            color: #FFD700; /* Emas */
            font-weight: 400;
            margin-top: 5px;
            letter-spacing: 2px;
            text-shadow: 1px 1px 3px rgba(0,0,0,0.8);
        }}

        /* === METRIC CARDS STYLE === */
        div[data-testid="stMetricLabel"] p {{
            font-size: 1.6rem !important;
            font-weight: 700 !important;
            color: #E0E0E0 !important;
        }}
        div[data-testid="stMetricValue"] div {{
            font-size: 1.1rem !important;
        }}
        div[data-testid="stMetric"] {{
            background-color: #1E1E1E;
            border: 1px solid #333;
            border-left: 5px solid #4CAF50;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            transition: transform 0.2s;
        }}
        div[data-testid="stMetric"]:hover {{
            transform: translateY(-2px);
            border-color: #555;
        }}
        
        .group-header {{
            color: #81C784;
            border-bottom: 2px solid #333;
            padding-bottom: 5px;
            margin-top: 30px;
            font-family: 'Segoe UI', sans-serif;
            font-weight: 900;
            font-size: 1.5rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}

        /* === BUTTONS === */
        .stButton button {{
            background-color: #B71C1C !important;
            color: white !important;
            font-weight: 600 !important;
            border: 1px solid #E53935 !important;
            border-radius: 6px;
        }}
        .stButton button:hover {{
            background-color: #D32F2F !important;
            border-color: #FFCDD2 !important;
        }}
        
        .footer-run-all button {{
            background: linear-gradient(45deg, #B71C1C, #D32F2F) !important;
            font-size: 1.4rem !important;
            height: 65px !important;
            border: none !important;
            box-shadow: 0 4px 15px rgba(211, 47, 47, 0.4);
        }}
    </style>
    
    <meta http-equiv="refresh" content="3600">
""", unsafe_allow_html=True)

# --- 4. SETUP LOGIC ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "output", "monitor_live.csv")
LAUNCHER_SCRIPT = os.path.join(BASE_DIR, "bin", "run_with_curtain.py")

def load_data():
    if not os.path.exists(CSV_PATH) or os.stat(CSV_PATH).st_size == 0:
        return pd.DataFrame(columns=['timestamp', 'station'])
    try:
        df = pd.read_csv(CSV_PATH, encoding='utf-8', encoding_errors='replace')
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            df = df.dropna(subset=['timestamp'])
        return df
    except Exception:
        return pd.DataFrame(columns=['timestamp', 'station'])

def run_robot(script_path, args_list, is_run_all=False):
    full_path = os.path.join(BASE_DIR, script_path)
    cmd = [sys.executable, LAUNCHER_SCRIPT, full_path] + args_list
    subprocess.Popen(cmd)
    
    msg = "🚀 Sequence Meter Reading Dimulai..." if is_run_all else f"🚀 Reading {args_list[0] if args_list else ''}..."
    st.toast(msg, icon="⏳")
    time.sleep(2)
    st.rerun()

def get_status_by_schedule(last_ts):
    if pd.isna(last_ts): return "🔴", "BELUM UPDATE", "inverse"
    
    now = datetime.now()
    today = now.date()
    data_date = last_ts.date()
    
    sched_morning = now.replace(hour=5, minute=30, second=0, microsecond=0)
    sched_afternoon = now.replace(hour=13, minute=0, second=0, microsecond=0)
    
    buffer = timedelta(minutes=15)
    
    status_icon, status_text, delta_color = "🔴", "BELUM UPDATE", "inverse"
    
    if data_date == today:
        if now > (sched_afternoon + buffer):
            if last_ts >= sched_afternoon: status_icon, status_text, delta_color = "🟢", "UPDATED", "normal"
        elif now > (sched_morning + buffer):
            if last_ts >= sched_morning: status_icon, status_text, delta_color = "🟢", "UPDATED", "normal"
        else:
             status_icon, status_text, delta_color = "🟢", "UPDATED", "normal"
             
    return status_icon, status_text, delta_color

# ================= LAYOUT UTAMA =================

# --- 1. HEADER VISUAL (LAYOUT BARU) ---
logo_html = f'<img src="data:image/png;base64,{logo_img}" class="header-logo">' if logo_img else ''

st.markdown(f"""
    <div class="visual-header">
        {logo_html}
        <div class="text-container">
            <div class="batik-title-text">Buku Catatan Elektronik</div>
            <div class="airnav-sub">AirNav Solo</div>
        </div>
    </div>
""", unsafe_allow_html=True)

# --- 2. DISPLAY ALAT ---
df = load_data()
groups = {
    "ILS": {
        "Localizer": ("bin/robot_pmdt.py", ["--target", "LOC"], ["LOCALIZER", "LOC"]),
        "GP":        ("bin/robot_pmdt.py", ["--target", "GP"],  ["GLIDE", "GP"]),
        "MM":        ("bin/robot_pmdt.py", ["--target", "MM"],  ["MIDDLE", "MM"]),
        "OM":        ("bin/robot_pmdt.py", ["--target", "OM"],  ["OUTER", "OM"]),
    },
    "DVOR/DME": {
        "DVOR":      ("bin/robot_maru.py", ["--DVOR"], ["DVOR", "220"]),
        "DME":       ("bin/robot_maru.py", ["--DME"],  ["DME", "320"]),
    }
}

for group_name, tools in groups.items():
    st.markdown(f"<div class='group-header'>{group_name}</div>", unsafe_allow_html=True)
    
    n_cols = len(tools)
    cols = st.columns(n_cols)
    
    for idx, (tool_name, (script, args, keywords)) in enumerate(tools.items()):
        col = cols[idx]
        
        last_ts = pd.NaT
        last_update_str = "-"
        if not df.empty:
            mask = df['station'].str.upper().apply(lambda x: any(k in x for k in keywords))
            tool_df = df[mask]
            if not tool_df.empty:
                last_ts = tool_df['timestamp'].max()
                last_update_str = last_ts.strftime("%H:%M")

        icon, status, color = get_status_by_schedule(last_ts)

        with col:
            st.metric(
                label=tool_name,
                value=f"{icon} {status}",
                delta=f"Last: {last_update_str}",
                delta_color=color
            )
            if st.button(f"Meter Reading {tool_name}", key=f"btn_{tool_name}", use_container_width=True):
                run_robot(script, args)

st.markdown("---")
st.write("")

# --- 3. FOOTER RUN ALL ---
col_l, col_m, col_r = st.columns([1, 2, 1])
with col_m:
    st.markdown('<div class="footer-run-all">', unsafe_allow_html=True)
    if st.button("RUN ALL METER READING", use_container_width=True):
        run_robot("bin/run_all.py", [], is_run_all=True)
    st.markdown('</div>', unsafe_allow_html=True)

st.write("")
st.caption("BATIK System v7.1 | Developed for AirNav Solo")