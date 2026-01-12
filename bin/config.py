# FILE: bin/config.py
# ================================================================
# CONFIGURASI BATIK (MERGED: ORIGINAL USER SETTINGS + NEW STRUCTURE)
# ================================================================
import os

# --- BASE PATHS ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- DATABASE ---
# Menggunakan setting asli Anda
DB_PATH = os.path.join(BASE_DIR, "data", "batik_master.db")

# --- OUTPUT PATHS ---
OUTPUT_DIR = os.path.join(BASE_DIR, "output") # Ditambahkan untuk referensi umum
EVIDENCE_DIR = os.path.join(BASE_DIR, "output", "evidence_log")
TEMP_DIR = os.path.join(BASE_DIR, "output", "temp_raw")
LOG_DIR = os.path.join(BASE_DIR, "logs")

# --- ASSETS (Gambar Target PMDT) ---
ASSETS_DIR = os.path.join(BASE_DIR, "config", "assets") 
COORD_FILE = os.path.join(BASE_DIR, "config", "data_koordinat.json")

# --- SUBDIRECTORIES (LEGACY SUPPORT) ---
# Tetap dibiarkan agar script lama tidak error
MARU_ROOT = os.path.join(EVIDENCE_DIR, "MARU")
DVOR_DIR = os.path.join(MARU_ROOT, "DVOR")
DME_DIR = os.path.join(MARU_ROOT, "DME")
PMDT_DIR = os.path.join(EVIDENCE_DIR, "PMDT")

# --- EXTERNAL APPS PATHS (ORIGINAL) ---
PATH_PMDT = r"D:\ILS APP\PMDT v8.7.2.0\PMDT.exe"
PATH_DASHBOARD = r"D:\eman\monitor jaringan\MoDar-v1.1\MonitoringDashboard.exe"
PATH_DASHBOARD_WD = r"D:\eman\monitor jaringan\MoDar-v1.1"
PATH_RCSU = r"D:\ILS APP\RCSU\Rcsu.exe"
PATH_MARU_310 = r"D:\APP peralatan\MOPHIENS\MARU 310\MARU 310.exe"
IP_MARU_310 = "192.168.56.45"
PATH_MARU_220 = r"D:\APP peralatan\MOPHIENS\MARU 220\MARU 220.exe"
IP_MARU_220 = "192.168.56.41"

# --- PMDT SETTINGS ---
PMDT_ANCHOR = (2379, -1052, 1024, 768)

# --- TIMINGS ---
DELAY_SHORT = 0.5
DELAY_MEDIUM = 1.5
DELAY_LONG = 3.0
DELAY_EXTRA = 5.0

# ================================================================
# [BARU] FUNGSI STRUKTUR FOLDER RAPI (MARU/DVOR, PMDT/LOC)
# ================================================================
def get_output_folder(category, tool_name):
    """
    Membuat folder otomatis: output/CATEGORY/TOOL_NAME/
    Contoh: output/PMDT/LOCALIZER/ atau output/MARU/DME/
    Digunakan oleh robot_pmdt.py dan robot_maru.py yang baru.
    """
    # Bersihkan nama alat dari karakter path yang tidak valid
    clean_name = tool_name.replace("/", "_").replace("\\", "_")
    
    # Path tujuan: BASE_DIR/output/KATEGORI/NAMA_ALAT
    target_path = os.path.join(OUTPUT_DIR, category, clean_name)
    
    if not os.path.exists(target_path):
        os.makedirs(target_path)
        
    return target_path