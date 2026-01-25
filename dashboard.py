# FILE: dashboard.py
# ================================================================
# BATIK SOLO DASHBOARD - CENTERED LAYOUT & NO GREY BAR
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

# --- FUNGSI UNHIDE/HIDE ---
def set_sheet_visibility(sh, sheet_id, visible=True):
    body = {
        "requests": [
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_id,
                        "hidden": not visible 
                    },
                    "fields": "hidden"
                }
            }
        ]
    }
    try:
        sh.batch_update(body)
    except Exception as e:
        print(f"Gagal ubah visibilitas: {e}")

# --- FUNGSI PDF FETCH ---
@st.cache_data(ttl=300) 
def get_hidden_sheet_as_pdf(tool_code):
    try:
        if not os.path.exists(CREDENTIALS_FILE):
            return None, "File credentials.json hilang."
        
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        gc = gspread.authorize(creds)
        
        try:
            sh = gc.open(MASTER_SPREADSHEET_NAME)
        except:
            return None, f"File '{MASTER_SPREADSHEET_NAME}' tidak ditemukan."

        target_sheet_name = f"LAST_{tool_code}"
        try:
            ws = sh.worksheet(target_sheet_name)
        except:
            return None, f"Sheet '{target_sheet_name}' tidak ditemukan."

        if creds.expired:
            creds.refresh(google.auth.transport.requests.Request())
        access_token = creds.token
        
        # --- URL EXPORT ---
        # Margin 0.15
        url = (f"https://docs.google.com/spreadsheets/d/{sh.id}/export?"
               f"format=pdf&gid={ws.id}&"
               "size=A4&portrait=true&fitw=false&scale=4&gridlines=false&printtitle=false&sheetnames=false&fzr=false&"
               "top_margin=0.15&bottom_margin=0&left_margin=0.15&right_margin=0")
        
        headers = {'Authorization': f'Bearer {access_token}'}
        
        set_sheet_visibility(sh, ws.id, visible=True)
        try:
            res = requests.get(url, headers=headers)
        finally:
            set_sheet_visibility(sh, ws.id, visible=False)
        
        if res.status_code != 200:
            return None, f"Gagal fetch PDF (Code: {res.status_code})"
            
        b64_pdf = base64.b64encode(res.content).decode('utf-8')
        return b64_pdf, None

    except Exception as e:
        return None, str(e)

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
        /* 1. GLOBAL RESET */
        .stApp { background-color: #000000; }
        .block-container { padding: 0 !important; max-width: 100% !important; }
        header { display: none; }

        /* 2. HEADER IMAGE */
        .visual-header {
            background-repeat: repeat-x; 
            background-size: auto 100%; 
            background-position: center top; 
            height: 250px; 
            width: 100vw; 
            display: flex; flex-direction: row; justify-content: center; align-items: center; gap: 30px;
            box-shadow: inset 0 0 0 2000px rgba(0, 0, 0, 0.2); 
            border-bottom: 4px solid #FFD700;
            margin-left: calc(-50vw + 50%);
            margin-right: calc(-50vw + 50%);
            margin-bottom: 40px;
        }

        /* 3. LAYOUT KOLOM */
        div[data-testid="column"] {
            display: flex;
            flex-direction: column;
            align-items: center !important; 
        }

        /* 4. CONTENT STYLE */
        iframe, .stImage img {
            display: block !important;
            margin: 0 auto !important;
        }

        /* 5. EXPANDER (EVIDENCE) -> TETAP 768px */
        div[data-testid="stExpander"] {
            width: 768px !important;
            min-width: 768px !important;
            max-width: 768px !important;
            margin: 0 auto !important;
            
            background-color: #2D2D2D !important;
            border: 1px solid #333 !important;
            border-radius: 4px;
        }
        .streamlit-expanderHeader {
            background-color: #2D2D2D !important; color: white !important; font-weight: 600;
        }
        .streamlit-expanderContent {
            background-color: #000000 !important; color: white !important; border-top: 1px solid #333;
        }
        [data-testid="stExpander"] p { color: #ccc !important; }

        /* 6. TITLE & BUTTON */
        .tool-title {
            color: #ffffff; font-size: 1.4rem; font-weight: 700;
            margin-bottom: 5px; 
            text-align: center; /* JUDUL RATA TENGAH */
            display: block;
        }
        
        .stButton button { 
            border-radius: 4px; font-weight: 600; 
            background-color: #007bff; color: white; height: 38px;
            margin: 0 auto; /* Tombol Center */
            display: block;
        }
        
        /* HEADER ASSETS */
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
        "LOC": "LOCALIZER", "GP": "GLIDE PATH", 
        "MM": "MIDDLE MARKER", "OM": "OUTER MARKER",
        "DVOR": "DVOR", "DME": "DME"
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
            found = [os.path.join(p, f) for f in os.listdir(p) 
                     if dstr in f and f.lower().endswith(extension_list)]
            candidates.extend(found)
    if candidates: 
        candidates.sort(key=os.path.getmtime, reverse=True)
        return candidates[0]
    return None

def run_robot(script, args):
    subprocess.Popen([sys.executable, LAUNCHER_SCRIPT, os.path.join(BASE_DIR, script)] + args)
    st.toast("🚀 Robot Start...", icon="⏳"); time.sleep(2); st.rerun()

# --- COMPONENT: RENDER TOOL CARD ---
def render_tool_card(tool_name, tool_code, script, args, is_ils=True):
    
    # 1. KONFIGURASI TAMPILAN
    paper_size_config = {
        "LOC":  {"w": 530, "h": 560}, 
        "GP":   {"w": 530, "h": 400},
        "MM":   {"w": 530, "h": 210},
        "OM":   {"w": 530, "h": 210},
        "DVOR": {"w": 530, "h": 480},
        "DME":  {"w": 530, "h": 425}
    }
    cfg = paper_size_config.get(tool_code, {"w": 530, "h": 600})
    WINDOW_W_PX = f"{cfg['w']}px"
    WINDOW_H_PX = f"{cfg['h']}px"
    
    # LEBAR IFRAME DIPERLEBAR LAGI
    INNER_IFRAME_W = "900px"
    
    # OFFSET / GESER KIRI (DIPERBESAR AGAR HILANG TOTAL)
    # Menaikkan offset ke -52px untuk memastikan area abu-abu habis
    PDF_X_OFFSET = "-52px" 
    
    # ALIGNMENT HEADER (Center relative to PDF Width)
    VIRTUAL_W = 854 
    HEADER_W = cfg['w']
    SPACER = (VIRTUAL_W - HEADER_W) / 2
    
    pdf_b64, err_msg = get_hidden_sheet_as_pdf(tool_code)
    evidence_file = None
    if not is_ils: 
        evidence_file = find_evidence_file(tool_name, datetime.now(), ('.pdf'))
    else:
        evidence_file = find_evidence_file(tool_code, datetime.now(), ('.png', '.jpg', '.jpeg'))

    # CONTAINER POLOS
    with st.container():
        
        # --- HEADER ALIGNMENT (JUDUL & TOMBOL DI TENGAH) ---
        # Kita buat 3 kolom: Spacer Kiri | Konten Tengah | Spacer Kanan
        c_L, c_Center, c_R = st.columns([SPACER, HEADER_W, SPACER])
        
        with c_Center:
            # 1. JUDUL
            st.markdown(f'<div class="tool-title">{tool_name}</div>', unsafe_allow_html=True)
            
            # 2. TOMBOL (Di bawah judul, di tengah)
            # Kita pakai sub-kolom agar tombol tidak terlalu lebar
            # Rasio [1, 1, 1] membuat tombol ada di tengah dgn ukuran wajar
            b_space1, b_btn, b_space2 = st.columns([1, 1.2, 1])
            with b_btn:
                # Label Tombol: RUN LOC, RUN GP, dst
                if st.button(f"RUN {tool_code}", key=f"run_{tool_code}", use_container_width=True):
                    run_robot(script, args)
        
        st.write("") 

        # --- PDF DISPLAY ---
        if pdf_b64:
            pdf_display = f"""
                <div style="width:{WINDOW_W_PX}; height:{WINDOW_H_PX}; overflow:hidden; border:none; margin: 0 auto 15px auto; position: relative;">
                    <iframe src="data:application/pdf;base64,{pdf_b64}#toolbar=0&navpanes=0&scrollbar=0&zoom=100" 
                            width="{INNER_IFRAME_W}" 
                            height="1200px" 
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
                    with open(evidence_file, "rb") as f:
                        b64_img = base64.b64encode(f.read()).decode('utf-8')
                    img_html = f"""
                        <div style="width:100%; overflow:hidden; border-radius:4px; margin: 0 auto;">
                            <img src="data:image/png;base64,{b64_img}" style="width:100%; display:block;">
                        </div>
                    """
                    st.markdown(img_html, unsafe_allow_html=True)
                else:
                    with open(evidence_file, "rb") as f:
                        b64_ev_pdf = base64.b64encode(f.read()).decode('utf-8')
                    ev_pdf_html = f"""
                        <div style="width:100%; height:600px; overflow:hidden; border-radius:4px; margin: 0 auto;">
                            <iframe src="data:application/pdf;base64,{b64_ev_pdf}#toolbar=0&navpanes=0&scrollbar=0&view=FitH" 
                                    width="100%" 
                                    height="100%" 
                                    style="border:none;"
                                    scrolling="no">
                            </iframe>
                        </div>
                    """
                    st.markdown(ev_pdf_html, unsafe_allow_html=True)
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

# --- MAIN LAYOUT (2 KOLOM) ---
with st.container():
    
    # TOMBOL RUN ALL
    c_run_all = st.columns([1, 2, 1]) 
    with c_run_all[1]:
        if st.button("🚀 RUN ALL METER READING", use_container_width=True):
            run_robot("bin/run_all.py", [])
    
    st.write("")
    
    st.markdown("### 📡 INSTRUMENT LANDING SYSTEM (ILS)")
    
    c1, c2 = st.columns(2)
    with c1:
        render_tool_card("Localizer", "LOC", "bin/robot_pmdt.py", ["--target", "LOC"], is_ils=True)
    with c2:
        render_tool_card("Glidepath", "GP", "bin/robot_pmdt.py", ["--target", "GP"], is_ils=True)

    c3, c4 = st.columns(2)
    with c3:
        render_tool_card("Middle Marker", "MM", "bin/robot_pmdt.py", ["--target", "MM"], is_ils=True)
    with c4:
        render_tool_card("Outer Marker", "OM", "bin/robot_pmdt.py", ["--target", "OM"], is_ils=True)

    st.markdown("### 📡 NAVIGASI UDARA (DVOR & DME)")
    c5, c6 = st.columns(2)
    with c5: render_tool_card("DVOR", "DVOR", "bin/robot_maru.py", ["--DVOR"], is_ils=False)
    with c6: render_tool_card("DME", "DME", "bin/robot_maru.py", ["--DME"], is_ils=False)

    st.markdown("<br><br>", unsafe_allow_html=True)