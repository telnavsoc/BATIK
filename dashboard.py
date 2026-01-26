# FILE: dashboard.py
# ================================================================
# BATIK SOLO DASHBOARD - SMART CACHE VERSIONING
# FITUR: INDIVIDUAL REFRESH, CUSTOM PAPER SIZE, CLEAN UI
# ================================================================

import streamlit as st
import pandas as pd
import os
import sys
import subprocess
import time
import base64
import gspread 
import requests 
from datetime import datetime

from google.oauth2.service_account import Credentials
import google.auth.transport.requests

# --- CONFIG & PATHS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BIN_DIR = os.path.join(BASE_DIR, "bin")
sys.path.append(BIN_DIR)

import config 
import sheet_handler 
import batik_parser 

# --- SETUP ---
CREDENTIALS_FILE = os.path.join(BASE_DIR, 'credentials.json')
MASTER_SPREADSHEET_NAME = "LOGBOOK_BATIK"

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# --- STATE MANAGEMENT (UNTUK REFRESH PER ALAT) ---
# Kita simpan versi cache untuk masing-masing alat
if "cache_versions" not in st.session_state:
    st.session_state.cache_versions = {
        "LOC": 0, "GP": 0, "MM": 0, "OM": 0, "DVOR": 0, "DME": 0
    }

# --- KONEKSI CACHED ---
@st.cache_resource
def get_gspread_client():
    if not os.path.exists(CREDENTIALS_FILE):
        return None, None
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    gc = gspread.authorize(creds)
    return gc, creds

def set_sheet_visibility(sh, sheet_id, visible=True):
    body = {
        "requests": [{"updateSheetProperties": {
            "properties": {"sheetId": sheet_id, "hidden": not visible},
            "fields": "hidden"
        }}]
    }
    try:
        sh.batch_update(body)
    except:
        pass

# --- FUNGSI PDF FETCH (SMART REFRESH) ---
# Kita tambahkan argumen 'cache_ver'. Meskipun tidak dipakai di logika,
# perubahan nilai argumen ini akan memaksa Streamlit mengabaikan cache lama.
@st.cache_data(ttl=300, show_spinner="Membaca Data Parameter...") 
def get_hidden_sheet_as_pdf(tool_code, cache_ver):
    try:
        gc, creds = get_gspread_client()
        if not gc: return None, "Koneksi Google Gagal (Cek Credentials)"
        
        try:
            sh = gc.open(MASTER_SPREADSHEET_NAME)
        except:
            return None, f"File Spreadsheet '{MASTER_SPREADSHEET_NAME}' Hilang"

        target_sheet_name = f"LAST_{tool_code}"
        try:
            ws = sh.worksheet(target_sheet_name)
        except:
            return None, f"Sheet '{target_sheet_name}' Tidak Ditemukan"

        if creds.expired:
            creds.refresh(google.auth.transport.requests.Request())
        
        # URL EXPORT (Scale 100%, Margin 0.15)
        url = (f"https://docs.google.com/spreadsheets/d/{sh.id}/export?"
               f"format=pdf&gid={ws.id}&"
               "size=A4&portrait=true&fitw=false&scale=4&gridlines=false&printtitle=false&sheetnames=false&fzr=false&"
               "top_margin=0.15&bottom_margin=0&left_margin=0.15&right_margin=0")
        
        headers = {'Authorization': f'Bearer {creds.token}'}
        
        set_sheet_visibility(sh, ws.id, visible=True)
        try:
            res = requests.get(url, headers=headers)
        finally:
            set_sheet_visibility(sh, ws.id, visible=False)
        
        if res.status_code != 200: return None, f"Gagal Download PDF (Error {res.status_code})"
        
        return base64.b64encode(res.content).decode('utf-8'), None
    except Exception as e:
        return None, f"System Error: {str(e)}"

st.set_page_config(
    page_title="BATIK SOLO",
    page_icon="📒",
    layout="wide",
    initial_sidebar_state="collapsed" 
)

LAUNCHER_SCRIPT = os.path.join(BIN_DIR, "run_with_curtain.py")

# --- CSS STYLING ---
st.markdown("""
    <style>
        .stApp { background-color: #000000; }
        .block-container { padding: 0 !important; max-width: 100% !important; }
        header { display: none; }

        .visual-header {
            background-repeat: repeat-x; background-size: auto 100%; background-position: center top; 
            height: 250px; width: 100vw; display: flex; flex-direction: row; justify-content: center; 
            align-items: center; gap: 30px; box-shadow: inset 0 0 0 2000px rgba(0, 0, 0, 0.2); 
            border-bottom: 4px solid #FFD700; margin-left: calc(-50vw + 50%); margin-right: calc(-50vw + 50%); margin-bottom: 40px;
        }

        div[data-testid="column"] { display: flex; flex-direction: column; align-items: center !important; }
        iframe, .stImage img { display: block !important; margin: 0 auto !important; }

        div[data-testid="stExpander"] {
            width: 768px !important; min-width: 768px !important; max-width: 768px !important; margin: 0 auto !important;
            background-color: #2D2D2D !important; border: 1px solid #333 !important; border-radius: 4px;
        }
        .streamlit-expanderHeader { background-color: #2D2D2D !important; color: white !important; font-weight: 600; }
        .streamlit-expanderContent { background-color: #000000 !important; color: white !important; border-top: 1px solid #333; }
        [data-testid="stExpander"] p { color: #ccc !important; }

        .tool-title { color: #ffffff; font-size: 1.4rem; font-weight: 700; margin-bottom: 5px; text-align: center; display: block; }
        
        /* Tombol Style */
        .stButton button { border-radius: 4px; font-weight: 600; height: 38px; }
        /* Tombol RUN (Primary Color) */
        div[data-testid="stVerticalBlock"] > div > div > div > div > div > button { 
             background-color: #007bff; color: white;
        }
        
        .header-logo { height: 160px; width: auto; object-fit: contain; }
        .text-container { display: flex; flex-direction: column; text-align: left; }
        .batik-title-text { font-size: 2.8rem; color: #FFFFFF; font-weight: 700; margin: 0; line-height: 1.2;}
        .airnav-sub { font-family: 'Times New Roman', serif; font-size: 2.2rem; color: #FFD700; margin-top: 5px; }
        section[data-testid="stSidebar"] { display: none; }
    </style>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
@st.cache_data
def get_img_as_base64(file_path):
    if not os.path.exists(file_path): return ""
    with open(file_path, "rb") as f: data = f.read()
    return base64.b64encode(data).decode()

def find_evidence_file(tool_code, date, extension_list):
    dstr = date.strftime("%Y%m%d")
    folder_mapping = {
        "LOC": "LOCALIZER", "GP": "GLIDE PATH", "MM": "MIDDLE MARKER", 
        "OM": "OUTER MARKER", "DVOR": "DVOR", "DME": "DME"
    }
    folder_name = folder_mapping.get(tool_code, tool_code)
    category = "PMDT" if tool_code in ["LOC", "GP", "MM", "OM"] else "MARU"
    possible_paths = []
    if category == "PMDT":
        possible_paths.append(os.path.join(config.OUTPUT_DIR, category, folder_name, "Monitor_Data"))
    else:
        possible_paths.append(os.path.join(config.OUTPUT_DIR, category, folder_name, "Transmitter_Data"))
    possible_paths.append(os.path.join(config.OUTPUT_DIR, category, folder_name))
    possible_paths.append(os.path.join(config.OUTPUT_DIR, category, tool_code))

    candidates = []
    for p in possible_paths:
        if os.path.exists(p):
            found = [os.path.join(p, f) for f in os.listdir(p) if dstr in f and f.lower().endswith(extension_list)]
            candidates.extend(found)
    if candidates: 
        candidates.sort(key=os.path.getmtime, reverse=True)
        return candidates[0]
    return None

# --- FUNGSI UPDATE VERSI CACHE (INCREMENT) ---
def trigger_refresh(tool_code):
    # Naikkan versi cache untuk alat ini saja
    # Ini akan memaksa fungsi get_hidden_sheet_as_pdf download ulang hanya untuk alat ini
    st.session_state.cache_versions[tool_code] += 1

def run_robot(script, args, tool_code):
    with st.spinner("Membaca Data Parameter..."):
        process = subprocess.run(
            [sys.executable, LAUNCHER_SCRIPT, os.path.join(BASE_DIR, script)] + args,
            capture_output=True, text=True
        )
    if process.returncode == 0:
        st.toast(f"✅ Data {tool_code} Terupdate!", icon="🔄")
        
        # UPDATE CACHE KHUSUS ALAT INI (Biar langsung fresh)
        trigger_refresh(tool_code)
        
        time.sleep(1)
        st.rerun()
    else:
        st.error(f"❌ Error:\n{process.stderr}")

# --- RENDER TOOL CARD ---
def render_tool_card(tool_name, tool_code, script, args, is_ils=True):
    
    # 1. KONFIGURASI TAMPILAN SESUAI REQUEST
    paper_size_config = {
        "LOC":  {"w": 530, "h": 560}, 
        "GP":   {"w": 530, "h": 400},
        "MM":   {"w": 530, "h": 210},
        "OM":   {"w": 530, "h": 210},
        "DVOR": {"w": 530, "h": 480},
        "DME":  {"w": 530, "h": 425}
    }
    cfg = paper_size_config.get(tool_code, {"w": 530, "h": 500})
    WINDOW_W_PX = f"{cfg['w']}px"
    WINDOW_H_PX = f"{cfg['h']}px"
    
    # SETUP ABSOLUTE POS (FIXED GREY BAR)
    INNER_IFRAME_W = "900px"
    PDF_X_OFFSET = "-52px" 
    
    # ALIGNMENT
    VIRTUAL_W = 854 
    HEADER_W = cfg['w']
    SPACER = (VIRTUAL_W - HEADER_W) / 2
    
    # --- FETCH DATA DENGAN VERSI CACHE UNIK ---
    # Kita ambil versi saat ini dari session state
    current_version = st.session_state.cache_versions[tool_code]
    pdf_b64, err_msg = get_hidden_sheet_as_pdf(tool_code, current_version)

    evidence_file = None
    if not is_ils: 
        evidence_file = find_evidence_file(tool_name, datetime.now(), ('.pdf'))
    else:
        evidence_file = find_evidence_file(tool_code, datetime.now(), ('.png', '.jpg', '.jpeg'))

    with st.container():
        # --- HEADER (CENTER) ---
        c_L, c_Center, c_R = st.columns([SPACER, HEADER_W, SPACER])
        with c_Center:
            st.markdown(f'<div class="tool-title">{tool_name}</div>', unsafe_allow_html=True)
            
            # TOMBOL RUN & REFRESH BERDAMPINGAN
            # Kita bagi kolom kecil: [Tombol Run] [Tombol Refresh]
            b_cols = st.columns([4, 1]) 
            
            with b_cols[0]: # Tombol RUN (Besar)
                if st.button(f"RUN {tool_code}", key=f"run_{tool_code}", use_container_width=True):
                    run_robot(script, args, tool_code) # Pass tool_code untuk auto-refresh
            
            with b_cols[1]: # Tombol REFRESH (Kecil)
                if st.button("🔄", key=f"refresh_{tool_code}", help="Refresh data alat ini saja"):
                    trigger_refresh(tool_code)
                    st.rerun()
        
        st.write("") 

        # --- PDF DISPLAY ---
        if pdf_b64:
            pdf_display = f"""
                <div style="width:{WINDOW_W_PX}; height:{WINDOW_H_PX}; overflow:hidden; border:none; margin: 0 auto 15px auto; position: relative;">
                    <iframe src="data:application/pdf;base64,{pdf_b64}#toolbar=0&navpanes=0&scrollbar=0&zoom=100" 
                            width="{INNER_IFRAME_W}" height="1200px" 
                            style="border:none; position: absolute; top: -2px; left: {PDF_X_OFFSET}; pointer-events:none;"
                            scrolling="no">
                    </iframe>
                </div>
            """
            st.markdown(pdf_display, unsafe_allow_html=True)
        else:
            if err_msg: st.warning(f"⚠️ {err_msg}")
            else: st.info("Loading Data...")

        # --- EVIDENCE DISPLAY (768px) ---
        with st.expander("📸 Lihat Evidence", expanded=False):
            if evidence_file:
                st.caption(f"File: {os.path.basename(evidence_file)}")
                if is_ils:
                    with open(evidence_file, "rb") as f: b64_img = base64.b64encode(f.read()).decode('utf-8')
                    st.markdown(f'<div style="width:100%; overflow:hidden; border-radius:4px; margin: 0 auto;"><img src="data:image/png;base64,{b64_img}" style="width:100%; display:block;"></div>', unsafe_allow_html=True)
                else:
                    with open(evidence_file, "rb") as f: b64_ev_pdf = base64.b64encode(f.read()).decode('utf-8')
                    st.markdown(f'<div style="width:100%; height:600px; overflow:hidden; border-radius:4px; margin: 0 auto;"><iframe src="data:application/pdf;base64,{b64_ev_pdf}#toolbar=0&navpanes=0&scrollbar=0&view=FitH" width="100%" height="100%" style="border:none;" scrolling="no"></iframe></div>', unsafe_allow_html=True)
            else:
                st.info("Belum ada evidence.")
        st.markdown("<br>", unsafe_allow_html=True)

# --- HEADER SECTION ---
header_bg = get_img_as_base64("background_lite.jpg") or get_img_as_base64("background.png")
logo_img = get_img_as_base64("logo.png")
st.markdown(f"""
    <div class="visual-header" style="background-image: url('data:image/jpg;base64,{header_bg}');">
        <img src="data:image/png;base64,{logo_img}" class="header-logo">
        <div class="text-container">
            <div class="batik-title-text">Buku Catatan Elektronik</div>
            <div class="airnav-sub">AirNav Solo</div>
        </div>
    </div>
""", unsafe_allow_html=True)

# --- MAIN LAYOUT ---
with st.container():
    c_run_all = st.columns([1, 2, 1]) 
    with c_run_all[1]:
        # Tombol ini tidak me-refresh cache spesifik (kecuali ditambah logika tambahan)
        # Saat ini hanya menjalankan robot back-to-back
        if st.button("🚀 RUN ALL METER READING", use_container_width=True): 
             # Untuk Run All, kita pakai script run_all.py
             # Jika ingin auto-refresh semua setelah run all, bisa ditambahkan trigger_refresh loop
             run_robot("bin/run_all.py", [], "ALL") 
    
    st.write("")
    
    st.markdown("### 📡 INSTRUMENT LANDING SYSTEM (ILS)")
    c1, c2 = st.columns(2)
    with c1: render_tool_card("Localizer", "LOC", "bin/robot_pmdt.py", ["--target", "LOC"], is_ils=True)
    with c2: render_tool_card("Glidepath", "GP", "bin/robot_pmdt.py", ["--target", "GP"], is_ils=True)
    
    c3, c4 = st.columns(2)
    with c3: render_tool_card("Middle Marker", "MM", "bin/robot_pmdt.py", ["--target", "MM"], is_ils=True)
    with c4: render_tool_card("Outer Marker", "OM", "bin/robot_pmdt.py", ["--target", "OM"], is_ils=True)
    
    st.markdown("### 📡 NAVIGASI UDARA (DVOR & DME)")
    c5, c6 = st.columns(2)
    with c5: render_tool_card("DVOR", "DVOR", "bin/robot_maru.py", ["--DVOR"], is_ils=False)
    with c6: render_tool_card("DME", "DME", "bin/robot_maru.py", ["--DME"], is_ils=False)
    
    st.markdown("<br><br>", unsafe_allow_html=True)