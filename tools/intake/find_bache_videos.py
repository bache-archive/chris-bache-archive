#!/usr/bin/env python3
"""
Find new Chris Bache–related YouTube videos and compare to an existing index.json.

Features
- Loads known IDs from index.json (supports multiple shapes)
- Searches multiple query variants (name + book)
- Heuristic scoring to prefer interviews/talks (vs reviews/reposts)
- Duration and phrase-based filtering (drop Shorts, audiobooks, “link in bio,” etc.)
- Optional allow/deny channel lists and “require name in title”
- Exports JSON + CSV candidates
- Works with --api-key or YT_API_KEY from .env (python-dotenv optional)

Usage
  python tools/find_bache_videos.py --index index.json
  # (env) YT_API_KEY is read from .env if --api-key not passed

Common flags
  --min-score 3 --min-duration-sec 600 --require-name-in-title
"""
import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple

# Optional .env loading
try:
    from dotenv import load_dotenv  # pip install python-dotenv
    load_dotenv()
except Exception:
    pass

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"

# ---- Query set --------------------------------------------------------------

def default_queries() -> List[str]:
    # Separate searches; merged later.
    return [
        'intitle:"Chris Bache"',
        'intitle:"Christopher Bache"',
        'intitle:"Christopher M. Bache"',
        '"Chris Bache"',
        '"Christopher Bache"',
        '"Christopher M. Bache"',
        '"LSD and the Mind of the Universe" "Chris Bache"',
        '"LSD and the Mind of the Universe" "Christopher"',
        # Broader book phrases (down-weighted, filtered later):
        '"LSD and the Mind of the Universe"',
        '"Diamonds from Heaven" Bache',
    ]

# ---- Patterns & scoring -----------------------------------------------------

NAME_PATTERNS = [
    re.compile(r"\bchris(?:topher)?\s+m\.?\s*bache\b", re.I),
    re.compile(r"\bchris(?:topher)?\s+bache\b", re.I),
    re.compile(r"\bbache\b", re.I),  # fallback, weak
]

BOOK_PATTERNS = [
    re.compile(r"\blsd\s+and\s+the\s+mind\s+of\s+the\s+universe\b", re.I),
    re.compile(r"\bdiamonds?\s+from\s+heaven\b", re.I),
]

INTERVIEW_HINTS = [
    re.compile(r"\b(with|conversation|interview|dialogue|talk|lecture|podcast|keynote|q\s*&\s*a|panel)\b", re.I),
]

def score_candidate(title: str, desc: str, channel_title: str, allow_channels: List[str]) -> Tuple[int, Dict[str, bool]]:
    """
    Heuristic scoring:
      +5 if full name match (Christopher M. Bache) in title
      +4 if "Chris Bache" in title
      +3 if name in description
      +2 if book phrase in title/desc
      +1 if interview-ish hints
      +1 if channel title contains 'Bache'
      +2 if channel is in allow list
      -2 if only book phrase appears but no 'Bache' anywhere (likely review)
    """
    t = title or ""
    d = desc or ""
    c = channel_title or ""

    flags = {
        "full_name_title": bool(re.search(r"\bchristopher\s+m\.?\s*bache\b", t, re.I)),
        "chris_name_title": bool(re.search(r"\bchris\s+bache\b", t, re.I)),
        "any_name_desc": any(p.search(d) for p in NAME_PATTERNS),
        "book_phrase": any(p.search(t) or p.search(d) for p in BOOK_PATTERNS),
        "interview_hint": any(p.search(t) or p.search(d) for p in INTERVIEW_HINTS),
        "channel_has_bache": bool(re.search(r"\bbache\b", c, re.I)),
        "has_any_name_anywhere": any(p.search(t) or p.search(d) for p in NAME_PATTERNS),
        "allow_channel": c in allow_channels if allow_channels else False,
    }

    score = 0
    if flags["full_name_title"]:
        score += 5
    if flags["chris_name_title"]:
        score += 4
    if flags["any_name_desc"]:
        score += 3
    if flags["book_phrase"]:
        score += 2
    if flags["interview_hint"]:
        score += 1
    if flags["channel_has_bache"]:
        score += 1
    if flags["allow_channel"]:
        score += 2
    if flags["book_phrase"] and not flags["has_any_name_anywhere"]:
        score -= 2  # likely about the book, not with Chris

    return score, flags

# ---- Utilities --------------------------------------------------------------

def http_get(url: str, params: Dict[str, str]) -> dict:
    full = f"{url}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(full) as resp:
        return json.loads(resp.read().decode("utf-8"))

def parse_iso8601_duration(iso: str) -> int:
    """Parse simple PT#H#M#S to seconds."""
    if not iso or not iso.startswith("PT"):
        return 0
    h = m = s = 0
    cur = iso[2:]
    num = ""
    for ch in cur:
        if ch.isdigit():
            num += ch
        else:
            if ch == 'H': h = int(num or 0)
            if ch == 'M': m = int(num or 0)
            if ch == 'S': s = int(num or 0)
            num = ""
    return h * 3600 + m * 60 + s

def load_known_ids(index_path: Path) -> set:
    """
    Supports:
    - {"videos": [{"youtube_id": "..."} , ...]}
    - {"items": [{"id": "..."} , ...]}
    - ["id1", "id2", ...]
    - any dict where nested objects contain "youtube_id" or "id" strings
    """
    if not index_path.exists():
        print(f"[warn] index.json not found at {index_path}. Proceeding with empty known set.", file=sys.stderr)
        return set()
    try:
        data = json.loads(index_path.read_text())
    except Exception as e:
        print(f"[warn] Could not parse {index_path}: {e}. Proceeding with empty known set.", file=sys.stderr)
        return set()

    known = set()

    def walk(obj):
        if isinstance(obj, dict):
            if "youtube_id" in obj and isinstance(obj["youtube_id"], str):
                known.add(obj["youtube_id"])
            if "id" in obj and isinstance(obj["id"], str) and 8 <= len(obj["id"]) <= 15:
                if all(c.isalnum() or c in "-_" for c in obj["id"]):
                    known.add(obj["id"])
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)
        elif isinstance(obj, str):
            if 8 <= len(obj) <= 15 and all(c.isalnum() or c in "-_" for c in obj):
                known.add(obj)

    walk(data)
    return known

def youtube_search(api_key: str, query: str, max_results: int = 100, published_after: str = None, order: str = "date") -> List[dict]:
    """Return search items (id + snippet)."""
    items = []
    params = {
        "key": api_key,
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": 50 if max_results > 50 else max_results,
        "order": order,
        "safeSearch": "none",
        "regionCode": "US",
        "relevanceLanguage": "en",
    }
    if published_after:
        params["publishedAfter"] = published_after

    token = None
    while True:
        if token:
            params["pageToken"] = token
        data = http_get(f"{YOUTUBE_API_BASE}/search", params)
        items.extend(data.get("items", []))
        token = data.get("nextPageToken")
        if not token or len(items) >= max_results:
            break
        time.sleep(0.2)  # politeness

    return items[:max_results]

def videos_details(api_key: str, video_ids: List[str]) -> Dict[str, dict]:
    out = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]
        params = {
            "key": api_key,
            "part": "snippet,contentDetails,statistics",
            "id": ",".join(batch),
            "maxResults": 50,
        }
        data = http_get(f"{YOUTUBE_API_BASE}/videos", params)
        for it in data.get("items", []):
            out[it["id"]] = it
        time.sleep(0.15)
    return out

# ---- Main -------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Find new Chris Bache–related YouTube videos and compare to an existing index.json.")

    # Inputs / outputs
    ap.add_argument("--api-key", required=False, help="YouTube Data API v3 key (or set YT_API_KEY in .env)")
    ap.add_argument("--index", type=Path, default=Path("index.json"), help="Path to existing index.json")
    ap.add_argument("--out-json", type=Path, default=Path("candidates.bache.youtube.json"))
    ap.add_argument("--out-csv", type=Path, default=Path("candidates.bache.youtube.csv"))

    # Search window & volume
    ap.add_argument("--max-per-query", type=int, default=120)
    ap.add_argument("--days", type=int, default=3650, help="Search window (days back). Default ~10 years.")
    ap.add_argument("--order", type=str, default="date", choices=["date", "relevance", "viewCount", "rating", "title", "videoCount"])

    # Heuristics & filters
    ap.add_argument("--min-score", type=int, default=2, help="Minimum heuristic score to keep")
    ap.add_argument("--min-duration-sec", type=int, default=600, help="Drop videos shorter than this (default 10 min)")
    ap.add_argument("--max-duration-sec", type=int, default=6*60*60, help="Drop videos longer than this (default 6h)")
    ap.add_argument("--exclude-phrases", nargs="*", default=[
        "free audiobook", "audiobook", "full audiobook", "link in bio", "reaction", "summary", "asmr"
    ], help="Lower-signal phrases in title/description to exclude.")
    ap.add_argument("--allow-shorts", action="store_true", help="Keep YouTube Shorts (default: drop)")

    ap.add_argument("--allow-channels", nargs="*", default=[
        "New Thinking Allowed with Jeffrey Mishlove",
        "Buddha at the Gas Pump",
        "SAND",
        "Science and Nonduality",
        "Psychedelics Today",
        "Alex Tsakiris",
        "Theories of Everything with Curt Jaimungal",
        "The Stoa",
        "Evolve and Ascend",
    ], help="Boost these channels by +2.")
    ap.add_argument("--deny-channels", nargs="*", default=[], help="Drop these channels entirely.")
    ap.add_argument("--require-name-in-title", action="store_true", help="Keep only videos with the name in the title.")

    args = ap.parse_args()

    # API key resolution
    if not args.api_key:
        args.api_key = os.getenv("YT_API_KEY")
    if not args.api_key:
        ap.error("Missing API key. Pass --api-key or set YT_API_KEY in .env")

    known = load_known_ids(args.index)
    print(f"[info] Loaded {len(known)} known YouTube IDs from {args.index}")

    since = (datetime.now(timezone.utc) - timedelta(days=args.days)).isoformat()
    queries = default_queries()
    print(f"[info] Running {len(queries)} queries across {args.days} days...")

    found_ids = set()
    raw_items = []

    for q in queries:
        print(f"[info] Searching: {q}")
        items = youtube_search(args.api_key, q, max_results=args.max_per_query, published_after=since, order=args.order)
        raw_items.extend(items)
        for it in items:
            vid = it.get("id", {}).get("videoId")
            if vid:
                found_ids.add(vid)

    print(f"[info] Retrieved {len(raw_items)} search items; unique IDs: {len(found_ids)}")

    # Fetch full details
    details_map = videos_details(args.api_key, list(found_ids))
    print(f"[info] Fetched details for {len(details_map)} videos.")

    candidates = []
    for vid, obj in details_map.items():
        if vid in known:
            continue

        snippet = obj.get("snippet", {}) or {}
        cdet = obj.get("contentDetails", {}) or {}

        title = snippet.get("title", "") or ""
        desc = snippet.get("description", "") or ""
        channel_title = snippet.get("channelTitle", "") or ""
        published_at = snippet.get("publishedAt")

        # Drop deny channels early
        if channel_title in args.deny_channels:
            continue

        duration_iso = cdet.get("duration")
        duration_sec = parse_iso8601_duration(duration_iso)

        # Drop Shorts unless allowed (often <60s)
        if not args.allow_shorts and duration_sec and duration_sec < 60:
            continue

        # Duration bounds
        if duration_sec and (duration_sec < args.min_duration_sec or duration_sec > args.max_duration_sec):
            continue

        # Exclude phrases
        lt = title.lower()
        ld = desc.lower()
        if any(p.lower() in lt or p.lower() in ld for p in args.exclude_phrases):
            continue

        score, flags = score_candidate(title, desc, channel_title, args.allow_channels)

        if args.require_name_in_title and not (flags["full_name_title"] or flags["chris_name_title"]):
            continue

        if score >= args.min_score:
            candidates.append({
                "video_id": vid,
                "title": title,
                "channel_title": channel_title,
                "published_at": published_at,
                "duration_sec": duration_sec,
                "score": score,
                "flags": flags,
                "url": f"https://www.youtube.com/watch?v={vid}",
            })

    # Sort by score, then publish date
    candidates.sort(key=lambda x: (x["score"], x.get("published_at") or ""), reverse=True)

    # Write outputs
    args.out_json.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "query_days": args.days,
        "min_score": args.min_score,
        "count": len(candidates),
        "candidates": candidates,
    }, indent=2), encoding="utf-8")

    with args.out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["score", "video_id", "published_at", "duration_sec", "title", "channel_title", "url", "flags"])
        for c in candidates:
            w.writerow([
                c["score"],
                c["video_id"],
                c["published_at"],
                c.get("duration_sec", ""),
                c["title"],
                c["channel_title"],
                c["url"],
                ";".join([k for k, v in c["flags"].items() if v]),
            ])

    print(f"[done] Wrote {len(candidates)} candidates to:")
    print(f"  - {args.out_json}")
    print(f"  - {args.out_csv}")

    if len(candidates) > 0:
        print("\nTop 10 preview:")
        for c in candidates[:10]:
            print(f"  [{c['score']}] {c['published_at']} — {c['title']} — {c['url']}")

if __name__ == "__main__":
    main()