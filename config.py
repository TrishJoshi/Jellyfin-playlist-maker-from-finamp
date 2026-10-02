import os

def load_env():
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    k, v = line.strip().split("=", 1)
                    os.environ[k] = v.strip('"\'')

load_env()

JELLYFIN_URL = os.getenv("JELLYFIN_URL", "http://100.76.51.22:8096")
USERNAME = os.getenv("USERNAME", "CBOT")
PASSWORD = os.getenv("PASSWORD", "OKKKwhexm1ZSGg")

# List of playlist names that should bypass the track count sanity check.
# This is typically used for playlists that contain duplicate songs,
# because the extraction script automatically deduplicates tracks,
# resulting in a lower unique track count than the UI header claims.
IGNORE_SANITY_CHECK = [
    "Vatsa Winter 2023"
]
