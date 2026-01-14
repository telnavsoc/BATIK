# FILE: dashboard.py
# ================================================================
# BATIK SOLO DASHBOARD V20 (PDF READER FOR DVOR TX LOGIC)
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
import sheet_handler 
import batik_parser 

st.set_page_config(
    page_title="BATIK SOLO",
    page_icon="📒",
    layout="wide",
    initial_sidebar_state="expanded" 
)

LAUNCHER_SCRIPT = os.path.join(BASE_DIR, "bin", "run_with_curtain.py")
DB_PATH = config.DB_PATH

# --- HELPER: BACA PDF SECARA BINARY (UNTUK MENCARI TX) ---
def extract_tx_from_pdf_binary(pdf_path):
    """
    Membaca file PDF secara binary raw untuk mencari string 'Active TX' 
    dan menentukan apakah TX1 atau TX2 yang muncul setelahnya.
    """
    try:
        with open(pdf_path, "rb") as f:
            content = f.read()
            # PDF Maru biasanya menyimpan teks sebagai stream. 
            # Kita cari byte pattern "Active TX"
            # Pattern di PDF biasanya: (Active TX) ... (TX1)
            
            # 1. Cari posisi "Active TX"
            idx = content.find(b"Active TX")
            if idx != -1:
                # Ambil potongan data 500 byte setelah kata Active TX
                chunk = content[idx:idx+500]
                
                # Cari indikator TX1 atau TX2 di potongan tersebut
                if b"TX2" in chunk: return 2
                if b"TX1" in chunk: return 1
    except:
        pass
    return None # Gagal baca atau tidak ketemu

# --- FUNGSI EMBED GOOGLE SHEET ---
def embed_google_sheet(sheet_id, gid):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit?gid={gid}&rm=minimal"
    st.markdown(f"""
        <div style="background-color:white; padding:5px; border-radius:10px; border:1px solid #ddd; margin-bottom: 20px;">
            <iframe src="{url}" width="100%" height="800px" frameborder="0"></iframe>
        </div>
    """, unsafe_allow_html=True)
    st.caption(f"🔗 [Klik untuk membuka di Tab Baru](https://docs.google.com/spreadsheets/d/{sheet_id}/edit?gid={gid})")

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

def find_evidence_pdf(tool, date):
    """Mencari file PDF Evidence"""
    dstr = date.strftime("%Y%m%d")
    for cat in ["MARU", "PMDT"]:
        ct = tool.replace("/", "_").replace("\\", "_")
        p = os.path.join(config.OUTPUT_DIR, cat, ct)
        if os.path.exists(p):
            fs = [f for f in os.listdir(p) if f.endswith(".pdf") and dstr in f]
            if fs: return os.path.join(p, sorted(fs)[-1])
    return None

def find_evidence(tool, date):
    dstr = date.strftime("%Y%m%d")
    res = []
    for cat in ["MARU", "PMDT"]:
        ct = tool.replace("/", "_").replace("\\", "_")
        p = os.path.join(config.OUTPUT_DIR, cat, ct)
        if os.path.exists(p):
            candidates = [os.path.join(p, f) for f in os.listdir(p) if dstr in f and f.endswith(('.png','.jpg','.pdf'))]
            res.extend(candidates)
    if res: res.sort(key=os.path.getmtime, reverse=True)
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
    st.markdown("### 📂 Digital Logbook Viewer")
    c1, c2, c3 = st.columns(3)
    with c1: s_date = st.date_input("Pilih Bulan", datetime.today())
    with c2: s_tool = st.selectbox("Peralatan", get_tools())
    with c3: 
        st.write("")
        force_sync = st.button("🔄 Force Re-Sync Data", use_container_width=True)
    
    st.markdown("---")
    
    # 1. LOGIKA SYNC MANUAL
    if force_sync and s_tool != "No Data":
        raw_file = find_raw(s_tool, s_date)
        if raw_file:
            with st.spinner("Membaca Raw Data & Upload Manual..."):
                content = ""
                try: 
                    with open(raw_file, "r", encoding="utf-8", errors="replace") as f: content = f.read()
                except:
                    with open(raw_file, "r", encoding="latin-1", errors="replace") as f: content = f.read()
                
                # === [LOGIKA KHUSUS DVOR: BACA PDF] ===
                if "DVOR" in s_tool.upper():
                    pdf_file = find_evidence_pdf(s_tool, s_date)
                    if pdf_file:
                        pdf_tx = extract_tx_from_pdf_binary(pdf_file)
                        if pdf_tx:
                            # Injeksi Marker ke Content agar dibaca Parser
                            content += f"\n\n# [PDF_EVIDENCE] Active TX: TX{pdf_tx}"
                            st.toast(f"DVOR: Terdeteksi TX {pdf_tx} Active (via PDF)", icon="📡")
                # ======================================

                # Proses Parsing
                tool_up = s_tool.upper()
                rows_data = []
                active_tx = 1
                
                if "LOC" in tool_up or "GLIDE" in tool_up or "GP" in tool_up:
                    t_type = "LOCALIZER" if "LOC" in tool_up else "GLIDEPATH"
                    rows_data, active_tx = batik_parser.parse_pmdt_loc_gp(t_type, content)
                elif "MARKER" in tool_up or "MM" in tool_up or "OM" in tool_up:
                    rows_data, active_tx = batik_parser.parse_pmdt_mm_om(content)
                else:
                    rows_data, active_tx = batik_parser.parse_maru_data(s_tool, content)
                
                # Upload
                if rows_data:
                    sid, gid, err = sheet_handler.upload_data_to_sheet(s_tool, rows_data, s_date, active_tx)
                    if err: st.error(f"Upload Gagal: {err}")
                    else: st.success("Data berhasil disinkronkan manual!")
                else:
                    st.warning("Tidak ada data valid ditemukan di file raw.")
        else:
            st.error("File Raw tidak ditemukan.")

    # 2. VIEWER GOOGLE SHEET
    if s_tool != "No Data":
        try:
            sh, err = sheet_handler.connect_gsheet()
            if not err:
                ws, err_ws = sheet_handler.get_or_create_monthly_sheet(sh, s_tool, s_date)
                if ws:
                    sheet_handler.update_period_label(ws, s_date)
                    embed_google_sheet(sh.id, ws.id)
                else: st.info("Sheet belum dibuat (Data kosong).")
            else: st.error("Gagal koneksi ke Google Sheet.")
        except Exception as e: st.error(f"Viewer Error: {e}")

        st.markdown("#### 📸 Bukti Evidence (Lokal)")
        evs = find_evidence(s_tool, s_date)
        if evs:
            for e in evs:
                if e.endswith(".pdf"):
                    with open(e,"rb") as f: b64 = base64.b64encode(f.read()).decode()
                    st.markdown(f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="600"></iframe>', unsafe_allow_html=True)
                else: st.image(e)
        else: st.info("Evidence belum tersedia.")