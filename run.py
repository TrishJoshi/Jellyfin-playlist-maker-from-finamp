import os
import sys
import time
import subprocess
import re
import hashlib
import xml.etree.ElementTree as ET
import json
import shutil

def run_adb(cmd):
    try:
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False

def hash_xml_content_desc(filepath):
    """Hashes only the content-desc attributes from the XML to ignore status bar changes"""
    try:
        tree = ET.parse(filepath)
        content = ""
        for node in tree.iter('node'):
            desc = node.get('content-desc', '')
            if desc:
                content += desc + "\n"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    except Exception:
        # Fallback to regex if parsing fails
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            descs = re.findall(r'content-desc="([^"]*)"', content)
            return hashlib.md5("\n".join(descs).encode('utf-8')).hexdigest()
        except:
            return ""

def extract_playlist_info(filepath):
    """Returns (playlist_name, expected_track_count)"""
    try:
        tree = ET.parse(filepath)
        prev_desc = ""
        for node in tree.iter('node'):
            desc = node.get('content-desc', '')
            if desc:
                match = re.search(r'(\d+) Track(s)? \([\d:]+\)', desc)
                if match:
                    return prev_desc.strip(), int(match.group(1))
                prev_desc = desc
    except ET.ParseError:
        pass
    return None, None

def extract_tracks_from_xml(filepath):
    tracks = []
    try:
        tree = ET.parse(filepath)
        for node in tree.iter('node'):
            desc = node.get('content-desc', '')
            if desc and '\n' in desc and 'Seconds' in desc:
                parts = desc.split('\n')
                if len(parts) >= 2:
                    title = parts[0].strip()
                    artist = parts[1].strip()
                    tracks.append({"title": title, "artist": artist})
    except ET.ParseError:
        pass
    return tracks

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

        playlist_name, expected_count = extract_playlist_info(temp_xml)
        
        if not playlist_name:
            print("Error: Could not identify a playlist on the current screen.")
            print("Make sure you are on a Finamp playlist page (needs to contain a 'X Tracks (MM:SS)' element).")
            continue
            
        print(f"Detected Playlist: '{playlist_name}' (Expected Tracks: {expected_count})")
        
        safe_dir_name = playlist_name.replace("/", "_")
        base_dir_name = os.path.join("playlists", safe_dir_name)
        dir_name = base_dir_name
        is_new_run = False
        
        if os.path.exists(base_dir_name):
            print(f"Warning: Directory '{base_dir_name}' already exists. Creating a temporary directory to compare later.")
            dir_name = base_dir_name + "_temp_run"
            is_new_run = True
            if os.path.exists(dir_name):
                shutil.rmtree(dir_name)
                
        os.makedirs(dir_name, exist_ok=True)
        
        i = 1
        target_xml = os.path.join(dir_name, f"dump_{i}.xml")
        shutil.move(temp_xml, target_xml)
        
        prev_hash = hash_xml_content_desc(target_xml)
        print(f"Saved dump_{i}.xml")
        
        while True:
            # Swipe up from y=2000 to y=1300 over 500ms (shorter scroll)
            run_adb(["adb", "shell", "input", "swipe", "500", "2000", "500", "1300", "500"])
            time.sleep(1)
            
            i += 1
            print(f"Dumping screen {i}... ", end="", flush=True)
            
            run_adb(["adb", "shell", "uiautomator", "dump", "/sdcard/ui_dump.xml"])
            target_xml = os.path.join(dir_name, f"dump_{i}.xml")
            run_adb(["adb", "pull", "/sdcard/ui_dump.xml", target_xml])
            
            current_hash = hash_xml_content_desc(target_xml)
            
            if current_hash == prev_hash:
                print("\nReached the bottom!")
                os.remove(target_xml)
                i -= 1
                break
                
            print("Saved.")
            prev_hash = current_hash
            
        print(f"Finished scrolling. Extracting and deduplicating tracks...")
        
        all_tracks = []
        seen = set()
        for idx in range(1, i + 1):
            xml_file = os.path.join(dir_name, f"dump_{idx}.xml")
            for t in extract_tracks_from_xml(xml_file):
                key = (t['title'], t['artist'])
                if key not in seen:
                    seen.add(key)
                    all_tracks.append(t)
                    
        tracks_json = os.path.join(dir_name, "tracks.json")
        with open(tracks_json, "w", encoding="utf-8") as f:
            json.dump(all_tracks, f, indent=2, ensure_ascii=False)
            
        print(f"Extracted {len(all_tracks)} unique tracks to tracks.json")
        
        if expected_count is not None and len(all_tracks) != expected_count:
            print("\n" + "!"*60)
            print(f"ERROR: SANITY CHECK FAILED!")
            print(f"Playlist header claims {expected_count} tracks, but we only extracted {len(all_tracks)}.")
            print("This can happen if a scroll skipped tracks or if the scroll stopped early.")
            print("!"*60)
            input("\nPlease scroll back to the TOP of the playlist on your phone, then press Enter to retry...")
            shutil.rmtree(dir_name)
            continue
            
        if is_new_run:
            old_tracks_file = os.path.join(base_dir_name, "tracks.json")
            
            if os.path.exists(old_tracks_file):
                with open(old_tracks_file, "r", encoding="utf-8") as f:
                    old_tracks = json.load(f)
                
                if old_tracks == all_tracks:
                    print("Data is identical to existing playlist folder. Replacing old folder.")
                    shutil.rmtree(base_dir_name)
                    os.rename(dir_name, base_dir_name)
                    dir_name = base_dir_name
                else:
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    new_final_name = f"{base_dir_name} - {timestamp}"
                    print(f"Data is different! Keeping both. New run saved as '{new_final_name}'.")
                    os.rename(dir_name, new_final_name)
                    dir_name = new_final_name
            else:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                new_final_name = f"{base_dir_name} - {timestamp}"
                print(f"Data is different or tracks.json missing from old folder! Keeping both. New run saved as '{new_final_name}'.")
                os.rename(dir_name, new_final_name)
                dir_name = new_final_name
                
        print(f"Directory: {dir_name}")

if __name__ == "__main__":
    main()
