# FILE: dashboard.py
# ================================================================
# BATIK SOLO DASHBOARD - FINAL PRODUCTION
# FITUR: SMART CACHE (HANYA RELOAD JIKA DATA BERUBAH), STABLE UI
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
from PIL import Image

# Library untuk Window Focus
import pygetwindow as gw 

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

# --- LOAD ASSETS ---
ICON_PATH = r"D:\eman\BATIK\B.png"
REFRESH_ICON_PATH = r"D:\eman\BATIK\refresh.png"
ILS_ICON_PATH = r"D:\eman\BATIK\ils_icon.png"
DVOR_ICON_PATH = r"D:\eman\BATIK\dvor_icon.png"
BG_LITE_PATH = "background_lite.jpg"
BG_PNG_PATH = "background.png"
LOGO_PATH = "logo.png"

page_icon_img = "📒"
try:
    if os.path.exists(ICON_PATH):
        page_icon_img = Image.open(ICON_PATH)
except Exception as e:
    pass

# --- HELPER: SMART IMAGE CACHING ---
@st.cache_data
def get_img_as_base64(file_path, _mtime=None):
    if not os.path.exists(file_path): return ""
    with open(file_path, "rb") as f: data = f.read()
    return base64.b64encode(data).decode()

def load_smart_img(path):
    if os.path.exists(path):
        return get_img_as_base64(path, os.path.getmtime(path))
    return ""

# Load Assets
refresh_icon_b64 = load_smart_img(REFRESH_ICON_PATH)
ils_icon_b64 = load_smart_img(ILS_ICON_PATH)
dvor_icon_b64 = load_smart_img(DVOR_ICON_PATH)
logo_b64 = load_smart_img(LOGO_PATH)

header_bg_b64 = ""
if os.path.exists(BG_LITE_PATH):
    header_bg_b64 = load_smart_img(BG_LITE_PATH)
elif os.path.exists(BG_PNG_PATH):
    header_bg_b64 = load_smart_img(BG_PNG_PATH)

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="BATIK SOLO",
    page_icon=page_icon_img,
    layout="wide",
    initial_sidebar_state="collapsed" 
)

# --- STATE MANAGEMENT ---
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

# --- SMART DATA CACHE LOGIC ---

# 1. Fungsi Ringan: Cek Kapan Terakhir Spreadsheet Diedit
# Fungsi ini berjalan cepat setiap kali refresh browser.
# Jika timestamp tidak berubah, maka fungsi PDF yang berat TIDAK AKAN dijalankan.
@st.cache_data(ttl=60) # Cek metadata ke Google setiap 60 detik (sangat ringan)
def get_last_data_update():
    gc, _ = get_gspread_client()
    if not gc: return None
    try:
        sh = gc.open(MASTER_SPREADSHEET_NAME)
        # lastUpdateTime berisi string timestamp kapan file terakhir diedit
        return sh.lastUpdateTime 
    except:
        return datetime.now().strftime("%Y-%m-%d %H") # Fallback jika gagal

# 2. Fungsi Berat: Generate PDF
# HAPUS ttl=300. Sekarang kita andalkan parameter 'data_timestamp'
# Cache hanya akan invalid jika 'cache_ver' berubah (klik tombol) ATAU 'data_timestamp' berubah (edit sheet)
@st.cache_data(show_spinner="Memproses Data Terbaru...") 
def get_hidden_sheet_as_pdf(tool_code, cache_ver, data_timestamp):
    try:
        gc, creds = get_gspread_client()
        if not gc: return None, "Koneksi Google Gagal"
        
        try:
            sh = gc.open(MASTER_SPREADSHEET_NAME)
        except:
            return None, "Spreadsheet Hilang"

        target_sheet_name = f"LAST_{tool_code}"
        try:
            ws = sh.worksheet(target_sheet_name)
        except:
            return None, f"Sheet '{target_sheet_name}' Tidak Ditemukan"

        if creds.expired:
            creds.refresh(google.auth.transport.requests.Request())
        
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
        
        if res.status_code != 200: return None, f"Error {res.status_code}"
        
        return base64.b64encode(res.content).decode('utf-8'), None
    except Exception as e:
        return None, str(e)

LAUNCHER_SCRIPT = os.path.join(BIN_DIR, "run_with_curtain.py")

# --- CSS STYLING ---
st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&display=swap');

        .stApp {{ background-color: #000000; }}
        
        .block-container {{ 
            padding-top: 0rem !important; 
            padding-left: 1rem !important;     
            padding-right: 1rem !important;    
            padding-bottom: 0rem !important;
            max-width: 100vw !important;       
        }}
        
        header {{ display: none; }}
        footer {{ display: none !important; }}

        /* HEADER IMAGE */
        .visual-header {{
            background-repeat: repeat-x; background-size: auto 100%; background-position: center top; 
            height: 250px; 
            width: calc(100% + 2rem); 
            margin-top: -15px !important;
            margin-left: -1rem; 
            margin-right: -1rem;
            display: flex; flex-direction: row; justify-content: center; 
            align-items: center; gap: 20px; 
            border-bottom: 4px solid #FFD700; margin-bottom: 30px;
        }}

        /* TYPOGRAPHY */
        .batik-title-text {{ 
            font-family: 'Playfair Display', 'Times New Roman', serif; 
            font-size: 2.5rem; color: #FFFFFF; font-weight: 700; 
            margin-top: 5px; margin-bottom: 0; line-height: 1.1;
            text-shadow: 2px 2px 5px #000000;
        }}
        .airnav-sub {{ 
            font-family: 'Times New Roman', serif; font-size: 1.8rem; 
            color: #FFD700; margin-top: 0px; text-shadow: 1px 1px 3px #000000;
        }}
        .header-logo {{ height: 130px; width: auto; object-fit: contain; margin-top: 0px; }}

        /* BOX STYLE */
        div[data-testid="stVerticalBlock"]:has(> .element-container .tool-title) {{
            border: 3px solid #666 !important;    
            border-radius: 15px !important;       
            background-color: #121212 !important; 
            box-shadow: 0 10px 30px rgba(0,0,0, 0.9), 0 0 8px rgba(255,255,255, 0.15) !important;
            padding: 20px !important;
            margin-bottom: 25px !important;
            gap: 15px !important;
        }}

        .tool-title {{ 
            color: #ffffff; font-size: 1.6rem; font-weight: 700; 
            margin-bottom: 15px; text-align: center; display: block; 
            border-bottom: 2px solid #FFD700; padding-bottom: 10px;
            text-transform: uppercase; letter-spacing: 1px;
        }}

        /* BUTTON STYLE (RUN) */
        .stButton button {{
            background-color: #222 !important;
            border: 1px solid #555 !important;
            color: white !important;
            font-weight: 700 !important;
            height: 55px !important;
            border-radius: 6px !important;
            transition: all 0.2s ease !important;
        }}
        .stButton button:hover {{
            border-color: #FFD700 !important;
            color: #FFD700 !important;
            background-color: #333 !important;
            font-weight: 900 !important; 
            transform: scale(1.02);
            box-shadow: 0 0 10px rgba(255, 215, 0, 0.2);
        }}

        /* REFRESH BUTTON */
        div[data-testid="stVerticalBlock"]:has(> .element-container .tool-title) [data-testid="stHorizontalBlock"] [data-testid="stColumn"]:nth-child(3) button {{
            background-image: url("data:image/png;base64,{refresh_icon_b64}");
            background-size: 48px 48px !important; 
            background-repeat: no-repeat;
            background-position: center;
            border: none !important;
            background-color: transparent !important;
            box-shadow: none !important;
            color: transparent !important;
            height: 55px; width: 100%;
            transition: transform 0.2s ease;
            position: relative;
        }}
        
        div[data-testid="stVerticalBlock"]:has(> .element-container .tool-title) [data-testid="stHorizontalBlock"] [data-testid="stColumn"]:nth-child(3) button:hover {{
            transform: scale(1.25) !important; 
            background-color: transparent !important; 
            border: none !important;
            box-shadow: none !important;
            color: transparent !important;
            font-weight: normal !important;
        }}

        /* TOOLTIP REFRESH */
        div[data-testid="stVerticalBlock"]:has(> .element-container .tool-title) [data-testid="stHorizontalBlock"] [data-testid="stColumn"]:nth-child(3) button:hover::after {{
            content: "Muat Ulang Data";
            position: absolute; bottom: -35px; left: 50%; transform: translateX(-50%) scale(0.8);
            background-color: #333; color: #FFD700; padding: 4px 8px; border-radius: 4px;
            font-size: 10px; font-family: sans-serif; white-space: nowrap; border: 1px solid #555;
            z-index: 999; pointer-events: none;
        }}
        
        div[data-testid="stExpander"] {{ border: none !important; box-shadow: none !important; background-color: transparent !important; }}
        .streamlit-expanderHeader {{ background-color: transparent !important; border-bottom: 1px solid #444 !important; color: #ccc !important; }}
        
        .footer-credit {{
            text-align: left; color: #666; font-size: 0.8rem;
            margin-top: 50px; margin-bottom: 0px !important; padding-bottom: 5px;
            margin-left: 10px; font-family: monospace; letter-spacing: 1px; opacity: 0.6;
        }}
        
        .text-container {{ display: flex; flex-direction: column; text-align: left; }}
        section[data-testid="stSidebar"] {{ display: none; }}
        
        h3 {{ color: #FFFFFF !important; font-family: 'Segoe UI', sans-serif; margin-bottom: 15px !important; }}
    </style>
""", unsafe_allow_html=True)

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

def switch_to_app(tool_code):
    target_keyword = ""
    if tool_code == "DVOR": target_keyword = "MARU 220"
    elif tool_code == "DME": target_keyword = "MARU 310"
    else: target_keyword = "RCSU"

    try:
        windows = gw.getWindowsWithTitle(target_keyword)
        if windows:
            app_window = windows[0]
            if not app_window.isActive:
                try:
                    app_window.minimize()
                    time.sleep(0.1)
                    app_window.restore()
                except: pass
            app_window.activate()
            time.sleep(0.5) 
        else:
            print(f"Warning: Window '{target_keyword}' tidak ditemukan.")
    except Exception as e:
        print(f"Focus Error: {e}")

def on_click_run(script, args, tool_code):
    switch_to_app(tool_code)
    try:
        st.toast(f"🤖 Robot {tool_code} Sedang Berjalan...", icon="⏳")
        process = subprocess.run(
            [sys.executable, LAUNCHER_SCRIPT, os.path.join(BASE_DIR, script)] + args,
            capture_output=True, text=True
        )
        if process.returncode == 0:
            st.toast(f"✅ Robot {tool_code} Selesai!", icon="🤖")
            st.session_state.cache_versions[tool_code] += 1
        else:
            st.toast(f"❌ Error Robot {tool_code}", icon="⚠️")
            print(process.stderr)
    except Exception as e:
        st.error(f"System Error: {e}")

def on_click_refresh(tool_code):
    st.session_state.cache_versions[tool_code] += 1
    st.toast("Memuat ulang data...", icon="🔄")

def render_tool_card(tool_name, tool_code, script, args, is_ils=True, pad_height=0):
    cfg = {"LOC":{"w":530,"h":560},"GP":{"w":530,"h":400},"MM":{"w":530,"h":210},"OM":{"w":530,"h":210},"DVOR":{"w":530,"h":480},"DME":{"w":530,"h":425}}.get(tool_code, {"w":530,"h":500})
    W_PX, H_PX = f"{cfg['w']}px", f"{cfg['h']}px"
    
    current_version = st.session_state.cache_versions[tool_code]
    
    # [SMART CACHE CALL]
    # Ambil timestamp data terbaru. Jika belum 60 detik, pakai cache ringan.
    # Jika timestamp sama dengan cache sebelumnya, fungsi PDF (berat) tidak akan jalan.
    latest_data_time = get_last_data_update()
    
    # Panggil fungsi PDF dengan kunci tambahan (timestamp)
    pdf_b64, err_msg = get_hidden_sheet_as_pdf(tool_code, current_version, latest_data_time)
    
    evidence_file = None
    if not is_ils: 
        evidence_file = find_evidence_file(tool_name, datetime.now(), ('.pdf'))
    else:
        evidence_file = find_evidence_file(tool_code, datetime.now(), ('.png', '.jpg', '.jpeg'))

    with st.container():
        st.markdown(f'<div class="tool-title">{tool_name}</div>', unsafe_allow_html=True)
        
        c_left, c_center, c_right = st.columns([1, 4, 1]) 
        
        with c_left: st.empty()
        with c_center: 
            st.button(f"RUN {tool_code}", key=f"run_{tool_code}", use_container_width=True, 
                      on_click=on_click_run, args=(script, args, tool_code))
        with c_right: 
            st.button(" ", key=f"ref_{tool_code}", use_container_width=True,
                      on_click=on_click_refresh, args=(tool_code,))
        
        st.write("") 

        if pdf_b64:
            st.markdown(f"""
                <div style="display: flex; justify-content: center; width: 100%;">
                    <div style="width:{W_PX}; height:{H_PX}; overflow:hidden; border:none; position: relative;">
                        <iframe src="data:application/pdf;base64,{pdf_b64}#toolbar=0&navpanes=0&scrollbar=0&zoom=100" 
                                width="900px" height="1200px" 
                                style="border:none; position: absolute; top: -2px; left: -52px; pointer-events:none;"
                                scrolling="no">
                        </iframe>
                    </div>
                </div>
            """, unsafe_allow_html=True)
        else:
            if err_msg: st.warning(f"⚠️ {err_msg}")
            else: st.info("Loading Data...")

        if pad_height > 0:
            st.markdown(f'<div style="height: {pad_height}px;"></div>', unsafe_allow_html=True)

        st.write("")
        with st.expander("📸 Lihat Evidence"):
            if evidence_file:
                st.caption(f"File: {os.path.basename(evidence_file)}")
                if is_ils:
                    with open(evidence_file, "rb") as f: b64_img = base64.b64encode(f.read()).decode('utf-8')
                    st.markdown(f'<div style="width:100%; text-align:center;"><img src="data:image/png;base64,{b64_img}" style="max-width:100%; border-radius:4px;"></div>', unsafe_allow_html=True)
                else:
                    with open(evidence_file, "rb") as f: b64_ev_pdf = base64.b64encode(f.read()).decode('utf-8')
                    st.markdown(f'<iframe src="data:application/pdf;base64,{b64_ev_pdf}#toolbar=0&navpanes=0&scrollbar=0&view=FitH" width="100%" height="500px" style="border:none;"></iframe>', unsafe_allow_html=True)
            else:
                st.info("Belum ada evidence.")

# --- HEADER SECTION ---
st.markdown(f"""
    <div class="visual-header" style="background-image: url('data:image/jpg;base64,{header_bg_b64}');">
        <img src="data:image/png;base64,{logo_b64}" class="header-logo">
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
        if st.button("🚀 RUN ALL METER READING", use_container_width=True): 
             switch_to_app("LOC") 
             with st.spinner("Menjalankan Semua Robot..."):
                subprocess.run([sys.executable, LAUNCHER_SCRIPT, os.path.join(BIN_DIR, "run_all.py")], capture_output=True)
             st.rerun()
    
    st.write("")
    
    # HEADER ILS (ICON 80px)
    st.markdown(f"""
        <div style="display:flex; align-items:center; gap:20px; margin-bottom: 5px;">
            <img src="data:image/png;base64,{ils_icon_b64}" width="80" height="80">
            <h3 style="margin:0; padding:0; color:white; font-size: 1.8rem;">INSTRUMENT LANDING SYSTEM (ILS)</h3>
        </div>
    """, unsafe_allow_html=True)
    
    c1, c2 = st.columns(2) 
    with c1: render_tool_card("Localizer", "LOC", "bin/robot_pmdt.py", ["--target", "LOC"], is_ils=True)
    with c2: render_tool_card("Glidepath", "GP", "bin/robot_pmdt.py", ["--target", "GP"], is_ils=True, pad_height=160)
    
    c3, c4 = st.columns(2)
    with c3: render_tool_card("Middle Marker", "MM", "bin/robot_pmdt.py", ["--target", "MM"], is_ils=True)
    with c4: render_tool_card("Outer Marker", "OM", "bin/robot_pmdt.py", ["--target", "OM"], is_ils=True)
    
    # DIVIDER GOLD
    st.markdown("""<hr style="height:2px;border:none;color:#FFD700;background-color:#FFD700; margin-top: 40px; margin-bottom: 40px;" /> """, unsafe_allow_html=True)

    # HEADER DVOR (ICON 80px)
    st.markdown(f"""
        <div style="display:flex; align-items:center; gap:20px; margin-bottom: 5px;">
            <img src="data:image/png;base64,{dvor_icon_b64}" width="80" height="80">
            <h3 style="margin:0; padding:0; color:white; font-size: 1.8rem;">NAVIGASI UDARA (DVOR & DME)</h3>
        </div>
    """, unsafe_allow_html=True)
    
    c5, c6 = st.columns(2)
    with c5: render_tool_card("DVOR", "DVOR", "bin/robot_maru.py", ["--DVOR"], is_ils=False)
    with c6: render_tool_card("DME", "DME", "bin/robot_maru.py", ["--DME"], is_ils=False, pad_height=55)
    
    st.markdown("<br><br>", unsafe_allow_html=True)

# --- CREDIT FOOTER (STATIC) ---
st.markdown('<div class="footer-credit">Designed by <b>EBS</b></div>', unsafe_allow_html=True)