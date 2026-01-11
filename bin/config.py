# FILE: bin/config.py (UPDATE)
import os

# --- BASE PATHS ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- DATABASE ---
DB_PATH = os.path.join(BASE_DIR, "data", "batik_master.db")

# --- OUTPUT PATHS ---
EVIDENCE_DIR = os.path.join(BASE_DIR, "output", "evidence_log")
TEMP_DIR = os.path.join(BASE_DIR, "output", "temp_raw")
LOG_DIR = os.path.join(BASE_DIR, "logs")

# --- ASSETS (Gambar Target PMDT) ---
# PERBAIKAN: Menunjuk ke subfolder 'assets' di dalam config
ASSETS_DIR = os.path.join(BASE_DIR, "config", "assets") 
COORD_FILE = os.path.join(BASE_DIR, "config", "data_koordinat.json")

# --- SUBDIRECTORIES ---
MARU_ROOT = os.path.join(EVIDENCE_DIR, "MARU")
DVOR_DIR = os.path.join(MARU_ROOT, "DVOR")
DME_DIR = os.path.join(MARU_ROOT, "DME")
PMDT_DIR = os.path.join(EVIDENCE_DIR, "PMDT")

# --- EXTERNAL APPS PATHS ---
PATH_PMDT = r"D:\ILS APP\PMDT v8.7.2.0\PMDT.exe"
# ... (Sisanya tetap sama) ...
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