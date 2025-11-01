#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Merge a patch (array of records) into the canonical index.json,
dedupe by youtube_id (preferred) then slug, and sort by published date.
Optionally validate that media files exist relative to --root.

Usage:
  python tools/curation/merge_index.py \
    --base index.json \
    --patch patches/2025-10-31-bache-youtube/work/index.patch.json \
    --out  patches/2025-10-31-bache-youtube/outputs/index.merged.json \
    --root . \
    --validate-paths
"""

import argparse, json, os, sys
from datetime import datetime
from pathlib import Path

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Accept either a list or an object with "items"
    if isinstance(data, dict) and "items" in data and isinstance(data["items"], list):
        return data["items"]
    if isinstance(data, list):
        return data
    raise SystemExit(f"[error] Unsupported JSON structure in {path}")

def write_json(path, items):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
        f.write("\n")

def key_for(record):
    yt = (record.get("youtube_id") or "").strip()
    if yt:
        return ("yt", yt)
    sl = (record.get("slug") or "").strip()
    if sl:
        return ("slug", sl)
    # Fallback: archival_title + published
    return ("title_pub", (record.get("archival_title") or "", record.get("published") or ""))

def parse_date(s):
    if not s:
        return datetime.max
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except Exception:
        # tolerate ISO 8601 datetime
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d")
        except Exception:
            return datetime.max

def merge_records(base, patch):
    index = {}
    order = []  # preserve base order; new items append

    # Seed from base
    for rec in base:
        k = key_for(rec)
        index[k] = rec
        order.append(k)

    # Apply patch (upsert)
    applied = 0
    for rec in patch:
        k = key_for(rec)
        if k in index:
            # merge shallowly; patch wins
            merged = dict(index[k])
            # deep-merge "media" if both present
            if "media" in index[k] and "media" in rec:
                m = dict(index[k]["media"])
                m.update(rec["media"])
                rec = dict(rec)
                rec["media"] = m
            merged.update(rec)
            index[k] = merged
        else:
            index[k] = rec
            order.append(k)
        applied += 1

    # Build list and sort by published asc
    items = [index[k] for k in order]
    items.sort(key=lambda r: (parse_date(r.get("published")), r.get("slug") or "", r.get("youtube_id") or ""))

    return items, applied

def validate_paths(items, root):
    missing = []
    rootp = Path(root)
    for rec in items:
        media = rec.get("media") or {}
        for fkey in ("audio", "video"):
            rel = media.get(fkey)
            if not rel:
                continue
            p = rootp / rel
            if not p.exists():
                missing.append(rel)
    return sorted(set(missing))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="Path to canonical index.json (root of repo)")
    ap.add_argument("--patch", required=True, help="Path to patch JSON (array of records)")
    ap.add_argument("--out", required=True, help="Output path for merged index")
    ap.add_argument("--root", default=".", help="Repo root for path validation")
    ap.add_argument("--validate-paths", action="store_true", help="Validate that media paths exist")
    args = ap.parse_args()

    base = load_json(args.base)
    patch = load_json(args.patch)

    merged, applied = merge_records(base, patch)
    write_json(args.out, merged)

    print(f"[merge] base={len(base)}  patch={len(patch)}  applied={applied}  out={len(merged)}")
    print(f"[sort]  merged index sorted by 'published' (YYYY-MM-DD)")

    if args.validate_paths:
        missing = validate_paths(merged, args.root)
        if missing:
            print(f"[warn] {len(missing)} missing media paths:")
            for m in missing:
                print(f"  - {m}")
            sys.exit(2)
        else:
            print("[ok] all referenced media paths exist")

if __name__ == "__main__":
    main()
