import argparse
from bin.robot_maru import MaruRobot
from datetime import datetime

def print_header():
    print("="*92)
    print(" BATIK SYSTEM | MARU AUTOMATION | FINAL GRANULAR DVOR/DME")
    print("="*92)
    print(f"{'TIME':<10} | {'STATION':<15} | {'ACTION':<45} | STATUS")
    print("-"*92)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--DVOR", action="store_true", help="Run MARU 220 (DVOR)")
    parser.add_argument("--DME", action="store_true", help="Run MARU 320 (DME)")

    args = parser.parse_args()

    print_header()
    bot = MaruRobot()

    if args.DVOR:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] DVOR        | START")
        bot.run_dvor()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] DVOR        | DONE")
    elif args.DME:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] DME         | START")
        bot.run_dme()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] DME         | DONE")
    else:
        print("Gunakan:  python run_maru.py --DVOR   atau   python run_maru.py --DME")
