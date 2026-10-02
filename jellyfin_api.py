import requests
import time
from config import JELLYFIN_URL, USERNAME, PASSWORD

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
        for item in results:
            jellyfin_title = item.get('Name', '')
            jellyfin_artists = [a.lower() for a in item.get('Artists', [])]
            if title.lower() == jellyfin_title.lower() and artist.lower() in jellyfin_artists:
                return item['Id']
                
        for item in results:
            if item.get('Name', '').lower() == title.lower():
                return item['Id']

        return results[0]['Id']
    else:
        fallback_title = title.split('(')[0].strip()
        fallback_results = do_search(fallback_title)
        if fallback_results:
            return fallback_results[0]['Id']
        return None
