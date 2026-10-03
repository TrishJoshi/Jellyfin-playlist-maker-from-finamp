import requests
import sys

from config import JELLYFIN_URL
from jellyfin_api import get_auth_token, retry_request

def main():
    print("Authenticating with Jellyfin...")
    token, user_id = get_auth_token()
    headers = {"Authorization": f'MediaBrowser Token="{token}"'}
    
    print("Searching for the 'LIKED' playlist...")
    params = {"IncludeItemTypes": "Playlist", "searchTerm": "LIKED", "Recursive": "true"}
    check_resp = retry_request(requests.get, f"{JELLYFIN_URL}/Users/{user_id}/Items", headers=headers, params=params)
    playlists = check_resp.json().get('Items', [])
    
    playlist_id = None
    for pl in playlists:
        if pl.get('Name') == 'LIKED':
            playlist_id = pl['Id']
            break
            
    if not playlist_id:
        print("ERROR: Could not find 'LIKED' playlist on the Jellyfin server.")
        sys.exit(1)
        
    print(f"Fetching tracks for playlist ID: {playlist_id}...")
    items_resp = retry_request(
        requests.get, 
        f"{JELLYFIN_URL}/Playlists/{playlist_id}/Items", 
        headers=headers, 
        params={"userId": user_id, "Fields": "UserData"}
    )
    items = items_resp.json().get('Items', [])
    
    if not items:
        print("No tracks found in the LIKED playlist.")
        return
        
    print(f"Found {len(items)} tracks. Hearting them all...")
    
    hearted_count = 0
    skipped_count = 0
    
    for i, item in enumerate(items):
        item_id = item['Id']
        title = item.get('Name', 'Unknown')
        artists = ", ".join(item.get('Artists', []))
        
        is_favorite = item.get('UserData', {}).get('IsFavorite', False)
        
        if not is_favorite:
            print(f"  [{i+1}/{len(items)}] ❤️ Hearting: {title} - {artists}")
            fav_url = f"{JELLYFIN_URL}/Users/{user_id}/FavoriteItems/{item_id}"
            retry_request(requests.post, fav_url, headers=headers)
            hearted_count += 1
        else:
            # print(f"  [{i+1}/{len(items)}] ⏭️ Already hearted: {title} - {artists}")
            skipped_count += 1
            
    print("\n==========================================================")
    print(f"Finished! Hearted {hearted_count} new tracks. (Skipped {skipped_count} tracks that were already favorited).")

if __name__ == "__main__":
    main()
