#!/usr/bin/env python3
"""
find_bache_audio.py — Thorough finder for audio-only podcasts and blog interviews with Chris Bache.

What it does (no paid APIs required):
  1) Apple Podcasts Search API (episodes): direct hits for "Chris Bache" and variants
  2) Apple Podcasts Search API (podcasts): collects feed URLs, parses RSS, finds matching episodes
  3) Heuristics to classify "audio-only" (mp3/m4a/enclosure audio) vs everything else
  4) De-dupes, normalizes, and exports JSON + CSV

Optional (if you provide keys as env vars):
  - LISTENNOTES_API_KEY      → queries Listen Notes episodes API
  - GCS_API_KEY + GCS_CX     → Google Custom Search to sweep blogs + MP3s

Usage:
  python3 find_bache_audio.py --out out/bache_audio
"""

import csv
import dataclasses
import json
import os
import re
import sys
import time
import urllib.parse
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

import requests

try:
    import feedparser
except ImportError:
    print("This script requires 'feedparser' (pip install feedparser).", file=sys.stderr)
    sys.exit(1)

APPLE_SEARCH = "https://itunes.apple.com/search"
APPLE_LOOKUP = "https://itunes.apple.com/lookup"

# ---- Configurable knobs ----
DEFAULT_OUT_BASENAME = "bache_audio_results"
USER_AGENT = "BacheArchiveFinder/1.0 (+https://github.com/bache-archive)"

# Search terms that reliably catch Chris:
PERSON_TERMS = [
    '"Chris Bache"',
    '"Christopher M. Bache"',
    '"Christopher Bache"',
    'Chris Bache',
    'Christopher M. Bache',
]

# Helpful topic phrases Chris is often attached to:
TOPIC_TERMS = [
    '"LSD and the Mind of the Universe"',
    '"Diamonds from Heaven"',
    '"Future Human"',
    '"deep time"',
    '"species mind"',
]

# For RSS parsing, accept episodes mentioning:
EPISODE_MATCH_PATTERNS = [
    r"\bchris(?:topher)?\s+bache\b",
    r"\bchristopher\s+m\.?\s+bache\b",
    r"\bBache\b.*\bLSD\b",
    r"\bLSD and the Mind of the Universe\b",
    r"\bDiamonds from Heaven\b",
    r"\bFuture Human\b",
]
EPISODE_MATCH_RE = re.compile("|".join(EPISODE_MATCH_PATTERNS), re.IGNORECASE)

AUDIO_MIME_HINTS = (
    "audio/mpeg",
    "audio/mp3",
    "audio/x-m4a",
    "audio/aac",
    "audio/mp4",
    "audio/ogg",
)

AUDIO_EXT_HINTS = (
    ".mp3",
    ".m4a",
    ".aac",
    ".mp4",  # some podcasts use mp4 audio
    ".ogg",
    ".oga",
    ".opus",
)

HTTP_TIMEOUT = 15
REQUEST_SLEEP = 0.4  # be polite to APIs
MAX_ITUNES_LIMIT = 200  # Apple allows up to 200 per query


@dataclass
class Hit:
    source: str                     # 'apple_episode', 'apple_rss', 'listennotes', 'gcs'
    title: str
    url: str
    published: Optional[str]
    podcast_name: Optional[str]
    enclosure_url: Optional[str]
    enclosure_type: Optional[str]
    duration: Optional[str]
    transcript_url: Optional[str]
    notes_url: Optional[str]
    # Provenance
    feed_url: Optional[str] = None
    itunes_collection_id: Optional[str] = None
    itunes_track_id: Optional[str] = None


def _get(url: str, params: dict = None, headers: dict = None) -> Optional[requests.Response]:
    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    try:
        r = requests.get(url, params=params, headers=h, timeout=HTTP_TIMEOUT)
        if r.status_code == 200:
            return r
        return None
    except requests.RequestException:
        return None


def looks_audio(url: Optional[str], mime: Optional[str]) -> bool:
    if mime:
        m = mime.lower()
        if any(h in m for h in AUDIO_MIME_HINTS):
            return True
    if url:
        u = url.lower().split("?")[0]
        if any(u.endswith(ext) for ext in AUDIO_EXT_HINTS):
            return True
    return False


def apple_search_episodes(terms: List[str]) -> List[Hit]:
    hits: List[Hit] = []
    for term in terms:
        params = {
            "term": term,
            "media": "podcast",
            "entity": "podcastEpisode",
            "limit": str(MAX_ITUNES_LIMIT),
            "country": "US",
        }
        time.sleep(REQUEST_SLEEP)
        resp = _get(APPLE_SEARCH, params=params)
        if not resp:
            continue
        data = resp.json()
        for item in data.get("results", []):
            title = item.get("trackName") or item.get("collectionName") or ""
            url = item.get("trackViewUrl") or item.get("collectionViewUrl") or ""
            podcast_name = item.get("collectionName")
            enclosure_url = item.get("episodeUrl") or item.get("previewUrl")
            enclosure_type = None  # Apple doesn't always provide MIME here
            published = item.get("releaseDate")
            duration = str(item.get("trackTimeMillis")) if item.get("trackTimeMillis") else None
            hit = Hit(
                source="apple_episode",
                title=title,
                url=url,
                published=published,
                podcast_name=podcast_name,
                enclosure_url=enclosure_url,
                enclosure_type=enclosure_type,
                duration=duration,
                transcript_url=None,
                notes_url=None,
                feed_url=item.get("feedUrl"),
                itunes_collection_id=str(item.get("collectionId")) if item.get("collectionId") else None,
                itunes_track_id=str(item.get("trackId")) if item.get("trackId") else None,
            )
            # Keep only plausible audio episodes
            if looks_audio(enclosure_url, enclosure_type) or "podcasts.apple.com" in url:
                hits.append(hit)
    return hits


def apple_search_podcasts_and_rss(terms: List[str]) -> List[str]:
    """Return unique RSS feed URLs for podcasts matching broader queries."""
    feeds = set()
    for term in terms:
        params = {
            "term": term,
            "media": "podcast",
            "entity": "podcast",
            "limit": str(MAX_ITUNES_LIMIT),
            "country": "US",
        }
        time.sleep(REQUEST_SLEEP)
        resp = _get(APPLE_SEARCH, params=params)
        if not resp:
            continue
        data = resp.json()
        for item in data.get("results", []):
            if "feedUrl" in item and item["feedUrl"]:
                feeds.add(item["feedUrl"])
            # If no feedUrl, try lookup by collectionId to fetch feed
            cid = item.get("collectionId")
            if cid:
                time.sleep(REQUEST_SLEEP)
                r2 = _get(APPLE_LOOKUP, params={"id": cid})
                if r2:
                    d2 = r2.json()
                    for it2 in d2.get("results", []):
                        fu = it2.get("feedUrl")
                        if fu:
                            feeds.add(fu)
    return sorted(feeds)


def parse_rss_for_bache(feed_url: str) -> List[Hit]:
    hits: List[Hit] = []
    time.sleep(REQUEST_SLEEP)
    parsed = feedparser.parse(feed_url)
    podcast_name = parsed.feed.get("title", None)
    for e in parsed.entries:
        # Build a text blob (title + summary) to match against
        title = e.get("title", "") or ""
        summary = (
            e.get("summary", "")
            or e.get("subtitle", "")
            or e.get("description", "")
            or ""
        )
        blob = f"{title}\n{summary}"
        if not EPISODE_MATCH_RE.search(blob):
            continue
        # Find enclosure if present
        enclosure_url, enclosure_type, duration = None, None, None
        if "enclosures" in e and e.enclosures:
            enc = e.enclosures[0]
            enclosure_url = enc.get("href")
            enclosure_type = enc.get("type")
        elif "links" in e:
            for ln in e.links:
                if ln.get("rel") == "enclosure":
                    enclosure_url = ln.get("href")
                    enclosure_type = ln.get("type")
                    break
        # Try duration
        duration = e.get("itunes_duration") or e.get("duration")
        # Prefer the episode page link for URL
        url = e.get("link") or enclosure_url or feed_url

        if looks_audio(enclosure_url, enclosure_type) or enclosure_url is None:
            hits.append(
                Hit(
                    source="apple_rss",
                    title=title.strip(),
                    url=url,
                    published=e.get("published") or e.get("updated"),
                    podcast_name=podcast_name,
                    enclosure_url=enclosure_url,
                    enclosure_type=enclosure_type,
                    duration=str(duration) if duration else None,
                    transcript_url=None,  # could be discovered in show notes later
                    notes_url=url,
                    feed_url=feed_url,
                )
            )
    return hits


def listen_notes_search(terms: List[str]) -> List[Hit]:
    api_key = os.getenv("LISTENNOTES_API_KEY")
    if not api_key:
        return []
    headers = {"X-ListenAPI-Key": api_key, "User-Agent": USER_AGENT}
    hits: List[Hit] = []
    base = "https://listen-api.listennotes.com/api/v2/search"
    for term in terms:
        params = {
            "q": term,
            "type": "episode",
            "safe_mode": "1",
            "sort_by_date": "0",
            "len_min": 5,
            "len_max": 180,
            "offset": 0,
        }
        for _ in range(5):  # up to ~250 results
            time.sleep(REQUEST_SLEEP)
            r = requests.get(base, headers=headers, params=params, timeout=HTTP_TIMEOUT)
            if r.status_code != 200:
                break
            data = r.json()
            for ep in data.get("results", []):
                audio = ep.get("audio")
                title = ep.get("title_original") or ep.get("title")
                podcast_name = ep.get("podcast", {}).get("title_original") or ep.get("podcast", {}).get("title")
                url = ep.get("listennotes_url") or ep.get("link") or audio
                hits.append(
                    Hit(
                        source="listennotes",
                        title=title or "",
                        url=url or "",
                        published=ep.get("pub_date_ms"),
                        podcast_name=podcast_name,
                        enclosure_url=audio,
                        enclosure_type=None,
                        duration=str(ep.get("audio_length_sec")) if ep.get("audio_length_sec") else None,
                        transcript_url=None,
                        notes_url=ep.get("link"),
                        feed_url=None,
                    )
                )
            next_off = data.get("next_offset")
            if next_off is None or next_off == params["offset"]:
                break
            params["offset"] = next_off
    return hits


def gcs_web_sweep(queries: List[str]) -> List[Hit]:
    """Google Custom Search sweep for mp3/blog interview pages (optional)."""
    api_key = os.getenv("GCS_API_KEY")
    cx = os.getenv("GCS_CX")
    if not api_key or not cx:
        return []
    hits: List[Hit] = []
    base = "https://www.googleapis.com/customsearch/v1"
    q_templates = [
        '{term} podcast interview',
        '{term} audio interview',
        '{term} mp3',
        '{term} site:podcasts.apple.com',
        '{term} site:spotify.com/episode',
        '{term} site:soundcloud.com',
        '{term} site:podbean.com',
        '{term} site:libsyn.com',
        '{term} site:ttbook.org',
        '{term} site:psychedelicstoday.com',
        '{term} site:resources.soundstrue.com',
        '{term} site:accidentalgods.life',
        '{term} site:newthinkingallowed.org',
    ]
    for term in queries:
        for tmpl in q_templates:
            q = tmpl.format(term=term)
            params = {"key": api_key, "cx": cx, "q": q, "num": 10}
            time.sleep(REQUEST_SLEEP)
            r = _get(base, params=params)
            if not r:
                continue
            data = r.json()
            for item in data.get("items", []):
                title = item.get("title", "")
                link = item.get("link", "")
                snippet = item.get("snippet", "")
                # Heuristic accept
                if any(x in link.lower() for x in ("/episode", ".mp3", "podcast")) or EPISODE_MATCH_RE.search(snippet):
                    hits.append(
                        Hit(
                            source="gcs",
                            title=title,
                            url=link,
                            published=None,
                            podcast_name=None,
                            enclosure_url=link if link.endswith(".mp3") else None,
                            enclosure_type=None,
                            duration=None,
                            transcript_url=None,
                            notes_url=link,
                            feed_url=None,
                        )
                    )
    return hits


def dedupe(hits: List[Hit]) -> List[Hit]:
    seen: Dict[str, Hit] = {}
    for h in hits:
        key = (h.enclosure_url or h.url).strip().lower()
        if key in seen:
            # Merge sparse fields into the richer one
            rich = seen[key]
            for f in dataclasses.fields(Hit):
                name = f.name
                if getattr(rich, name) in (None, "") and getattr(h, name):
                    setattr(rich, name, getattr(h, name))
        else:
            seen[key] = h
    return list(seen.values())


def export(out_base: str, hits: List[Hit]) -> Tuple[str, str]:
    os.makedirs(os.path.dirname(out_base) or ".", exist_ok=True)
    json_path = f"{out_base}.json"
    csv_path = f"{out_base}.csv"

    # Sort by published (desc) when possible, else title
    def sort_key(h: Hit):
        return (h.published or "", h.title or "")
    hits_sorted = sorted(hits, key=sort_key, reverse=True)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump([asdict(h) for h in hits_sorted], f, ensure_ascii=False, indent=2)

    cols = [
        "source", "title", "url", "published", "podcast_name",
        "enclosure_url", "enclosure_type", "duration",
        "transcript_url", "notes_url", "feed_url",
        "itunes_collection_id", "itunes_track_id",
    ]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for h in hits_sorted:
            w.writerow({k: getattr(h, k) for k in cols})

    return json_path, csv_path


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Find audio-only podcasts/blog interviews featuring Chris Bache.")
    ap.add_argument("--out", default=DEFAULT_OUT_BASENAME, help="Output basename (no extension). Default: bache_audio_results")
    ap.add_argument("--no-apple-episodes", action="store_true", help="Skip Apple episode search")
    ap.add_argument("--no-apple-rss", action="store_true", help="Skip Apple podcast RSS parsing")
    ap.add_argument("--no-listennotes", action="store_true", help="Skip Listen Notes even if key present")
    ap.add_argument("--no-gcs", action="store_true", help="Skip Google Custom Search even if keys present")
    args = ap.parse_args()

    # 1) Apple podcast episodes (direct)
    hits: List[Hit] = []
    if not args.no_apple_episodes:
        print("Searching Apple Podcasts (episodes)…")
        hits += apple_search_episodes(PERSON_TERMS)

    # 2) Apple podcast feeds + RSS parse
    if not args.no_apple_rss:
        print("Searching Apple Podcasts (podcast feeds + RSS)…")
        # Combine person + topic terms to broaden feed discovery
        feed_terms = list(PERSON_TERMS) + list(TOPIC_TERMS)
        feeds = apple_search_podcasts_and_rss(feed_terms)
        print(f"  Found {len(feeds)} candidate feeds")
        for i, feed in enumerate(feeds, 1):
            print(f"  [{i}/{len(feeds)}] Parse feed: {feed}")
            try:
                hits += parse_rss_for_bache(feed)
            except Exception:
                # Keep going; some feeds will be malformed or blocked
                pass

    # 3) Listen Notes (optional)
    if not args.no_listennotes:
        if os.getenv("LISTENNOTES_API_KEY"):
            print("Searching Listen Notes (optional)…")
            hits += listen_notes_search(PERSON_TERMS + TOPIC_TERMS)
        else:
            print("Skipping Listen Notes (LISTENNOTES_API_KEY not set)")

    # 4) Google Custom Search (optional)
    if not args.no_gcs:
        if os.getenv("GCS_API_KEY") and os.getenv("GCS_CX"):
            print("Sweeping the web via Google Custom Search (optional)…")
            hits += gcs_web_sweep(PERSON_TERMS + TOPIC_TERMS)
        else:
            print("Skipping GCS (GCS_API_KEY or GCS_CX not set)")

    # 5) De-duplicate + export
    print(f"Total raw hits: {len(hits)}")
    hits = dedupe(hits)
    print(f"De-duped hits: {len(hits)}")

    json_path, csv_path = export(args.out, hits)
    print(f"Wrote: {json_path}")
    print(f"Wrote: {csv_path}")
    print("\nTip: spot-check any ‘notes_url’ pages for transcripts to ingest later.")


if __name__ == "__main__":
    main()
