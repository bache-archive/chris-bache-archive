#!/usr/bin/env python3
"""
Sync a YouTube playlist from index.json (YouTube links or explicit IDs).

Features:
- Creates the playlist if --playlist-id is omitted.
- Adds videos missing from the playlist (idempotent).
- Inserts in reverse add-order so the playlist UI reads oldest->newest.
- Optional strict reordering to enforce true chronological order.
- Dry-run mode to preview actions without changing anything.

Prereqs:
  pip install google-api-python-client google-auth-oauthlib google-auth-httplib2
  # (google-auth installs transport.requests)
  client_secret.json in tools/

Usage:
  # Create-or-sync (without reordering existing items)
  python tools/yt_playlist_sync.py --title "Chris Bache Archive — Public Talks & Interviews (2009–2025)"

  # Sync an existing playlist by ID
  python tools/yt_playlist_sync.py --playlist-id PLIuDc6SKtEHWjyTpCTJj6AVUrRYv3rbu1

  # Preview only
  python tools/yt_playlist_sync.py --playlist-id PLIu... --dry-run

  # Enforce strict oldest->newest across the entire playlist
  python tools/yt_playlist_sync.py --playlist-id PLIu... --reorder
"""
from __future__ import annotations
import argparse
import datetime
import json
import pathlib
import re
import sys
from typing import Dict, List, Tuple

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

ROOT = pathlib.Path(__file__).resolve().parents[2]
INDEX_JSON = ROOT / "index.json"
SECRETS = ROOT / "tools" / "client_secret.json"
TOKEN = ROOT / "tools" / "token.json"
SCOPES = ["https://www.googleapis.com/auth/youtube"]

# Extract 11-char video IDs from common URL shapes
YOUTUBE_ID_RE = re.compile(r"(?:v=|/shorts/|/embed/|youtu\.be/)([A-Za-z0-9_-]{11})")


def extract_video_id_from_url(url: str) -> str:
    if not url:
        return ""
    m = YOUTUBE_ID_RE.search(url)
    return m.group(1) if m else ""


def load_items() -> List[Dict]:
    """
    Expect index.json at repo root with items that include:
      - youtube_id (preferred) OR youtube_url
      - published (YYYY-MM-DD)
    """
    with INDEX_JSON.open("r", encoding="utf-8") as f:
        items = json.load(f)

    def key_fn(it: Dict) -> Tuple[datetime.date, str]:
        d = (it.get("published") or "").strip()
        try:
            dt = datetime.date.fromisoformat(d)
        except Exception:
            dt = datetime.date.min
        # Tie-breaker for stability
        tiebreak = (it.get("slug") or it.get("archival_title") or it.get("title") or "").strip()
        return (dt, tiebreak)

    items.sort(key=key_fn)  # oldest first
    return items


def auth_youtube(dry_run: bool = False):
    if dry_run:
        return None  # No network calls in dry-run until explicitly needed

    creds = None
    if TOKEN.exists():
        creds = Credentials.from_authorized_user_file(TOKEN, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(SECRETS), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN.write_text(creds.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=creds)


def create_playlist(youtube, title: str, description: str = "", dry_run: bool = False) -> str:
    if dry_run:
        print(f"[dry-run] Would create playlist: {title!r}")
        return "DRY_RUN_PLAYLIST_ID"
    body = {
        "snippet": {"title": title, "description": description},
        "status": {"privacyStatus": "public"},
    }
    resp = youtube.playlists().insert(part="snippet,status", body=body).execute()
    return resp["id"]


def get_existing_video_ids(youtube, playlist_id: str) -> List[str]:
    ids: List[str] = []
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


def get_playlist_items(youtube, playlist_id: str) -> List[Dict]:
    out: List[Dict] = []
    page_token = None
    while True:
        resp = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=page_token
        ).execute()
        out.extend(resp.get("items", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return out


def add_video(youtube, playlist_id: str, video_id: str, dry_run: bool = False):
    if dry_run:
        print(f"[dry-run] Would add video: {video_id} -> playlist {playlist_id}")
        return
    body = {
        "snippet": {
            "playlistId": playlist_id,
            "resourceId": {"kind": "youtube#video", "videoId": video_id},
        }
    }
    youtube.playlistItems().insert(part="snippet", body=body).execute()


def reorder_playlist(youtube, playlist_id: str, target_order: List[str], dry_run: bool = False):
    """
    Enforce that the playlist begins with target_order in that exact order.
    Videos missing (private/deleted) are skipped. Other videos remain after.
    """
    items = get_playlist_items(youtube, playlist_id)
    by_vid = {i["contentDetails"]["videoId"]: i for i in items}

    # Filter to videos that are actually present in the playlist
    target = [v for v in target_order if v in by_vid]

    for pos, vid in enumerate(target):
        it = by_vid[vid]
        cur_pos = it["snippet"]["position"]
        if cur_pos == pos:
            continue

        if dry_run:
            print(f"[dry-run] Would move video {vid} from position {cur_pos} -> {pos}")
            continue

        # Only 'id' and 'snippet' allowed on update; include resourceId
        body = {
            "id": it["id"],
            "snippet": {
                "playlistId": playlist_id,
                "position": pos,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": vid
                }
            }
        }
        youtube.playlistItems().update(part="snippet", body=body).execute()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--playlist-id", default="", help="Existing playlist ID (optional)")
    ap.add_argument("--title", default="Chris Bache Archive — Public Talks & Interviews (2009–2025)",
                    help="Playlist title if creating a new one")
    ap.add_argument("--desc", default=(
        "A chronological journey through public talks and interviews by Christopher M. Bache. "
        "Transcripts and metadata: https://bache-archive.github.io/chris-bache-archive/"
    ), help="Playlist description if creating a new one")
    ap.add_argument("--reorder", action="store_true",
                    help="Enforce strict oldest→newest order across the entire playlist (optional).")
    ap.add_argument("--dry-run", action="store_true", help="Preview actions without making changes.")
    args = ap.parse_args()

    # Basic checks
    if not INDEX_JSON.exists():
        print(f"Missing {INDEX_JSON}", file=sys.stderr)
        sys.exit(2)
    if not SECRETS.exists() and not args.dry_run:
        print(f"Missing OAuth client secrets at {SECRETS}", file=sys.stderr)
        sys.exit(2)

    items = load_items()

    # Build list of video IDs in oldest->newest order, de-duped preserving order
    def vid_from_item(it: Dict) -> str:
        vid = (it.get("youtube_id") or "").strip()
        if len(vid) == 11 and re.fullmatch(r"[A-Za-z0-9_-]{11}", vid):
            return vid
        return extract_video_id_from_url((it.get("youtube_url") or "").strip())

    seen = set()
    ordered_vids: List[str] = []
    for it in items:
        vid = vid_from_item(it)
        if vid and vid not in seen:
            ordered_vids.append(vid)
            seen.add(vid)

    if not ordered_vids:
        print("No YouTube IDs/URLs found in index.json", file=sys.stderr)
        sys.exit(3)

    youtube = auth_youtube(dry_run=args.dry_run)

    playlist_id = args.playlist_id.strip()
    if not playlist_id:
        # Create a new playlist
        playlist_id = create_playlist(youtube, args.title, args.desc, dry_run=args.dry_run)
        print(f"Created playlist: {playlist_id}")

    # Fetch existing to ensure idempotency
    existing = set()
    if not args.dry_run:
        try:
            existing = set(get_existing_video_ids(youtube, playlist_id))
        except HttpError as e:
            print(f"Error reading playlist items: {e}", file=sys.stderr)
            sys.exit(4)
    else:
        print("[dry-run] Skipping fetch of existing playlist items; assuming none.")
    print(f"Playlist currently has {len(existing)} videos." if existing else "Playlist currently has 0 videos (or dry-run).")

    # Add new items in reverse (newest first) so the UI ends up oldest->newest
    added = 0
    to_add = [v for v in reversed(ordered_vids) if v not in existing]
    if to_add:
        print(f"{'Would add' if args.dry_run else 'Adding'} {len(to_add)} videos...")
    for vid in to_add:
        try:
            add_video(youtube, playlist_id, vid, dry_run=args.dry_run)
            added += 1
        except HttpError as e:
            print(f"Failed to add {vid}: {e}", file=sys.stderr)

    # Optional strict reordering
    if args.reorder:
        try:
            reorder_playlist(youtube, playlist_id, ordered_vids, dry_run=args.dry_run)
        except HttpError as e:
            print(f"Failed to reorder playlist: {e}", file=sys.stderr)

    print(f"Added {added} new videos." + (" (dry-run)" if args.dry_run else ""))
    print(f"Playlist URL: https://www.youtube.com/playlist?list={playlist_id}")

if __name__ == "__main__":
    main()