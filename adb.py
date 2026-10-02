import subprocess
import time

def run_adb_safe(cmd):
    """Run an ADB command safely, restarting the server on failure."""
    while True:
        try:
            subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except subprocess.CalledProcessError:
            print(f"\nADB Error with '{' '.join(cmd)}'. Restarting ADB and retrying in 3s...")
            subprocess.run(["adb", "kill-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["adb", "start-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(3)
