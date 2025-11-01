#!/usr/bin/env python3
"""
summarize_audio_results.py

Reads the JSON produced by tools/intake/find_bache_audio.py and emits:
  - Console summary: totals + top podcasts
  - podcasts_by_count.csv
  - episodes_ready_for_download.csv    (has enclosure_url)
  - episodes_missing_audio.csv         (no enclosure_url; follow up manually)
  - unique_hosts.txt                   (distinct page hosts from `url`)

Usage:
  python3 tools/curation/summarize_audio_results.py out/bache_audio.json
  python3 tools/curation/summarize_audio_results.py out/bache_audio.json --outdir reports/

Notes:
  - Treats items as unique by enclosure_url if present, else by url.
  - Filters obvious non-audio or duplicates.
"""

import argparse
import csv
import json
import os
from collections import Counter, defaultdict
from urllib.parse import urlparse

AUDIO_EXTS = (".mp3", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".mp4")  # mp4 is used for audio by some podcasts
AUDIO_MIMES = ("audio/",)

KEEP_COLS = [
    "source",
    "podcast_name",
    "title",
    "published",
    "url",
    "notes_url",
    "enclosure_url",
    "enclosure_type",
    "duration",
    "feed_url",
    "itunes_collection_id",
    "itunes_track_id",
]

def _looks_audio(url: str | None, mime: str | None) -> bool:
    if mime:
        if any(mime.lower().startswith(m) for m in AUDIO_MIMES):
            return True
    if url:
        path = urlparse(url).path.lower()
        if any(path.endswith(ext) for ext in AUDIO_EXTS):
            return True
    return False

def load_hits(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Expected a list of hits in JSON.")
    return data

def dedupe(hits: list[dict]) -> list[dict]:
    seen = {}
    for h in hits:
        key = (h.get("enclosure_url") or h.get("url") or "").strip().lower()
        if not key:
            continue
        if key in seen:
            # enrich sparse fields
            rich = seen[key]
            for k, v in h.items():
                if (rich.get(k) in (None, "", [])) and v not in (None, "", []):
                    rich[k] = v
        else:
            seen[key] = dict(h)
    return list(seen.values())

def write_csv(path: str, rows: list[dict], cols: list[str]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c) for c in cols})

def main():
    ap = argparse.ArgumentParser(description="Summarize Bache audio JSON results.")
    ap.add_argument("json_path", help="Path to JSON output from find_bache_audio.py")
    ap.add_argument("--outdir", default=None, help="Directory for CSV/TXT outputs (default: alongside JSON)")
    ap.add_argument("--top", type=int, default=20, help="Show top N podcasts in console (default: 20)")
    args = ap.parse_args()

    hits_raw = load_hits(args.json_path)
    hits = dedupe(hits_raw)

    # Bucket by podcast_name and detect audio vs missing
    by_podcast = defaultdict(list)
    ready = []   # has enclosure_url and looks like audio
    missing = [] # no enclosure_url or not clearly audio
    hosts = set()

    for h in hits:
        pn = (h.get("podcast_name") or "").strip() or "(unknown podcast)"
        by_podcast[pn].append(h)

        page_url = h.get("url") or h.get("notes_url")
        if page_url:
            try:
                hosts.add(urlparse(page_url).netloc.lower())
            except Exception:
                pass

        enc_url = h.get("enclosure_url")
        enc_type = h.get("enclosure_type")
        if enc_url and _looks_audio(enc_url, enc_type or ""):
            ready.append(h)
        else:
            missing.append(h)

    # Sort podcasts by count
    counts = Counter({k: len(v) for k, v in by_podcast.items()})
    top_podcasts = counts.most_common(args.top)

    total = len(hits)
    total_ready = len(ready)
    total_missing = len(missing)

    # Console summary
    print("=== Bache Audio Discovery Summary ===")
    print(f"Input JSON: {args.json_path}")
    print(f"Total unique hits: {total}")
    print(f"  Ready for download (has audio enclosure): {total_ready}")
    print(f"  Needs follow-up (no clear audio link):   {total_missing}")
    print()
    print("Top podcasts by episode count:")
    for name, n in top_podcasts:
        print(f"  {n:3d}  {name}")

    # Output paths
    outdir = args.outdir or os.path.dirname(os.path.abspath(args.json_path)) or "."
    os.makedirs(outdir, exist_ok=True)
    podcasts_csv = os.path.join(outdir, "podcasts_by_count.csv")
    ready_csv = os.path.join(outdir, "episodes_ready_for_download.csv")
    missing_csv = os.path.join(outdir, "episodes_missing_audio.csv")
    hosts_txt = os.path.join(outdir, "unique_hosts.txt")

    # Write files
    # 1) by-podcast counts
    write_csv(
        podcasts_csv,
        [{"podcast_name": name, "count": n} for name, n in counts.most_common()],
        ["podcast_name", "count"],
    )

    # 2) episodes ready
    write_csv(ready_csv, ready, KEEP_COLS)

    # 3) episodes missing
    write_csv(missing_csv, missing, KEEP_COLS)

    # 4) hosts
    with open(hosts_txt, "w", encoding="utf-8") as f:
        for h in sorted(hosts):
            f.write(h + "\n")

    print("\nWritten:")
    print(f"  {podcasts_csv}")
    print(f"  {ready_csv}")
    print(f"  {missing_csv}")
    print(f"  {hosts_txt}")
    print("\nNext:")
    print("  • Feed episodes_ready_for_download.csv → tools/media/download_media.py")
    print("  • Manually review episodes_missing_audio.csv pages for embedded players or links")
    print("  • Use unique_hosts.txt to whitelist useful domains in your CSE config")

if __name__ == "__main__":
    main()
