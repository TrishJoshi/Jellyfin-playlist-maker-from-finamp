import os
import sys
import time
import json
import shutil

from config import IGNORE_SANITY_CHECK
from adb import run_adb_safe
from parser import hash_xml_content_desc, extract_playlist_info, extract_tracks_from_xml, get_playlists_on_screen

def extract_single_playlist(target_pl):
    playlist_name = target_pl["name"]
    expected_count = target_pl["count"]
    
    print(f"\n--- Extracting Playlist: '{playlist_name}' ({expected_count} tracks) ---")
    
    temp_xml = "/tmp/ui_dump_playlist.xml"
    run_adb_safe(["adb", "shell", "uiautomator", "dump", "/sdcard/ui_dump.xml"])
    run_adb_safe(["adb", "pull", "/sdcard/ui_dump.xml", temp_xml])
    
    pl_name, ex_count = extract_playlist_info(temp_xml)
    if not pl_name:
        print(f"  Failed to verify we are on the playlist page for '{playlist_name}'.")
        return False
        
    safe_dir_name = playlist_name.replace("/", "_")
    base_dir_name = os.path.join("playlists", safe_dir_name)
    dir_name = base_dir_name
    is_new_run = False
    
    if os.path.exists(base_dir_name):
        dir_name = base_dir_name + "_temp_run"
        is_new_run = True
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            
    os.makedirs(dir_name, exist_ok=True)
    
    i = 1
    target_xml = os.path.join(dir_name, f"dump_{i}.xml")
    shutil.move(temp_xml, target_xml)
    
    prev_hash = hash_xml_content_desc(target_xml)
    
    while True:
        run_adb_safe(["adb", "shell", "input", "swipe", "500", "2000", "500", "1200", "500"])
        time.sleep(1)
        i += 1
        print(f"  Dumping screen {i}... ", end="", flush=True)
        run_adb_safe(["adb", "shell", "uiautomator", "dump", "/sdcard/ui_dump.xml"])
        target_xml = os.path.join(dir_name, f"dump_{i}.xml")
        run_adb_safe(["adb", "pull", "/sdcard/ui_dump.xml", target_xml])
        
        current_hash = hash_xml_content_desc(target_xml)
        if current_hash == prev_hash:
            print("\n  Reached the bottom!")
            os.remove(target_xml)
            i -= 1
            break
        print("Saved.")
        prev_hash = current_hash
        
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
        
    print(f"  Extracted {len(all_tracks)} unique tracks to tracks.json")
    
    if expected_count is not None and len(all_tracks) != expected_count:
        if playlist_name in IGNORE_SANITY_CHECK:
            print(f"  WARNING: Sanity check failed (Expected {expected_count}, got {len(all_tracks)}) but '{playlist_name}' is in config.py! Proceeding.")
        else:
            print(f"  ERROR: SANITY CHECK FAILED! Expected {expected_count}, got {len(all_tracks)}.")
            print(f"  (Corrupted run deleted, will retry this playlist later if you run the script again).")
            shutil.rmtree(dir_name)
            return False
        
    if is_new_run:
        old_tracks_file = os.path.join(base_dir_name, "tracks.json")
        if os.path.exists(old_tracks_file):
            with open(old_tracks_file, "r", encoding="utf-8") as f:
                old_tracks = json.load(f)
            if old_tracks == all_tracks:
                shutil.rmtree(base_dir_name)
                os.rename(dir_name, base_dir_name)
            else:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                os.rename(dir_name, f"{base_dir_name} - {timestamp}")
        else:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            os.rename(base_dir_name, f"{base_dir_name} - old_{timestamp}")
            os.rename(dir_name, base_dir_name)
            
    print(f"  Successfully extracted {playlist_name}!")
    return True

def main():
    os.makedirs("playlists", exist_ok=True)
    temp_xml = "/tmp/ui_dump_list.xml"
    
    print("\n==========================================================")
    print("Welcome to the Autonomous Finamp Playlist Extractor!")
    user_input = input("Please navigate to the LIST of playlists page on your phone, then press Enter (or 'q' to quit): ").strip().lower()
    
    if user_input in ('q', 'quit'):
        print("Exiting.")
        sys.exit(0)

    print("\n[Phase 1] Scrolling through the playlists page to build a master list...")
    master_playlists = []
    seen_playlist_names = set()
    prev_hash = ""
    
    while True:
        run_adb_safe(["adb", "shell", "uiautomator", "dump", "/sdcard/ui_dump.xml"])
        run_adb_safe(["adb", "pull", "/sdcard/ui_dump.xml", temp_xml])
        
        current_hash = hash_xml_content_desc(temp_xml)
        
        on_screen = get_playlists_on_screen(temp_xml)
        for pl in on_screen:
            if pl["name"] not in seen_playlist_names:
                seen_playlist_names.add(pl["name"])
                master_playlists.append(pl)
                print(f"  Found: {pl['name']} ({pl['count']} tracks)")
                
        if current_hash == prev_hash and prev_hash != "":
            print("Reached bottom of playlists list!")
            break
            
        prev_hash = current_hash
        run_adb_safe(["adb", "shell", "input", "swipe", "500", "2000", "500", "700", "500"])
        time.sleep(1)
        
    print(f"\nTotal unique playlists discovered: {len(master_playlists)}")
    
    playlists_to_extract = []
    for pl in master_playlists:
        safe_name = pl["name"].replace("/", "_")
        tracks_file = os.path.join("playlists", safe_name, "tracks.json")
        if os.path.exists(tracks_file):
            with open(tracks_file, "r", encoding="utf-8") as f:
                t = json.load(f)
            if len(t) == pl["count"] or pl["name"] in IGNORE_SANITY_CHECK:
                print(f"Skipping '{pl['name']}' (Already successfully extracted).")
                continue
        playlists_to_extract.append(pl)
        
    if not playlists_to_extract:
        print("\nAll playlists are already successfully extracted! Exiting.")
        sys.exit(0)
        
    print(f"\nNeed to extract {len(playlists_to_extract)} playlists.")
    print("Automatically scrolling back to the top of the playlists page...")
    
    prev_hash = ""
    while True:
        run_adb_safe(["adb", "shell", "uiautomator", "dump", "/sdcard/ui_dump.xml"])
        run_adb_safe(["adb", "pull", "/sdcard/ui_dump.xml", temp_xml])
        
        current_hash = hash_xml_content_desc(temp_xml)
        if current_hash == prev_hash and prev_hash != "":
            print("Reached the top of the playlists list!")
            break
            
        prev_hash = current_hash
        run_adb_safe(["adb", "shell", "input", "swipe", "500", "700", "500", "2000", "500"])
        time.sleep(1)
    
    print("\n[Phase 2] Autonomous extraction beginning...")
    
    for target_pl in playlists_to_extract:
        found_x = None
        found_y = None
        prev_hash = ""
        
        while True:
            run_adb_safe(["adb", "shell", "uiautomator", "dump", "/sdcard/ui_dump.xml"])
            run_adb_safe(["adb", "pull", "/sdcard/ui_dump.xml", temp_xml])
            
            current_hash = hash_xml_content_desc(temp_xml)
            on_screen = get_playlists_on_screen(temp_xml)
            
            is_bottom = (current_hash == prev_hash and prev_hash != "")
            
            for p in on_screen:
                if p["name"] == target_pl["name"]:
                    if not is_bottom and (p["y"] > 2200 or p["y"] < 250):
                        break
                    found_x = p["x"]
                    found_y = p["y"]
                    break
                    
            if found_x is not None:
                break
                
            if is_bottom:
                print(f"Could not find '{target_pl['name']}' on screen. Skipping for now.")
                break
                
            prev_hash = current_hash
            run_adb_safe(["adb", "shell", "input", "swipe", "500", "2000", "500", "700", "500"])
            time.sleep(1)
            
        if found_x is None:
            continue
            
        print(f"  Tapping on playlist at ({found_x}, {found_y})...")
        run_adb_safe(["adb", "shell", "input", "tap", str(found_x), str(found_y)])
        time.sleep(2)
        
        extract_single_playlist(target_pl)
        
        run_adb_safe(["adb", "shell", "input", "keyevent", "4"])
        time.sleep(2)
        
    print("\n==========================================================")
    print("All tasks completed!")

if __name__ == "__main__":
    main()
