import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw
import psutil
import time
import threading
import os
import sys
import subprocess
import requests

# --- CONFIG ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICON_PATH = os.path.join(BASE_DIR, "B.png")
DASHBOARD_SCRIPT = os.path.join(BASE_DIR, "dashboard.py")
CURTAIN_SCRIPT = os.path.join(BASE_DIR, "bin", "run_with_curtain.py")
ROBOT_TARGET_SCRIPT = os.path.join(BASE_DIR, "bin", "run_all.py")
DASHBOARD_URL = "http://localhost:8501"

# Flag Windows untuk menyembunyikan window
CREATE_NO_WINDOW = 0x08000000

current_status = "Initializing..."
is_running = True

def get_icon():
    if os.path.exists(ICON_PATH):
        try: return Image.open(ICON_PATH)
        except: pass
    img = Image.new('RGB', (64, 64), 'green')
    dc = ImageDraw.Draw(img)
    dc.rectangle((16, 16, 48, 48), fill='white')
    return img

def check_process(script_name):
    try:
        for proc in psutil.process_iter(['cmdline']):
            try:
                if proc.info['cmdline'] and script_name in " ".join(proc.info['cmdline']):
                    return True
            except: continue
    except: pass
    return False

# --- MENU ACTIONS ---
def on_quit(icon, item):
    global is_running
    is_running = False
    icon.stop()

def run_meter_reading(icon, item):
    icon.notify("Memulai Meter Reading (Curtain Mode)...", "BATIK System")
    
    # [PERBAIKAN UTAMA] Paksa gunakan pythonw.exe (tanpa console)
    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
    
    subprocess.Popen(
        [pythonw, CURTAIN_SCRIPT, ROBOT_TARGET_SCRIPT], 
        creationflags=CREATE_NO_WINDOW
    )

def open_dashboard_smart(icon, item):
    streamlit_running = check_process("dashboard.py")
    if not streamlit_running:
        icon.notify("Booting Dashboard Server...", "BATIK System")
        pythonw = sys.executable.replace("python.exe", "pythonw.exe")
        subprocess.Popen(
            [pythonw, "-m", "streamlit", "run", DASHBOARD_SCRIPT, "--server.headless", "true"],
            creationflags=CREATE_NO_WINDOW,
            cwd=BASE_DIR
        )
        time.sleep(3)
    os.system(f"start chrome {DASHBOARD_URL}")

def restart_watchdog(icon, item):
    script = os.path.join(BASE_DIR, "bin", "service_watchdog.py")
    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
    subprocess.Popen([pythonw, script], creationflags=CREATE_NO_WINDOW)
    icon.notify("Watchdog Restarted.", "BATIK System")

# --- MONITOR LOOP ---
def monitor_loop(icon):
    global current_status
    icon.visible = True
    while is_running:
        try:
            robot_active = check_process("run_with_curtain.py") or check_process("run_all.py")
            watchdog_active = check_process("service_watchdog.py")
            status = []
            if robot_active: status.append("🤖 Robot: WORKING")
            if watchdog_active: status.append("🛡️ Watchdog: ACTIVE")
            if not status: status.append("⚠️ IDLE/STOPPED")
            icon.title = f"BATIK System\n{' | '.join(status)}"
        except: pass
        time.sleep(2)

def is_tray_already_running():
    current_pid = os.getpid()
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['cmdline'] and 'batik_tray.py' in " ".join(proc.info['cmdline']):
                if proc.info['pid'] != current_pid: return True
        except: pass
    return False

menu = (
    item('Buka Dashboard', open_dashboard_smart),
    item('Jalankan Meter Reading (All)', run_meter_reading),
    item('Nyalakan Watchdog', restart_watchdog),
    item('Exit', on_quit)
)

if __name__ == "__main__":
    if is_tray_already_running(): sys.exit()
    tray_icon = pystray.Icon("BATIK_Monitor", get_icon(), "BATIK System", menu)
    threading.Thread(target=monitor_loop, args=(tray_icon,), daemon=True).start()
    tray_icon.run()