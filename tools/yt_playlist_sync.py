#!/usr/bin/env python3
"""
Sync a YouTube playlist from index.json (YouTube links only).

- Creates the playlist if PLAYLIST_ID is empty.
- Adds videos in reverse chronological add-order so the playlist displays oldest->newest.
- Skips empty/missing youtube_url entries.
- Idempotent: won't re-add existing videos.

Prereqs:
  pip install google-api-python-client google-auth-oauthlib google-auth-httplib2
  client_secret.json in tools/

Usage:
  python tools/yt_playlist_sync.py --title "Chris Bache Archive — Public Talks & Interviews (2014–2025)"
  # or, if you already created a playlist and know its ID:
  python tools/yt_playlist_sync.py --playlist-id PLxxxxxxxxxxxxxxxx
"""
import argparse, json, pathlib, re, sys, datetime
from typing import List, Dict

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

ROOT = pathlib.Path(__file__).resolve().parents[1]
INDEX_JSON = ROOT / "index.json"
SECRETS = ROOT / "tools" / "client_secret.json"
TOKEN = ROOT / "tools" / "token.json"
SCOPES = ["https://www.googleapis.com/auth/youtube"]

YOUTUBE_ID_RE = re.compile(r"(?:v=|/shorts/|/embed/|youtu\.be/)([A-Za-z0-9_-]{11})")

def extract_video_id(url: str) -> str:
    if not url:
        return ""
    m = YOUTUBE_ID_RE.search(url)
    return m.group(1) if m else ""

def load_items() -> List[Dict]:
    with INDEX_JSON.open("r", encoding="utf-8") as f:
        items = json.load(f)
    # sort by published (oldest first), fallback minimal date
    def k(it):
        d = (it.get("published") or "").strip()
        try:
            return datetime.date.fromisoformat(d)
        except Exception:
            return datetime.date.min
    items.sort(key=k)
    return items

def auth_youtube():
    creds = None
    if TOKEN.exists():
        creds = Credentials.from_authorized_user_file(TOKEN, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh()  # type: ignore
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(SECRETS), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN.write_text(creds.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=creds)

def create_playlist(youtube, title: str, description: str = "") -> str:
    body = {
        "snippet": {"title": title, "description": description},
        "status": {"privacyStatus": "public"},
    }
    resp = youtube.playlists().insert(part="snippet,status", body=body).execute()
    return resp["id"]

def get_existing_video_ids(youtube, playlist_id: str) -> List[str]:
    ids = []
    page_token = None
    while True:
        resp = youtube.playlistItems().list(
            part="contentDetails",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=page_token
        ).execute()
        for item in resp.get("items", []):
            vid = item["contentDetails"]["videoId"]
            ids.append(vid)
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return ids

def add_video(youtube, playlist_id: str, video_id: str):
    body = {
        "snippet": {
            "playlistId": playlist_id,
            "resourceId": {"kind": "youtube#video", "videoId": video_id},
        }
    }
    youtube.playlistItems().insert(part="snippet", body=body).execute()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--playlist-id", default="", help="Existing playlist ID (optional)")
    ap.add_argument("--title", default="Chris Bache Archive — Public Talks & Interviews (2014–2025)",
                    help="Playlist title if creating a new one")
    ap.add_argument("--desc", default=(
        "A chronological journey through public talks and interviews by Christopher M. Bache. "
        "Transcripts and metadata: https://bache-archive.github.io/chris-bache-archive/"
    ), help="Playlist description if creating a new one")
    args = ap.parse_args()

    if not INDEX_JSON.exists():
        print(f"Missing {INDEX_JSON}", file=sys.stderr)
        sys.exit(2)
    if not SECRETS.exists():
        print(f"Missing OAuth client secrets at {SECRETS}", file=sys.stderr)
        sys.exit(2)

    items = load_items()
    # Build list of video IDs in oldest->newest order (skip blanks)
    ordered_vids = []
    for it in items:
        vid = extract_video_id((it.get("youtube_url") or "").strip())
        if vid:
            ordered_vids.append(vid)

    if not ordered_vids:
        print("No YouTube URLs found in index.json", file=sys.stderr)
        sys.exit(3)

    youtube = auth_youtube()

    playlist_id = args.playlist_id.strip()
    if not playlist_id:
        # create once
        playlist_id = create_playlist(youtube, args.title, args.desc)
        print(f"Created playlist: {playlist_id}")

    # Ensure idempotency: fetch existing items
    existing = set(get_existing_video_ids(youtube, playlist_id))
    print(f"Playlist currently has {len(existing)} videos.")

    # Add in reverse (newest first) so display is oldest->newest
    added = 0
    for vid in reversed(ordered_vids):
        if vid in existing:
            continue
        try:
            add_video(youtube, playlist_id, vid)
            added += 1
        except HttpError as e:
            print(f"Failed to add {vid}: {e}", file=sys.stderr)

    print(f"Added {added} new videos.")
    print(f"Playlist URL (open in browser): https://www.youtube.com/playlist?list={playlist_id}")

if __name__ == "__main__":
    main()
