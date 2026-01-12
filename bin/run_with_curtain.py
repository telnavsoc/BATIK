# FILE: bin/run_with_curtain.py
# ================================================================
# BATIK LAUNCHER V4 (HARD KILLER)
# Menggunakan TASKKILL Windows untuk memastikan Robot mati total
# ================================================================

import subprocess
import sys
import time
import os

# PATH CONFIG
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CURTAIN_SCRIPT = os.path.join(BASE_DIR, "safety_curtain.py")
STOP_FLAG = os.path.join(BASE_DIR, "STOP_SIGNAL")
LOG_FILE = os.path.join(BASE_DIR, "live_monitor.log")

def log_system(msg):
    """Log pesan sistem ke file agar muncul di Curtain"""
    t = time.strftime("%H:%M:%S")
    formatted = f"{t} | SYSTEM           | {msg}\n"
    print(msg) # Print ke console asli
    try:
        with open(LOG_FILE, "a") as f: f.write(formatted)
    except: pass

def kill_process_tree(pid):
    """Membunuh proses dan anak-anaknya menggunakan Windows Taskkill"""
    try:
        # /F = Force, /T = Tree (Kill children), /PID = Process ID
        subprocess.run(f"taskkill /F /T /PID {pid}", shell=True, 
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f">>> [LAUNCHER] PID {pid} tree killed.")
    except Exception as e:
        print(f">>> [LAUNCHER] Kill failed: {e}")

def run_job(robot_script, args_list):
    # Bersih-bersih
    if os.path.exists(STOP_FLAG):
        try: os.remove(STOP_FLAG)
        except: pass
    
    # Inisialisasi Log File
    with open(LOG_FILE, "w") as f: f.write("") 

    log_system("Launcher Start. Menyiapkan Curtain...")

    # 1. NYALAKAN CURTAIN
    curtain_process = subprocess.Popen([sys.executable, CURTAIN_SCRIPT])
    time.sleep(2)

    # 2. JALANKAN ROBOT
    log_system(f"Eksekusi Robot: {os.path.basename(robot_script)}")
    full_cmd = [sys.executable, robot_script] + args_list
    
    # Kita biarkan robot menulis outputnya sendiri ke console & file
    robot_process = subprocess.Popen(full_cmd)

    try:
        while True:
            # A. Cek Robot Selesai
            if robot_process.poll() is not None:
                log_system("Tugas Robot Selesai.")
                break
            
            # B. Cek Stop Signal
            if os.path.exists(STOP_FLAG) or curtain_process.poll() is not None:
                print("\n>>> [LAUNCHER] !!! EMERGENCY STOP DETECTED !!!")
                log_system("!!! EMERGENCY STOP DETECTED !!!")
                
                # --- HARD KILL ---
                log_system("Killing Process Tree...")
                kill_process_tree(robot_process.pid)
                
                break
            
            time.sleep(0.1)

    except KeyboardInterrupt:
        kill_process_tree(robot_process.pid)

    finally:
        log_system("Menutup Curtain...")
        if curtain_process.poll() is None:
            curtain_process.terminate()
        
        if os.path.exists(STOP_FLAG):
            try: os.remove(STOP_FLAG)
            except: pass

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python bin/run_with_curtain.py <script_robot> [args...]")
        sys.exit(1)

    target = sys.argv[1]
    
    # Path Resolver
    if not os.path.exists(target):
        alt_path = os.path.join(BASE_DIR, os.path.basename(target)) 
        if os.path.exists(alt_path): target = alt_path
        else:
            alt_path_2 = os.path.join(os.path.dirname(BASE_DIR), target)
            if os.path.exists(alt_path_2): target = alt_path_2
            else:
                sys.exit(1)

    run_job(target, sys.argv[2:])