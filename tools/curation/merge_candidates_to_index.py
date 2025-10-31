#!/usr/bin/env python3
import json, sys, datetime, pathlib

patch_path = pathlib.Path("index.patch.json")
index_path = pathlib.Path("index.json")
out_path = pathlib.Path("index.merged.json")

index = json.loads(index_path.read_text())
patch = json.loads(patch_path.read_text())

# Normalize patch entries → archive-style stubs
merged_items = []
for item in patch:
    youtube_id = item["youtube_id"]
    youtube_url = f"https://youtu.be/{youtube_id}"
    merged_items.append({
        "archival_title": item["title"],
        "channel": item["channel"],
        "source_type": item.get("source_type", "interview"),
        "transcript": None,
        "diarist": None,
        "youtube_id": youtube_id,
        "youtube_url": youtube_url,
        "web_url": "",
        "duration_hms": None,
        "media": {},
        "blob_url": "",
        "raw_url": "",
        "published": item.get("published_at", "")[:10],
        "status": item.get("status", "pending"),
        "notes": "Auto-imported candidate; not yet diarized or verified.",
        "imported_at": datetime.datetime.now(datetime.UTC).isoformat()
    })

# Combine + deduplicate
all_items = {entry["youtube_id"]: entry for entry in index if entry.get("youtube_id")}
for m in merged_items:
    if m["youtube_id"] not in all_items:
        all_items[m["youtube_id"]] = m

# Sort by published descending
merged_sorted = sorted(
    all_items.values(),
    key=lambda e: e.get("published", ""),
    reverse=True
)

out_path.write_text(json.dumps(merged_sorted, indent=2))
print(f"[done] wrote merged file: {out_path}")
