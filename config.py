# Jellyfin Configuration
JELLYFIN_URL = "http://100.76.51.22:8096"
USERNAME = "CBOT"
PASSWORD = "OKKKwhexm1ZSGg"

# List of playlist names that should bypass the track count sanity check.
# This is typically used for playlists that contain duplicate songs,
# because the extraction script automatically deduplicates tracks,
# resulting in a lower unique track count than the UI header claims.
IGNORE_SANITY_CHECK = [
    "Vatsa Winter 2023"
]
