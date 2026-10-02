import os
import re
import sys
import glob
import requests
import xml.etree.ElementTree as ET
import json
import time

# --- CONFIGURATION ---
JELLYFIN_URL = "http://100.76.51.22:8096"
USERNAME = "CBOT"
PASSWORD = "OKKKwhexm1ZSGg"

def retry_request(method, url, **kwargs):
    backoffs = [5, 15, 30]
    for attempt, wait in enumerate(backoffs + [0]):
        try:
            resp = method(url, **kwargs)
            resp.raise_for_status()
            return resp
        except (requests.exceptions.Timeout, requests.exceptions.HTTPError) as e:
            if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code not in (502, 503, 504):
                raise
            if attempt == len(backoffs):
                raise
            print(f"API Error ({e}). Retrying in {wait}s...")
            time.sleep(wait)

def get_auth_token():
    auth_data = {"Username": USERNAME, "Pw": PASSWORD}
    headers = {
        "Authorization": 'MediaBrowser Client="Script", Device="Agent", DeviceId="1", Version="1.0"'
    }
    resp = retry_request(requests.post, f"{JELLYFIN_URL}/Users/authenticatebyname", json=auth_data, headers=headers)
    data = resp.json()
    return data['AccessToken'], data['User']['Id']

def search_jellyfin_for_track(title, artist, user_id, headers):
    def do_search(s_term):
        params = {
            "searchTerm": s_term,
            "IncludeItemTypes": "Audio",
            "Recursive": "true"
        }
        resp = retry_request(requests.get, f"{JELLYFIN_URL}/Users/{user_id}/Items", headers=headers, params=params)
        return resp.json().get('Items', [])

    results = do_search(title)
    
    if results:
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
    else:
        # Fallback search: Drop Artist requirement, trim searchTerm to alphanumeric before parenthesis
        fallback_title = title.split('(')[0].strip()
        fallback_results = do_search(fallback_title)
        if fallback_results:
            return fallback_results[0]['Id']
        return None

def main():
    if len(sys.argv) < 3:
        print("Usage: python app.py \"Playlist Name\" /path/to/xml/dumps")
        sys.exit(1)

    playlist_name = sys.argv[1]
    dump_dir = sys.argv[2]
    
    state_file = f"{playlist_name.replace(' ', '_')}_state.json"
    
    print("Authenticating with Jellyfin...")
    token, user_id = get_auth_token()
    headers = {"Authorization": f'MediaBrowser Token="{token}"'}
    
    track_ids = []
    
    if os.path.exists(state_file):
        print(f"State file {state_file} found. Skipping XML parsing and search.")
        with open(state_file, 'r') as f:
            track_ids = json.load(f)
    else:
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
            
        with open(state_file, 'w') as f:
            json.dump(track_ids, f)

    print(f"\nChecking if playlist '{playlist_name}' exists...")
    params = {"IncludeItemTypes": "Playlist", "searchTerm": playlist_name, "Recursive": "true"}
    check_resp = retry_request(requests.get, f"{JELLYFIN_URL}/Users/{user_id}/Items", headers=headers, params=params)
    playlists = check_resp.json().get('Items', [])
    
    playlist_id = None
    for pl in playlists:
        if pl.get('Name') == playlist_name:
            playlist_id = pl['Id']
            break
            
    if playlist_id:
        print(f"Playlist '{playlist_name}' already exists. Appending tracks...")
    else:
        print("Fetching Music library ID...")
        views_resp = retry_request(requests.get, f"{JELLYFIN_URL}/Users/{user_id}/Views", headers=headers)
        music_library_id = None
        for view in views_resp.json().get('Items', []):
            if view.get('CollectionType') == 'music':
                music_library_id = view['Id']
                break
                
        print(f"Creating playlist '{playlist_name}'...")
        create_payload = {"Name": playlist_name, "UserId": user_id, "MediaType": "Audio"}
        if music_library_id:
            create_payload["ParentId"] = music_library_id
            
        create_resp = retry_request(requests.post, f"{JELLYFIN_URL}/Playlists", json=create_payload, headers=headers)
        playlist_id = create_resp.json()['Id']
    
    print(f"Populating playlist with {len(track_ids)} tracks...")
    ids_str = ",".join(track_ids)
    add_url = f"{JELLYFIN_URL}/Playlists/{playlist_id}/Items"
    retry_request(requests.post, add_url, headers=headers, params={"userId": user_id, "ids": ids_str})
    
    print("Done.")

if __name__ == "__main__":
    main()
