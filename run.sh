#!/bin/bash

# Ensure we have the playlists directory
mkdir -p playlists

while true; do
    echo ""
    echo "=========================================================="
    read -p "Navigate to a playlist in Finamp and press Enter (or 'q' to quit): " user_input
    
    if [[ "$user_input" == "q" || "$user_input" == "quit" ]]; then
        echo "Exiting."
        break
    fi

    echo "Scanning current screen to identify playlist..."
    
    # Dump the screen
    adb shell uiautomator dump /sdcard/ui_dump.xml > /dev/null 2>&1
    
    # Check if adb command succeeded (handles offline devices)
    if [ $? -ne 0 ]; then
        echo "Error: ADB device offline or unresponsive. Attempting to restart adb server..."
        adb kill-server && adb start-server
        sleep 3
        echo "Please try again."
        continue
    fi

    adb pull /sdcard/ui_dump.xml /tmp/ui_dump_first.xml > /dev/null 2>&1

    # Extract playlist name using the virtual environment's Python
    playlist_name=$(venv/bin/python -c '
import xml.etree.ElementTree as ET
import re
import sys

try:
    tree = ET.parse("/tmp/ui_dump_first.xml")
    prev = ""
    for node in tree.iter("node"):
        desc = node.get("content-desc", "")
        if desc:
            if re.search(r"\d+ Track(s)? \(\d+:\d+\)", desc):
                print(prev.strip())
                sys.exit(0)
            prev = desc
except Exception:
    pass
sys.exit(1)
')

    if [ -z "$playlist_name" ]; then
        echo "Error: Could not identify a playlist on the current screen."
        echo "Make sure you are on a Finamp playlist page (needs to contain a 'X Tracks (MM:SS)' element)."
        continue
    fi

    echo "Detected Playlist: '$playlist_name'"
    
    # Create a safe directory name (replace slashes just in case)
    safe_dir_name=$(echo "$playlist_name" | tr '/' '_')
    dir_name="playlists/$safe_dir_name"
    
    if [ -d "$dir_name" ]; then
        echo "Warning: Directory '$dir_name' already exists. Overwriting/Appending dumps..."
    fi
    mkdir -p "$dir_name"
    
    i=1
    mv /tmp/ui_dump_first.xml "$dir_name/dump_$i.xml"
    
    # Hash only text fields to ignore status bar changes
    prev_hash=$(grep -o 'text="[^"]*"' "$dir_name/dump_$i.xml" | md5sum | awk '{print $1}')
    
    echo "Saved dump_$i.xml"
    
    while true; do
        # Swipe up from y=2000 to y=500 over 500ms
        adb shell input swipe 500 2000 500 500 500
        sleep 1
        
        ((i++))
        echo -n "Dumping screen $i... "
        adb shell uiautomator dump /sdcard/ui_dump.xml > /dev/null 2>&1
        adb pull /sdcard/ui_dump.xml "$dir_name/dump_$i.xml" > /dev/null 2>&1
        
        current_hash=$(grep -o 'text="[^"]*"' "$dir_name/dump_$i.xml" | md5sum | awk '{print $1}')
        
        # If the text hasn't changed since the last swipe, we hit the bottom
        if [[ "$current_hash" == "$prev_hash" ]]; then
            echo "Reached the bottom!"
            rm "$dir_name/dump_$i.xml" # clean up the duplicate last frame
            break
        fi
        
        echo "Saved."
        prev_hash=$current_hash
    done
    
    echo "Finished extracting '$playlist_name'. Total unique screens: $((i-1))"
    echo "Directory: $dir_name"
done
