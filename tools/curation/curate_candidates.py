#!/usr/bin/env python3
import json, argparse, re
from pathlib import Path

ALLOW_CHANNELS = {
    "New Thinking Allowed with Jeffrey Mishlove",
    "Buddha at the Gas Pump",
    "SAND", "Science and Nonduality", "Psychedelics Today",
    "Alex Tsakiris", "Theories of Everything with Curt Jaimungal",
    "The Stoa", "Evolve and Ascend",
    "Spirit Plant Medicine", "Magical Egypt",
    "OMTimesTV", "OMTimes Media",
    "Vancouver IONS Community Group",
    "Psychedelic Society of Asheville (PSA)",
    "The Human Experience Podcast",
}

NEGATIVE_TITLE_HINTS = [
    r"\bAI\b.*\bcustomer service\b",
    r"\bHearth\b",                  # business/contracting show
    r"\bowned and operated\b",
]

def main():
    ap = argparse.ArgumentParser(description="Curate candidate list into an index.patch.json")
    ap.add_argument("--in", dest="inpath", default="candidates.bache.youtube.json")
    ap.add_argument("--out", dest="outpath", default="index.patch.json")
    ap.add_argument("--min-score", type=int, default=3)
    ap.add_argument("--min-duration-sec", type=int, default=600)
    ap.add_argument("--require-name-in-title", action="store_true")
    ap.add_argument("--allow-all-channels", action="store_true", help="Ignore ALLOW_CHANNELS gate")
    args = ap.parse_args()

    data = json.loads(Path(args.inpath).read_text())
    cand = data.get("candidates", [])

    out = []
    for c in cand:
        score = c.get("score", 0)
        dur = c.get("duration_sec") or 0
        title = (c.get("title") or "").strip()
        channel = (c.get("channel_title") or "").strip()
        flags = c.get("flags", {})
        vid = c.get("video_id")
        published = c.get("published_at")

        if score < args.min_score: 
            continue
        if dur < args.min_duration_sec:
            continue
        if args.require_name_in_title and not (flags.get("full_name_title") or flags.get("chris_name_title")):
            continue
        # drop negative patterns (business/other Chris)
        if any(re.search(p, title, re.I) for p in NEGATIVE_TITLE_HINTS):
            continue
        # optional channel allowlist
        if not args.allow_all_channels and ALLOW_CHANNELS and (channel not in ALLOW_CHANNELS):
            # still allow if "Christopher" in title
            if not re.search(r"\bChristopher\b", title, re.I):
                continue

        out.append({
            "youtube_id": vid,
            "title": title,
            "channel": channel,
            "published_at": published,
            "source_type": "interview",   # adjust per your taxonomy
            "status": "pending"           # you’ll change to verified after transcript/metadata pass
        })

    Path(args.outpath).write_text(json.dumps(out, indent=2))
    print(f"[done] wrote {len(out)} curated entries → {args.outpath}")

if __name__ == "__main__":
    main()
