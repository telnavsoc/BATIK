# FILE: bin/run_all.py
# ================================================================
# BATIK SEQUENCER (UPDATED FOR AUTO CLOSE)
# Menjalankan semua robot secara berurutan (Queue)
# ================================================================

import subprocess
import sys
import os
import time

# Setup Path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PMDT_SCRIPT = os.path.join(BASE_DIR, "robot_pmdt.py")
MARU_SCRIPT = os.path.join(BASE_DIR, "robot_maru.py")

def run_step(script_path, args, step_name):
    print(f"\n{'='*60}")
    print(f" >>> [SEQUENCE] STEP: {step_name}")
    print(f"{'='*60}")
    
    cmd = [sys.executable, script_path] + args
    
    # Run blocking (tunggu sampai selesai baru lanjut)
    ret_code = subprocess.call(cmd)
    
    if ret_code == 0:
        print(f" >>> [SUCCESS] {step_name} Selesai.")
    else:
        print(f" >>> [WARNING] {step_name} Gagal/Error (Code: {ret_code}).")
    
    print(" >>> Cooldown 3 detik...")
    time.sleep(3)

if __name__ == "__main__":
    print(">>> BATIK RUN ALL SEQUENCE STARTED")
    
    # 1. GROUP ILS (PMDT)
    # Gunakan --keep-open untuk LOC, GP, MM agar aplikasi tidak tutup
    # Aplikasi PMDT akan tetap terbuka dan lanjut ke alat berikutnya
    run_step(PMDT_SCRIPT, ["--target", "LOC", "--keep-open"], "ILS - LOCALIZER")
    run_step(PMDT_SCRIPT, ["--target", "GP", "--keep-open"],  "ILS - GLIDE PATH")
    run_step(PMDT_SCRIPT, ["--target", "MM", "--keep-open"],  "ILS - MIDDLE MARKER")
    
    # Outer Marker TANPA --keep-open
    # Maka PMDT akan auto-close setelah OM selesai
    run_step(PMDT_SCRIPT, ["--target", "OM"], "ILS - OUTER MARKER")
    
    # 2. GROUP DVOR/DME (MARU)
    # Maru biasanya sudah handle close sendiri atau single session per app
    # Jika perlu auto-close untuk MARU juga, bisa disesuaikan di robot_maru.py
    run_step(MARU_SCRIPT, ["--DVOR"], "NAV - DVOR")
    run_step(MARU_SCRIPT, ["--DME"],  "NAV - DME")
    
    print("\n>>> ALL TASKS COMPLETED.")