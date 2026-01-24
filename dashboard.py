# FILE: dashboard.py
# ================================================================
# BATIK SOLO DASHBOARD - PERFECT FIT (WIDTH & HEIGHT)
# ================================================================

import streamlit as st
import pandas as pd
import os
import sys
import subprocess
import time
import base64
import gspread 
from datetime import datetime

# --- CONFIG & PATHS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BIN_DIR = os.path.join(BASE_DIR, "bin")
sys.path.append(BIN_DIR)

import config 
import sheet_handler 
import batik_parser 

# --- SETUP GSPREAD DIRECT ---
CREDENTIALS_FILE = os.path.join(BASE_DIR, 'credentials.json')
MASTER_SPREADSHEET_NAME = "LOGBOOK_BATIK"

def get_sheet_meta(tool_code):
    try:
        if not os.path.exists(CREDENTIALS_FILE):
            return None, None, "File credentials.json hilang."
            
        gc = gspread.service_account(filename=CREDENTIALS_FILE)
        
        try:
            sh = gc.open(MASTER_SPREADSHEET_NAME)
        except:
            return None, None, f"File '{MASTER_SPREADSHEET_NAME}' tidak ditemukan."

        target_sheet_name = f"LAST_{tool_code}"
        try:
            ws = sh.worksheet(target_sheet_name)
            return sh.id, ws.id, None
        except:
            return None, None, f"Sheet '{target_sheet_name}' tidak ditemukan."

    except Exception as e:
        return None, None, str(e)

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
        .tool-card-container {
            background-color: #f8f9fa;
            border-radius: 12px;
            border-left: 6px solid #FFD700;
            padding: 15px;
            margin-bottom: 25px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        }
        .tool-title {
            color: #2c3e50; font-size: 1.5rem; font-weight: 700;
            margin-bottom: 0px; 
            display: flex; justify-content: space-between; align-items: center;
        }
        
        /* Iframe Style - FIXED PIXEL WIDTH */
        .sheet-frame {
            border: 1px solid #ccc;
            border-radius: 4px;
            overflow: hidden;
            background: white;
            margin-top: 15px;
            /* Width diatur inline via Python */
        }
        
        header[data-testid="stHeader"] { z-index: 1; }
        footer {visibility: hidden;}
        .block-container { padding-top: 2rem; }
        .visual-header {
            background-repeat: repeat-x; background-size: auto 100%;
            background-position: center top; height: 280px; width: 100%;
            display: flex; flex-direction: row; justify-content: center;
            align-items: center; gap: 30px;
            box-shadow: inset 0 0 0 2000px rgba(10, 10, 15, 0.85); 
            margin-bottom: 30px; border-bottom: 6px solid #FFD700;
        }
        .header-logo { height: 180px; width: auto; object-fit: contain; }
        .text-container { display: flex; flex-direction: column; text-align: left; }
        .batik-title-text { font-size: 2.8rem; color: #FFFFFF; font-weight: 700; margin: 0; }
        .airnav-sub { font-family: 'Times New Roman', serif; font-size: 2.2rem; color: #FFD700; margin-top: 5px; }
        section[data-testid="stSidebar"] { display: none; }
        .stButton button { width: 100%; border-radius: 6px; font-weight: 600; background-color: #007bff; color: white;}
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
    possible_paths = [
        os.path.join(config.OUTPUT_DIR, category, folder_name, "Transmitter_Data"),
        os.path.join(config.OUTPUT_DIR, category, folder_name),
        os.path.join(config.OUTPUT_DIR, category, tool_code)
    ]
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
    ssid, gid, err_msg = get_sheet_meta(tool_code)

    evidence_file = None
    if not is_ils: 
        evidence_file = find_evidence_file(tool_name, datetime.now(), ('.pdf'))
    else:
        evidence_file = find_evidence_file(tool_code, datetime.now(), ('.png', '.jpg', '.jpeg'))

    st.markdown('<div class="tool-card-container">', unsafe_allow_html=True)
    
    c_title, c_btn = st.columns([3, 1])
    with c_title:
        st.markdown(f'<div class="tool-title">{tool_name}</div>', unsafe_allow_html=True)
    with c_btn:
        if st.button(f"▶ RUN", key=f"run_{tool_code}"):
            run_robot(script, args)

    st.markdown("---")

    # GOOGLE SHEET EMBED (FIXED WIDTH & HEIGHT)
    if ssid and gid:
        # KONFIGURASI HEIGHT (Tinggi) & WIDTH (Lebar)
        # Lebar 700px biasanya pas untuk 6 Kolom (A-F)
        # Jika masih kepotong kanan, naikkan width jadi 720 atau 750
        range_config = {
            "LOC":  {"row": "23", "height": "630", "width": "760"},
            "GP":   {"row": "17", "height": "460", "width": "760"},
            "MM":   {"row": "10", "height": "270", "width": "760"},
            "OM":   {"row": "10", "height": "270", "width": "760"},
            "DVOR": {"row": "20", "height": "540", "width": "760"},
            "DME":  {"row": "18", "height": "490", "width": "760"}
        }
        
        conf = range_config.get(tool_code, {"row": "25", "height": "600", "width": "100%"})
        
        target_range = f"A1:F{conf['row']}"
        frame_height = f"{conf['height']}px"
        frame_width = f"{conf['width']}px" if conf['width'] != "100%" else "100%"

        sheet_url = f"https://docs.google.com/spreadsheets/d/{ssid}/htmlembed?gid={gid}&widget=false&chrome=false&single=true&headers=false&range={target_range}"
        
        # Perhatikan atribut 'width' pada iframe sekarang mengambil dari config
        st.markdown(f"""
            <div class="sheet-frame" style="width: {frame_width};">
                <iframe src="{sheet_url}" width="100%" height="{frame_height}" frameborder="0" scrolling="no"></iframe>
            </div>
            <div style="text-align:right; font-size:0.8rem; margin-top:5px; width: {frame_width};">
                <a href="https://docs.google.com/spreadsheets/d/{ssid}/edit?gid={gid}" target="_blank" style="color:#999; text-decoration:none;">🔗 Edit Data</a>
            </div>
        """, unsafe_allow_html=True)
    else:
        if err_msg: st.warning(f"⚠️ {err_msg}")
        else: st.info("Loading Sheet...")

    with st.expander("📸 Lihat Evidence", expanded=False):
        if evidence_file:
            st.caption(f"File: {os.path.basename(evidence_file)}")
            if is_ils: 
                st.image(evidence_file, use_container_width=True)
            else:
                with open(evidence_file, "rb") as f:
                    base64_pdf = base64.b64encode(f.read()).decode('utf-8')
                pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
                st.markdown(pdf_display, unsafe_allow_html=True)
        else:
            st.info("Belum ada evidence.")

    st.markdown('</div>', unsafe_allow_html=True)

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
st.markdown("### 📡 INSTRUMENT LANDING SYSTEM (ILS)")
c1, c2 = st.columns(2)
with c1:
    render_tool_card("Localizer", "LOC", "bin/robot_pmdt.py", ["--target", "LOC"], is_ils=True)
    render_tool_card("Middle Marker", "MM", "bin/robot_pmdt.py", ["--target", "MM"], is_ils=True)
with c2:
    render_tool_card("Glidepath", "GP", "bin/robot_pmdt.py", ["--target", "GP"], is_ils=True)
    render_tool_card("Outer Marker", "OM", "bin/robot_pmdt.py", ["--target", "OM"], is_ils=True)

st.markdown("### 📡 NAVIGASI UDARA (DVOR & DME)")
c3, c4 = st.columns(2)
with c3: render_tool_card("DVOR", "DVOR", "bin/robot_maru.py", ["--DVOR"], is_ils=False)
with c4: render_tool_card("DME", "DME", "bin/robot_maru.py", ["--DME"], is_ils=False)

st.markdown("---")
if st.button("🚀 RUN ALL METER READING", use_container_width=True):
    run_robot("bin/run_all.py", [])