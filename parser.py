import re
import hashlib
import xml.etree.ElementTree as ET

def hash_xml_content_desc(filepath):
    try:
        tree = ET.parse(filepath)
        content = ""
        for node in tree.iter('node'):
            desc = node.get('content-desc', '')
            if desc:
                content += desc + "\n"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    except Exception:
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            descs = re.findall(r'content-desc="([^"]*)"', content)
            return hashlib.md5("\n".join(descs).encode('utf-8')).hexdigest()
        except:
            return ""

def extract_playlist_info(filepath):
    try:
        tree = ET.parse(filepath)
        prev_desc = ""
        for node in tree.iter('node'):
            desc = node.get('content-desc', '')
            if desc:
                match = re.search(r'^(\d+)\s+Track(s)? \([\d:]+\)', desc)
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

def get_playlists_on_screen(filepath):
    playlists = []
    try:
        tree = ET.parse(filepath)
        for node in tree.iter('node'):
            desc = node.get('content-desc', '')
            if desc:
                match = re.match(r'^(.+?)\n.*?\n(\d+)\s+Track(s)?(\nFavorite)?$', desc)
                if match:
                    name = match.group(1).strip()
                    count = int(match.group(2))
                    bounds = node.get('bounds')
                    if bounds:
                        b_match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                        if b_match:
                            x = (int(b_match.group(1)) + int(b_match.group(3))) // 2
                            y = (int(b_match.group(2)) + int(b_match.group(4))) // 2
                            playlists.append({"name": name, "count": count, "x": x, "y": y})
    except Exception:
        pass
    return playlists
