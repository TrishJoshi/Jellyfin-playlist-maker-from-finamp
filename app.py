import os
import re
import sys
import glob
import requests

# --- CONFIGURATION ---
JELLYFIN_URL = "http://100.76.51.22:8096"
USERNAME = "CBOT"
PASSWORD = "OKKKwhexm1ZSGg"

def get_auth_token():
    auth_data = {"Username": USERNAME, "Pw": PASSWORD}
    headers = {
        "X-Emby-Authorization": 'MediaBrowser Client="Python", Device="Script", DeviceId="123", Version="1.0"'
    }
    resp = requests.post(f"{JELLYFIN_URL}/Users/authenticatebyname", json=auth_data, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    return data['AccessToken'], data['User']['Id']

def search_jellyfin_for_track(title, artist, user_id, headers):
    params = {
        "searchTerm": title,
        "IncludeItemTypes": "Audio",
        "Recursive": "true"
    }
    resp = requests.get(f"{JELLYFIN_URL}/Users/{user_id}/Items", headers=headers, params=params)
    results = resp.json().get('Items', [])
    
    if not results:
        return None
        
    # Attempt strict matching first (Title + Artist)
    for item in results:
        jellyfin_title = item.get('Name', '')
        jellyfin_artists = [a.lower() for a in item.get('Artists', [])]
        
        if title.lower() == jellyfin_title.lower() and artist.lower() in jellyfin_artists:
            return item['Id']
            
    # Fallback to strict title match
    for item in results:
        if item.get('Name', '').lower() == title.lower():
            return item['Id']

    # Final fallback: return top search result
    return results[0]['Id']

def main():
    if len(sys.argv) < 3:
        print("Usage: python rebuild.py \"Playlist Name\" /path/to/xml/dumps")
        sys.exit(1)

    playlist_name = sys.argv[1]
    dump_dir = sys.argv[2]
    
    print("Authenticating with Jellyfin...")
    token, user_id = get_auth_token()
    headers = {"X-Emby-Token": token}
    
    xml_files = sorted(glob.glob(os.path.join(dump_dir, "*.xml")))
    extracted_tracks = []
    seen_titles = set()
    
    for xml_file in xml_files:
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            
            # Iterate through all UI nodes
            for node in root.iter('node'):
                desc = node.get('content-desc', '')
                
                # Finamp track nodes contain newlines and end with "Seconds"
                if desc and '\n' in desc and 'Seconds' in desc:
                    parts = desc.split('\n')
                    if len(parts) >= 2:
                        title = parts[0].strip()
                        artist = parts[1].strip()
                        
                        if title not in seen_titles:
                            seen_titles.add(title)
                            extracted_tracks.append((title, artist))
        except ET.ParseError:
            print(f"Skipping malformed XML file: {xml_file}")

    print(f"Extracted {len(extracted_tracks)} unique tracks from dumps.")
    track_ids = []
    
    for title, artist in extracted_tracks:
        track_id = search_jellyfin_for_track(title, artist, user_id, headers)
        if track_id:
            track_ids.append(track_id)
            print(f"  [Match] {title} - {artist}")
        else:
            print(f"  [Failed] Could not find: {title} - {artist}")

    if not track_ids:
        print("No tracks found in Jellyfin. Aborting.")
        sys.exit(1)

    print(f"\nCreating playlist '{playlist_name}'...")
    create_payload = {"Name": playlist_name, "UserId": user_id, "MediaType": "Audio"}
    create_resp = requests.post(f"{JELLYFIN_URL}/Playlists", json=create_payload, headers=headers)
    create_resp.raise_for_status()
    playlist_id = create_resp.json()['Id']
    
    print(f"Populating playlist with {len(track_ids)} tracks...")
    ids_str = ",".join(track_ids)
    add_url = f"{JELLYFIN_URL}/Playlists/{playlist_id}/Items?ItemIds={ids_str}"
    requests.post(add_url, headers=headers).raise_for_status()
    
    print("Done.")

if __name__ == "__main__":
    main()
