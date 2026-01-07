import subprocess
import time
import win32gui
import win32con
import win32process
import psutil
import sys
import os

# --- KONFIGURASI ---
PMDT_CONFIG = {
    "path": r"D:\ILS APP\PMDT v8.7.2.0\PMDT.exe",
    "process_name": "PMDT.exe",  # KITA CARI BERDASARKAN NAMA EXE
    "x": 0,    
    "y": 0,    
}

# --- HELPER FUNCTIONS ---

def get_process_name_by_hwnd(hwnd):
    """Mendapatkan nama file .exe dari sebuah jendela."""
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        process = psutil.Process(pid)
        return process.name()
    except:
        return ""

def find_pmdt_handle():
    """Mencari jendela KHUSUS milik PMDT.exe"""
    hwnd_found = 0
    
    def callback(h, _):
        nonlocal hwnd_found
        if win32gui.IsWindowVisible(h):
            # Cek Nama Proses-nya (Lebih Akurat dari Judul)
            proc_name = get_process_name_by_hwnd(h)
            
            if PMDT_CONFIG["process_name"].lower() == proc_name.lower():
                # Pastikan ini jendela utama (biasanya punya judul)
                if win32gui.GetWindowText(h):
                    hwnd_found = h
                    return False # Stop searching
        return True
    
    try:
        win32gui.EnumWindows(callback, None)
    except: pass
    
    return hwnd_found

def force_position(hwnd):
    """Memaksa jendela ke posisi (0,0) TANPA mengubah ukuran."""
    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.5)
            
        # 0x0041 = SWP_SHOWWINDOW | SWP_NOSIZE
        win32gui.SetWindowPos(hwnd, 0, 
                              PMDT_CONFIG["x"], PMDT_CONFIG["y"], 
                              0, 0, 
                              0x0041)
        
        print(f"   🔒 Posisi PMDT dikunci di: {PMDT_CONFIG['x']},{PMDT_CONFIG['y']}")
        return True
    except Exception as e:
        print(f"   ⚠️ Gagal atur posisi: {e}")
        return False

def launch_app():
    print("🚀 Mempersiapkan Aplikasi PMDT...")
    
    # 1. Cek berdasarkan NAMA PROCESS (PMDT.exe)
    hwnd = find_pmdt_handle()
    
    if hwnd == 0:
        print(f"   📂 Membuka {PMDT_CONFIG['process_name']}...")
        try:
            subprocess.Popen(PMDT_CONFIG["path"])
            print("   ⏳ Menunggu jendela muncul...")
            
            # Loop tunggu
            for _ in range(30): 
                hwnd = find_pmdt_handle()
                if hwnd != 0: break
                time.sleep(0.5)
            
            if hwnd == 0:
                print("   ❌ Timeout: Aplikasi tidak terbuka.")
                return False
                
            time.sleep(2) 
        except Exception as e:
            print(f"   ❌ Error launch: {e}")
            return False

    # 2. Kunci Posisi
    force_position(hwnd)
    
    # Bawa ke depan
    try:
        win32gui.SetForegroundWindow(hwnd)
    except: pass
    
    print("✅ PMDT Siap. Silakan jalankan 'calibration_tool.py' sekarang.")
    return True

if __name__ == "__main__":
    launch_app()