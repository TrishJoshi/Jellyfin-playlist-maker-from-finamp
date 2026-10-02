import os
import sys
import time
import subprocess
import re
import hashlib
import xml.etree.ElementTree as ET

def run_adb(cmd):
    try:
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False

def hash_xml_text(filepath):
    """Hashes only the text='...' attributes from the XML to ignore status bar changes"""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        texts = re.findall(r'text="([^"]*)"', content)
        return hashlib.md5("\n".join(texts).encode('utf-8')).hexdigest()
    except Exception:
        return ""

def extract_playlist_name(filepath):
    try:
        tree = ET.parse(filepath)
        prev_desc = ""
        for node in tree.iter('node'):
            desc = node.get('content-desc', '')
            if desc:
                if re.search(r'\d+ Track(s)? \(\d+:\d+\)', desc):
                    return prev_desc.strip()
                prev_desc = desc
    except ET.ParseError:
        pass
    return None

def main():
    os.makedirs("playlists", exist_ok=True)
    temp_xml = "/tmp/ui_dump_first.xml"

    while True:
        print("\n==========================================================")
        user_input = input("Navigate to a playlist in Finamp and press Enter (or 'q' to quit): ").strip().lower()
        
        if user_input in ('q', 'quit'):
            print("Exiting.")
            break

        print("Scanning current screen to identify playlist...")
        
        if not run_adb(["adb", "shell", "uiautomator", "dump", "/sdcard/ui_dump.xml"]):
            print("Error: ADB device offline or unresponsive. Attempting to restart adb server...")
            subprocess.run(["adb", "kill-server"])
            subprocess.run(["adb", "start-server"])
            time.sleep(3)
            print("Please try again.")
            continue
            
        run_adb(["adb", "pull", "/sdcard/ui_dump.xml", temp_xml])

        playlist_name = extract_playlist_name(temp_xml)
        
        if not playlist_name:
            print("Error: Could not identify a playlist on the current screen.")
            print("Make sure you are on a Finamp playlist page (needs to contain a 'X Tracks (MM:SS)' element).")
            continue
            
        print(f"Detected Playlist: '{playlist_name}'")
        
        safe_dir_name = playlist_name.replace("/", "_")
        dir_name = os.path.join("playlists", safe_dir_name)
        
        if os.path.exists(dir_name):
            print(f"Warning: Directory '{dir_name}' already exists. Overwriting/Appending dumps...")
        os.makedirs(dir_name, exist_ok=True)
        
        i = 1
        target_xml = os.path.join(dir_name, f"dump_{i}.xml")
        os.rename(temp_xml, target_xml)
        
        prev_hash = hash_xml_text(target_xml)
        print(f"Saved dump_{i}.xml")
        
        while True:
            # Swipe up from y=2000 to y=500 over 500ms
            run_adb(["adb", "shell", "input", "swipe", "500", "2000", "500", "500", "500"])
            time.sleep(1)
            
            i += 1
            print(f"Dumping screen {i}... ", end="", flush=True)
            
            run_adb(["adb", "shell", "uiautomator", "dump", "/sdcard/ui_dump.xml"])
            target_xml = os.path.join(dir_name, f"dump_{i}.xml")
            run_adb(["adb", "pull", "/sdcard/ui_dump.xml", target_xml])
            
            current_hash = hash_xml_text(target_xml)
            
            if current_hash == prev_hash:
                print("\nReached the bottom!")
                os.remove(target_xml)
                break
                
            print("Saved.")
            prev_hash = current_hash
            
        print(f"Finished extracting '{playlist_name}'. Total unique screens: {i-1}")
        print(f"Directory: {dir_name}")

if __name__ == "__main__":
    main()
