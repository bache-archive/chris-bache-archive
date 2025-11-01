#!/usr/bin/env python3
import argparse, csv, json, re

AUDIO_EXTS = (".mp3",".m4a",".aac",".ogg",".oga",".opus",".mp4")
def looks_audio(url: str|None, mime: str|None) -> bool:
    if mime and mime.lower().startswith("audio/"):
        return True
    if url:
        u = url.split("?",1)[0].lower()
        return any(u.endswith(ext) for ext in AUDIO_EXTS)
    return False

KEEP_COLS = [
    "source","podcast_name","title","published","url","notes_url",
    "enclosure_url","enclosure_type","duration","feed_url",
    "itunes_collection_id","itunes_track_id"
]

def main():
    ap = argparse.ArgumentParser(description="Filter to strict audio enclosures.")
    ap.add_argument("--src_json", required=True, help="out/bache_audio.json (or enriched)")
    ap.add_argument("--out_csv", required=True, help="Path to write CSV with only true audio enclosures")
    args = ap.parse_args()

    with open(args.src_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = []
    for h in data:
        enc = h.get("enclosure_url")
        mime = h.get("enclosure_type")
        if looks_audio(enc, mime):
            rows.append({k: h.get(k) for k in KEEP_COLS})

    with open(args.out_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=KEEP_COLS)
        w.writeheader(); w.writerows(rows)

    print(f"Kept {len(rows)} rows with strict audio enclosures → {args.out_csv}")

if __name__ == "__main__":
    main()
