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

def process_playlist(dump_dir, token, user_id, headers):
    xml_files = sorted(glob.glob(os.path.join(dump_dir, "*.xml")))
    if not xml_files:
        print(f"No XML files found in {dump_dir}. Skipping.")
        return
        
    playlist_name = None
    try:
        tree = ET.parse(xml_files[0])
        root = tree.getroot()
        prev_desc = ""
        for node in root.iter('node'):
            desc = node.get('content-desc', '')
            if desc:
                if re.search(r'\d+ Track(s)? \([\d:]+\)', desc):
                    playlist_name = prev_desc
                    break
                prev_desc = desc
    except ET.ParseError:
        pass
        
    if not playlist_name:
        print(f"Could not determine playlist name from the first XML file in {dump_dir}. Skipping.")
        return
        
    print(f"Extracted playlist name: '{playlist_name}'")
    state_file = f"{playlist_name.replace(' ', '_')}_state.json"
    
    track_ids = []
    
    if os.path.exists(state_file):
        print(f"State file {state_file} found. Skipping XML parsing and search.")
        with open(state_file, 'r') as f:
            track_ids = json.load(f)
    else:
        extracted_tracks = []
        tracks_json = os.path.join(dump_dir, "tracks.json")
        if os.path.exists(tracks_json):
            print(f"Found tracks.json! Loading pre-extracted tracks...")
            with open(tracks_json, "r", encoding="utf-8") as f:
                tracks_data = json.load(f)
            extracted_tracks = [(t["title"], t["artist"]) for t in tracks_data]
        else:
            print("tracks.json not found, falling back to raw XML parsing...")
            seen_titles = set()
            for xml_file in xml_files:
                try:
                    tree = ET.parse(xml_file)
                    root = tree.getroot()
                    
                    for node in root.iter('node'):
                        desc = node.get('content-desc', '')
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

        print(f"Extracted {len(extracted_tracks)} unique tracks.")
        
        for title, artist in extracted_tracks:
            track_id = search_jellyfin_for_track(title, artist, user_id, headers)
            if track_id:
                track_ids.append(track_id)
                print(f"  [Match] {title} - {artist}")
            else:
                print(f"  [Failed] Could not find: {title} - {artist}")

        if not track_ids:
            print("No tracks found in Jellyfin for this playlist. Skipping creation.")
            return
            
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
        print(f"Playlist '{playlist_name}' already exists. Fetching existing tracks to prevent duplicates...")
        existing_items_resp = retry_request(requests.get, f"{JELLYFIN_URL}/Playlists/{playlist_id}/Items?userId={user_id}", headers=headers)
        existing_track_ids = {item['Id'] for item in existing_items_resp.json().get('Items', [])}
        
        track_ids = [tid for tid in track_ids if tid not in existing_track_ids]
        if not track_ids:
            print("All tracks are already in the playlist. Nothing to add.")
            return
            
        print(f"Appending {len(track_ids)} new tracks...")
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
    
    chunk_size = 100
    for i in range(0, len(track_ids), chunk_size):
        chunk = track_ids[i:i + chunk_size]
        ids_str = ",".join(chunk)
        add_url = f"{JELLYFIN_URL}/Playlists/{playlist_id}/Items"
        retry_request(requests.post, add_url, headers=headers, params={"userId": user_id, "ids": ids_str})
        print(f"  Added batch {i//chunk_size + 1}/{(len(track_ids) - 1)//chunk_size + 1} ({len(chunk)} tracks)")
    
    print(f"Done with '{playlist_name}'.")

def main():
    if len(sys.argv) < 2:
        print("Usage: python app.py [/path/to/xml/dumps | --all]")
        sys.exit(1)

    if sys.argv[1] == "--all":
        dump_dirs = sorted([os.path.join("playlists", d) for d in os.listdir("playlists") if os.path.isdir(os.path.join("playlists", d))])
    else:
        if len(sys.argv) == 3:
            dump_dirs = [sys.argv[2]]
        else:
            dump_dirs = [sys.argv[1]]
            
    print("Authenticating with Jellyfin...")
    token, user_id = get_auth_token()
    headers = {"Authorization": f'MediaBrowser Token="{token}"'}
            
    for dump_dir in dump_dirs:
        print(f"\n==========================================================")
        print(f"Processing directory: {dump_dir}")
        process_playlist(dump_dir, token, user_id, headers)
        
    print("\n==========================================================")
    print("All Jellyfin playlists have been processed!")

if __name__ == "__main__":
    main()
