# FILE: bin/run_with_curtain.py
# ================================================================
# BATIK LAUNCHER V2 (ACTIVE MONITORING)
# Membunuh robot seketika jika STOP_SIGNAL terdeteksi
# ================================================================

import subprocess
import sys
import time
import os

# PATH CONFIG
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CURTAIN_SCRIPT = os.path.join(BASE_DIR, "safety_curtain.py")
STOP_FLAG = os.path.join(BASE_DIR, "STOP_SIGNAL")

def run_job(robot_script, args_list):
    print(f">>> [LAUNCHER] Target: {robot_script}")

    # Hapus sisa sinyal stop lama
    if os.path.exists(STOP_FLAG):
        try: os.remove(STOP_FLAG)
        except: pass

    # 1. NYALAKAN CURTAIN (Background)
    print(">>> [LAUNCHER] Membuka Safety Curtain...")
    curtain_process = subprocess.Popen([sys.executable, CURTAIN_SCRIPT])
    time.sleep(2) # Tunggu curtain siap

    # 2. JALANKAN ROBOT (Background juga, agar kita bisa monitor)
    print(">>> [LAUNCHER] Menjalankan Robot...")
    full_cmd = [sys.executable, robot_script] + args_list
    robot_process = subprocess.Popen(full_cmd)

    try:
        # 3. LOOPING MONITORING (NADI SISTEM)
        while True:
            # A. Cek apakah robot sudah selesai sendiri?
            if robot_process.poll() is not None:
                print(">>> [LAUNCHER] Robot selesai tugas.")
                break
            
            # B. Cek apakah Curtain mati atau File STOP ada?
            if os.path.exists(STOP_FLAG) or curtain_process.poll() is not None:
                print("\n>>> [LAUNCHER] !!! EMERGENCY STOP DETECTED !!!")
                print(">>> [LAUNCHER] Killing Robot Process...")
                
                # BUNUH ROBOT SEKETIKA
                robot_process.terminate()
                time.sleep(0.5)
                if robot_process.poll() is None: # Kalau bandel
                    robot_process.kill()
                
                print(">>> [LAUNCHER] Robot killed.")
                break
            
            # Cek setiap 0.1 detik
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n>>> [LAUNCHER] Interrupted by User (Terminal).")
        robot_process.kill()

    except Exception as e:
        print(f">>> [LAUNCHER] Error: {e}")

    finally:
        # 4. BERSIH-BERSIH
        print(">>> [LAUNCHER] Menutup Curtain & Membersihkan Sinyal...")
        
        # Pastikan Curtain mati
        if curtain_process.poll() is None:
            curtain_process.terminate()
        
        # Hapus file stop
        if os.path.exists(STOP_FLAG):
            try: os.remove(STOP_FLAG)
            except: pass

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python bin/run_with_curtain.py <script_robot> [args...]")
        sys.exit(1)

    target = sys.argv[1]
    
    # Validasi path
    if not os.path.exists(target):
        # Cek folder bin/
        alt_path = os.path.join(BASE_DIR, os.path.basename(target)) 
        if os.path.exists(alt_path): target = alt_path
        else:
            print(f"[ERROR] Script tidak ditemukan: {target}")
            sys.exit(1)

    run_job(target, sys.argv[2:])