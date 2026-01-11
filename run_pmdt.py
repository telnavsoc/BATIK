import os, sys, subprocess

BASE = os.path.dirname(os.path.abspath(__file__))
ROBOT = os.path.join(BASE, "bin", "robot_maru.py")

if __name__ == "__main__":
    if "--DVOR" in sys.argv:
        subprocess.call(["python", ROBOT, "--DVOR"])
    elif "--DME" in sys.argv:
        subprocess.call(["python", ROBOT, "--DME"])
    else:
        print("Gunakan: python run_maru.py --DVOR atau --DME")
