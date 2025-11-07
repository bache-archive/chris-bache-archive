#!/usr/bin/env python3
"""
tools/transcripts/normalize_front_matter.py

Normalize front matter for sources/transcripts/*.md to a lean, DRY, evergreen schema.

- Canonical fields pulled from index.json: title, date (published), type, channel
- Drops legacy / duplicate keys (e.g., youtube_id, archival_title, speakers, published)
- Retains diarist_sha1 and transcription_date (both under provenance)
- Keeps 'recorded' only if distinct from date (as provenance.recorded)
- Keeps transcriber (from transcriber/Transcriber) as provenance.transcriber
- Adds identifiers (Wikidata/OpenAlex) and people (Chris only)
- Adds provenance.source and diarist_txt/srt pointers if files exist

Usage:
  python tools/transcripts/normalize_front_matter.py            # dry run (default)
  python tools/transcripts/normalize_front_matter.py --write    # write changes
  python tools/transcripts/normalize_front_matter.py --only "2025-10-*.md" --write
"""

from __future__ import annotations
from pathlib import Path
import argparse, json, re, sys, fnmatch
from datetime import datetime

# --- Paths ---------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
TRANS_DIR = ROOT / "sources" / "transcripts"
DIARIST_DIR = ROOT / "sources" / "diarist"
INDEX_JSON = ROOT / "index.json"

# --- Constants -----------------------------------------------------------
WIKIDATA_PERSON = "Q112496741"
OPENALEX_PERSON = "A5045900737"

TYPE_MAP = {
    "talk": "lecture",
    "lecture": "lecture",
    "keynote": "lecture",
    "address": "lecture",
    "interview": "interview",
    "conversation": "interview",
    "panel": "panel",
    "panel-discussion": "panel",
    "discussion": "panel",
    "q&a": "qanda",
    "qa": "qanda",
    "qanda": "qanda",
    "reading": "reading",
    "clip": "clip",
}

# --- Front matter parsing ------------------------------------------------
FM_RE = re.compile(r'^\s*---\s*\n(.*?)\n---\s*\n(.*)\Z', re.S)

def split_front_matter(text: str):
    m = FM_RE.match(text)
    if not m:
        return "", text
    return m.group(1), m.group(2)

def load_index():
    try:
        data = json.loads(INDEX_JSON.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[error] cannot load index.json: {e}", file=sys.stderr)
        sys.exit(1)
    items = data["items"] if isinstance(data, dict) and "items" in data else data
    return {Path(it.get("transcript", "")).stem: it for it in items if it.get("transcript", "").endswith(".md")}

def canon_type(source_type: str) -> str:
    return TYPE_MAP.get((source_type or "").strip().lower(), "other")

def iso_date_or_empty(s: str) -> str:
    s = (s or "").strip()
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return s
    except Exception:
        return ""

def file_exists(p: Path) -> bool:
    try:
        return p.exists()
    except Exception:
        return False

def yaml_str(x):
    if x is None:
        return "null"
    s = str(x)
    if (
        s == ""
        or any(c in s for c in [":", "#", "{", "}", "[", "]", ",", "&", "*", "!", "|", ">", "'", '"'])
        or s.strip() != s
    ):
        s = s.replace('"', '\\"')
        return f"\"{s}\""
    return s

def build_yaml(meta: dict) -> str:
    lines = []

    def emit(k, v, indent=0):
        pad = "  " * indent
        if isinstance(v, dict):
            lines.append(f"{pad}{k}:")
            for kk in v:
                emit(kk, v[kk], indent + 1)
        elif isinstance(v, list):
            lines.append(f"{pad}{k}:")
            for item in v:
                if isinstance(item, dict):
                    lines.append(f"{pad}-")
                    for kk in item:
                        lines.append(f"{pad}  {kk}: {yaml_str(item[kk])}")
                else:
                    lines.append(f"{pad}- {yaml_str(item)}")
        else:
            lines.append(f"{pad}{k}: {yaml_str(v)}")

    order = [
        "title",
        "slug",
        "date",
        "type",
        "channel",
        "language",
        "license",
        "identifiers",
        "people",
        "provenance",
    ]
    for k in order:
        if k in meta:
            emit(k, meta[k])
    for k in meta:
        if k not in order:
            emit(k, meta[k])
    return "---\n" + "\n".join(lines) + "\n---\n"

def parse_kv_front_matter(fm_text: str) -> dict:
    meta = {}
    for line in fm_text.splitlines():
        if not line.strip() or ":" not in line:
            continue
        k, v = line.split(":", 1)
        meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="Write changes to files (default: dry run)")
    ap.add_argument("--only", default="", help="Glob to limit which .md files to process (e.g., '2025-10-*.md')")
    args = ap.parse_args()

    index = load_index()
    md_files = sorted(TRANS_DIR.glob("*.md"))
    if args.only:
        md_files = [p for p in md_files if fnmatch.fnmatch(p.name, args.only)]

    changed, total = 0, 0

    for md in md_files:
        total += 1
        text = md.read_text(encoding="utf-8")
        fm_text, body = split_front_matter(text)
        old_meta = parse_kv_front_matter(fm_text) if fm_text else {}
        slug = md.stem
        idx = index.get(slug, {})

        title = idx.get("archival_title") or old_meta.get("title") or slug.replace("-", " ")
        date = iso_date_or_empty(idx.get("published") or old_meta.get("date") or old_meta.get("published"))
        ty = canon_type(idx.get("source_type") or old_meta.get("type"))
        channel = idx.get("channel") or old_meta.get("channel") or ""
        transcriber = old_meta.get("transcriber") or old_meta.get("Transcriber")
        recorded = iso_date_or_empty(old_meta.get("recorded"))
        if recorded == date:
            recorded = ""

        diarist_txt = DIARIST_DIR / f"{slug}.txt"
        diarist_srt = DIARIST_DIR / f"{slug}.srt"
        have_txt = file_exists(diarist_txt)
        have_srt = file_exists(diarist_srt)

        new_meta = {
            "title": title,
            "slug": slug,
            "date": date or "",
            "type": ty,
            "channel": channel,
            "language": "en",
            "license": "CC0-1.0",
            "identifiers": {
                "wikidata_person": WIKIDATA_PERSON,
                "openalex_person": OPENALEX_PERSON,
            },
            "people": [
                {
                    "name": "Christopher M. Bache",
                    "wikidata": WIKIDATA_PERSON,
                    "openalex": OPENALEX_PERSON,
                }
            ],
            "provenance": {
                "source": "otter+diarist->normalization",
            },
        }

        # Optional provenance fields
        if transcriber:
            new_meta["provenance"]["transcriber"] = transcriber
        if recorded:
            new_meta["provenance"]["recorded"] = recorded
        if have_txt:
            new_meta["provenance"]["diarist_txt"] = str(diarist_txt.as_posix())
        if have_srt:
            new_meta["provenance"]["diarist_srt"] = str(diarist_srt.as_posix())

        # Preserve diarist_sha1 and transcription_date if found
        dsha1 = old_meta.get("diarist_sha1")
        tdate = iso_date_or_empty(old_meta.get("transcription_date"))
        if dsha1:
            new_meta["provenance"]["diarist_sha1"] = dsha1
        if tdate:
            new_meta["provenance"]["transcription_date"] = tdate

        new_fm = build_yaml(new_meta)
        new_text = new_fm + body

        if new_text != text:
            changed += 1
            rel = md.relative_to(ROOT)
            if args.write:
                md.write_text(new_text, encoding="utf-8")
                print(f"[write] {rel}")
            else:
                print(f"[diff]  {rel}")
                print(f"       title: {old_meta.get('title','(none)')}  →  {title}")
                print(f"       date : {old_meta.get('date') or '(none)'}  →  {date or '(empty)'}")
                print(f"       type : {old_meta.get('type','(none)')}  →  {ty}")
                print(f"       chan : {old_meta.get('channel','(none)')}  →  {channel}")
                if old_meta.get('diarist_sha1'):
                    print(f"       keep : diarist_sha1")
                if old_meta.get('transcription_date'):
                    print(f"       keep : transcription_date")

    print(f"\nDone: normalized {changed} / {total} files ({'written' if args.write else 'dry-run'} mode).")

if __name__ == "__main__":
    main()