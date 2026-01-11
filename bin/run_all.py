# FILE: bin/run_all.py
# ================================================================
# BATIK SEQUENCER
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
    
    # 1. GROUP ILS
    run_step(PMDT_SCRIPT, ["--target", "LOC"], "ILS - LOCALIZER")
    run_step(PMDT_SCRIPT, ["--target", "GP"],  "ILS - GLIDE PATH")
    run_step(PMDT_SCRIPT, ["--target", "MM"],  "ILS - MIDDLE MARKER")
    run_step(PMDT_SCRIPT, ["--target", "OM"],  "ILS - OUTER MARKER")
    
    # 2. GROUP DVOR/DME
    run_step(MARU_SCRIPT, ["--DVOR"], "NAV - DVOR")
    run_step(MARU_SCRIPT, ["--DME"],  "NAV - DME")
    
    print("\n>>> ALL TASKS COMPLETED.")