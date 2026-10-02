#!/bin/bash
prev_hash=""
i=1

while true; do
    echo "Dumping screen $i..."
    adb shell uiautomator dump /sdcard/ui_dump.xml > /dev/null 2>&1
    adb pull /sdcard/ui_dump.xml ./dump_$i.xml > /dev/null 2>&1
    
    # Extract only the text fields to ignore status bar clock/battery changes, then hash it
    current_hash=$(grep -o 'text="[^"]*"' ./dump_$i.xml | md5sum | awk '{print $1}')
    
    # If the text hasn't changed since the last swipe, we hit the bottom
    if [[ "$current_hash" == "$prev_hash" ]]; then
        echo "Reached the bottom! (Screen $i is identical to $((i-1)))"
        rm ./dump_$i.xml # clean up the duplicate last frame
        break
    fi
    
    prev_hash=$current_hash
    
    # Swipe up from y=2000 to y=500 over 500ms
    adb shell input swipe 500 2000 500 500 500
    sleep 1
    ((i++))
done
