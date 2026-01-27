import os
import time
import subprocess
import psutil
import pygetwindow as gw
import pyautogui
import sys
from datetime import datetime

# --- KONFIGURASI PATH ---
# Ambil folder "bin" secara absolut
BIN_DIR = os.path.dirname(os.path.abspath(__file__))
# Ambil folder "BATIK" (parent dari bin)
BASE_DIR = os.path.dirname(BIN_DIR)

# File Scripts
WATCHDOG_SCRIPT = "service_watchdog.py"
TRAY_SCRIPT = "batik_tray.py"
CURTAIN_SCRIPT = os.path.join(BIN_DIR, "run_with_curtain.py")
ROBOT_TARGET_SCRIPT = os.path.join(BIN_DIR, "run_all.py") 
DASHBOARD_SCRIPT = os.path.join(BASE_DIR, "dashboard.py")
DASHBOARD_URL = "http://localhost:8501" 
LOG_FILE = os.path.join(BASE_DIR, "routine_debug.log")

CREATE_NO_WINDOW = 0x08000000

def log(msg):
    """Catat log ke file routine_debug.log"""
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {msg}\n")
        print(msg) # Print juga ke console buat debug manual
    except: pass

def get_pythonw():
    return sys.executable.replace("python.exe", "pythonw.exe")

def kill_process_by_script(script_name):
    log(f"Attempting to stop {script_name}...")
    killed_count = 0
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['cmdline']:
                cmd_str = " ".join(proc.info['cmdline']).lower()
                if script_name.lower() in cmd_str:
                    if TRAY_SCRIPT.lower() in cmd_str:
                        continue # Lindungi Tray Icon
                    proc.kill()
                    killed_count += 1
        except: pass
    if killed_count > 0: log(f"-> Killed {killed_count} process(es).")

def run_robots_with_curtain():
    log(f"Running Robots: {CURTAIN_SCRIPT} -> {ROBOT_TARGET_SCRIPT}")
    
    # Validasi file dulu
    if not os.path.exists(CURTAIN_SCRIPT):
        log(f"CRITICAL: Curtain script not found at {CURTAIN_SCRIPT}")
        return
    if not os.path.exists(ROBOT_TARGET_SCRIPT):
        log(f"CRITICAL: Robot script not found at {ROBOT_TARGET_SCRIPT}")
        return

    cmd = [sys.executable, CURTAIN_SCRIPT, ROBOT_TARGET_SCRIPT]
    
    try:
        # PENTING: Tambahkan cwd=BIN_DIR agar script tahu dia ada di folder bin
        result = subprocess.run(
            cmd, 
            creationflags=CREATE_NO_WINDOW,
            cwd=BIN_DIR,  # <--- INI KUNCI PERBAIKANNYA
            capture_output=True, 
            text=True
        )
        
        if result.returncode != 0:
            log(f"ROBOT ERROR (Code {result.returncode}):")
            log(f"STDERR: {result.stderr}")
        else:
            log("Robot finished successfully.")
            
    except Exception as e:
        log(f"CRITICAL ERROR running robot: {str(e)}")

def open_dashboard_silent():
    log("Checking Dashboard Server...")
    # ... (logika sama, tapi tambah cwd)
    # Start Streamlit
    try:
        # Cek apakah sudah jalan
        already_running = False
        for proc in psutil.process_iter(['cmdline']):
            if proc.info['cmdline'] and 'streamlit' in " ".join(proc.info['cmdline']):
                already_running = True
                break
        
        if not already_running:
            log("Launching Streamlit Server...")
            subprocess.Popen(
                [get_pythonw(), "-m", "streamlit", "run", DASHBOARD_SCRIPT, "--server.headless", "true"],
                creationflags=CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                cwd=BASE_DIR # Streamlit butuh jalan di root folder
            )
            time.sleep(5)
            
        log("Opening Chrome...")
        os.system(f"start chrome {DASHBOARD_URL}")
        time.sleep(5)
    except Exception as e:
        log(f"Dashboard Launch Error: {e}")

def snap_chrome_right():
    log("Snapping Chrome Window...")
    # ... (logika snap window tetap sama)
    try:
        chrome_windows = [w for w in gw.getWindowsWithTitle('Chrome') if w.title != '']
        if not chrome_windows: chrome_windows = [w for w in gw.getWindowsWithTitle('Google Chrome')]
        if chrome_windows:
            win = chrome_windows[0]
            if win.isMinimized: win.restore()
            win.activate()
            screen_w, screen_h = pyautogui.size()
            win.moveTo(int(screen_w / 2), 0)
            win.resizeTo(int(screen_w / 2), screen_h)
            log("Snap Success.")
    except: pass

def main():
    log("=== ROUTINE STARTED (MANUAL/TASK) ===")
    kill_process_by_script(WATCHDOG_SCRIPT)
    run_robots_with_curtain()
    open_dashboard_silent()
    snap_chrome_right()
    
    log("Waiting 30 minutes...")
    # Ganti jadi 10 detik dulu untuk tes, nanti kembalikan ke 1800
    time.sleep(10) 
    
    log("Restarting Watchdog...")
    subprocess.Popen(
        [get_pythonw(), os.path.join(BIN_DIR, WATCHDOG_SCRIPT)], 
        creationflags=CREATE_NO_WINDOW,
        cwd=BIN_DIR
    )
    log("=== ROUTINE FINISHED ===")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"MAIN CRASH: {e}")