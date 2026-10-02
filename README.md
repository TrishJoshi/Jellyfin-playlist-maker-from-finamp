# Finamp Playlist Resurrector

## The Story 📖
I accidentally corrupted my backup of the Jellyfin DB and then upgraded it. Everything stopped working. When I tried to restore it using Proxmox VE's UI, it just straight up removed the container from the list because the backup itself was corrupt! 

I was forced to create a new container with a [fresh install of Jellyfin](https://jellyfin.org/docs/general/installation/linux#debian--ubuntu-and-derivatives). But I lost all my carefully curated playlists...

My only source of truth was [Finamp](https://github.com/jmshrv/finamp)! The Finamp Android app had all my playlists downloaded locally in offline mode. The easiest way to extract them was to write this autonomous ADB scraping tool to resurrect them and sync them back to my fresh Jellyfin server.

## Features ✨
* **Fully Autonomous Android Extraction**: Automatically scrolls through the Finamp UI, clicking and scraping every playlist on the device.
* **100% Idempotent Extraction**: You can stop and restart the script anytime. It cleanly skips already-extracted playlists.
* **Sanity Checking**: Mathematically verifies that every track was extracted by comparing against the Finamp UI headers.
* **Jellyfin API Sync**: Automatically recreates the playlists in your Jellyfin server.
* **Smart Matching**: Uses a cascading search algorithm to match your offline tracks back to your Jellyfin library.
* **API Safety**: Chunks Jellyfin playlist additions to prevent `414 URI Too Long` errors.

## Usage 🚀

### 1. Extract Playlists from Phone
Plug in your Android phone with ADB enabled, open Finamp to the playlists page, and run:
```bash
python run.py
```

### 2. Sync to Jellyfin
Once the extraction completes, push them all to your fresh Jellyfin install:
```bash
python app.py --all
```
