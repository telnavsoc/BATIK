# FILE: bin/service_watchdog.py
import subprocess
import time
import win32gui
import win32con
import win32api
import sys
import os

# Import Config Pusat
import config 

# --- KONFIGURASI LAYOUT ---
# Koordinat tetap disini karena spesifik untuk layout monitor
APPS = {
    "DASHBOARD": {
        "title": "NOC Monitoring System",
        "path": config.PATH_DASHBOARD,
        "workdir": config.PATH_DASHBOARD_WD,
        "x": 2100, "y": -1080, "w": 1310, "h": 315,
        "startup_delay": 2
    },
    "RCSU": {
        "title": "Model 2238 RCSU", 
        "path": config.PATH_RCSU,
        "x": 1560, "y": -1070, "w": 567, "h": 304,
        "startup_delay": 5
    },
    "MARU_310": {
        "title": "MARU 310",
        "path": config.PATH_MARU_310,
        "ip": config.IP_MARU_310,
        "x": 1566, "y": -780, "w": 1024, "h": 745,
        "startup_delay": 2
    },
    "MARU_220": {
        "title": "MARU 220",
        "path": config.PATH_MARU_220,
        "ip": config.IP_MARU_220,
        "x": 2368, "y": -780, "w": 1024, "h": 745,
        "startup_delay": 8
    }
}

ERROR_POPUPS = ["MOPHIENS", "Login to MARU 220", "Error", "Warning"]

# --- CORE TOOLS ---
def ping_check(ip):
    try:
        subprocess.check_output(f"ping -n 1 -w 1000 {ip}", shell=True, creationflags=0x08000000)
        return True
    except: return False

def find_window_handle(partial_title):
    hwnd_list = []
    def callback(h, _):
        if win32gui.IsWindowVisible(h):
            title = win32gui.GetWindowText(h)
            if partial_title.lower() in title.lower():
                hwnd_list.append(h)
        return True
    try:
        win32gui.EnumWindows(callback, None)
        return hwnd_list[0] if hwnd_list else 0
    except: return 0

def move_window_force(hwnd, x, y, w, h):
    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.5)
        win32gui.SetWindowPos(hwnd, 0, x, y, w, h, 0x0040)
        return True
    except: return False

def kill_process(process_name):
    print(f"   💀 KILL: {process_name}")
    try:
        subprocess.run(f"taskkill /F /IM \"{process_name}\"", shell=True, creationflags=0x08000000)
        time.sleep(2)
        return True
    except: return False

def smart_sleep(seconds):
    while seconds > 0:
        m, s = divmod(seconds, 60)
        print(f"   ⏳ Next Check: {'{:02d}:{:02d}'.format(m, s)}   ", end="\r") 
        time.sleep(1)
        seconds -= 1
    print(" " * 30, end="\r")

# --- LOGIC ---
def check_and_kill_errors():
    for error_title in ERROR_POPUPS:
        if win32gui.FindWindow(None, error_title) != 0:
            print(f"\n   🚨 ERROR FOUND: '{error_title}' -> Restarting MARU 220...")
            kill_process("MARU 220.exe") 
            return True
    return False

def run_rcsu_automation(hwnd, mode="loop"):
    if mode == "startup":
        clicks, interval = 3, 5
    else:
        clicks, interval = 1, 0

    childs = []
    try: win32gui.EnumChildWindows(hwnd, lambda h, p: childs.append(h), None)
    except: pass

    btn_hwnd = None
    for h in childs:
        if "Button" in win32gui.GetClassName(h):
            btn_hwnd = h; break
    
    if not btn_hwnd: return

    if win32gui.IsWindowEnabled(btn_hwnd):
        if mode == "startup": print(f"   🤖 RCSU Init: {clicks}x Klik...")
        for i in range(clicks):
            win32api.SendMessage(btn_hwnd, 0xF5, 0, 0)
            if i < clicks - 1 and interval > 0: time.sleep(interval)

def ensure_app_state(key):
    cfg = APPS[key]
    hwnd = find_window_handle(cfg["title"])
    
    if hwnd == 0: # STARTUP
        if "ip" in cfg and not ping_check(cfg["ip"]): return
        print(f"   🚀 Launching: {key}")
        try:
            cmd = cfg["path"]
            wd = cfg.get("workdir", None)
            if wd: subprocess.Popen(cmd, cwd=wd)
            else: subprocess.Popen(cmd)
        except Exception as e:
            print(f"   ❌ Fail: {e}"); return

        for _ in range(60):
            hwnd = find_window_handle(cfg["title"])
            if hwnd != 0: break
            time.sleep(0.5)
        
        if hwnd == 0: return 
        time.sleep(cfg["startup_delay"]) 
        hwnd = find_window_handle(cfg["title"])
        if hwnd:
            move_window_force(hwnd, cfg["x"], cfg["y"], cfg["w"], cfg["h"])
            if key == "RCSU": run_rcsu_automation(hwnd, mode="startup")

    else: # WATCHDOG
        try:
            rect = win32gui.GetWindowRect(hwnd)
            curr = (rect[0], rect[1], rect[2]-rect[0], rect[3]-rect[1])
            target = (cfg["x"], cfg["y"], cfg["w"], cfg["h"])
            if any(abs(c - t) > 10 for c, t in zip(curr, target)):
                print(f"   🔧 Fix Layout: {key}")
                move_window_force(hwnd, *target)
            if key == "RCSU": run_rcsu_automation(hwnd, mode="loop")
        except: pass

if __name__ == "__main__":
    print(f"🛡️ BATIK WATCHDOG ACTIVE [15m Interval]")
    print(f"----------------------------------------")
    try:
        while True:
            t_str = time.strftime('%H:%M:%S')
            print(f"[{t_str}] Checking...", end="\r")
            check_and_kill_errors()
            for app in ["DASHBOARD", "RCSU", "MARU_310", "MARU_220"]:
                ensure_app_state(app)
            smart_sleep(900)
    except KeyboardInterrupt:
        sys.exit()