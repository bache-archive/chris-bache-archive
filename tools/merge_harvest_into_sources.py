#!/usr/bin/env python3
# tools/merge_harvest_into_sources.py
"""
Merge harvested quote packs into docs/educational/*/sources.json.

Supports BOTH layouts:
  reports/quote_packs/<DATE>/<qid>/{talks.search.json,book.search.json}
  reports/quote_packs/<qid>/{talks.search.json,book.search.json}

Usage:
  python3 tools/merge_harvest_into_sources.py
  python3 tools/merge_harvest_into_sources.py --reports-root reports/quote_packs
"""

from __future__ import annotations
from pathlib import Path
import json, re, argparse
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "educational"

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reports-root", default=str(ROOT / "reports" / "quote_packs"),
                    help="Path to quote_packs root (dated or flat).")
    return ap.parse_args()

def find_latest_root(base: Path) -> Path | None:
    if not base.exists():
        return None
    dated = [p for p in base.iterdir() if p.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name)]
    return (sorted(dated, reverse=True)[0] if dated else base)

def find_pack_json(search_root: Path, qid: str, kind: str) -> Path | None:
    # kind in {"talks", "book"}
    candidates = [
        search_root / qid / f"{kind}.search.json",
        search_root / qid / "search.json" if kind == "talks" else None,
    ]
    for c in candidates:
        if c and c.exists():
            return c
    for c in search_root.rglob(f"{kind}.search.json"):
        if c.parent.name == qid:
            return c
    if kind == "talks":
        for c in search_root.rglob("search.json"):
            if c.parent.name == qid:
                return c
    return None

# -------- normalizers --------

def norm_talk_chunk(c: dict) -> dict:
    out = {
        "text": (c.get("text") or "").strip(),
        "ts_url": c.get("ts_url") or c.get("url") or "",
        "archival_title": c.get("archival_title") or c.get("title") or "",
        "recorded_date": c.get("recorded_date") or c.get("date") or "",
        "_score": c.get("_score"),
    }
    for k in ("start_hhmmss", "hhmmss", "time_hhmmss"):
        if c.get(k):
            out["start_hhmmss"] = c[k]
            break
    return out

def norm_book_chunk(c: dict) -> dict:
    # Be tolerant of field names from the harvester
    return {
        "text": (c.get("text") or "").strip(),
        "citation": (c.get("citation") or c.get("label") or "").strip(),
        "chapter_code": c.get("chapter_code") or c.get("chapter") or "",
        "section_code": c.get("section_code") or c.get("section") or "",
        "archival_title": c.get("archival_title") or "",  # optional
        "_score": c.get("_score"),
    }

def merge_chunks(existing: list[dict], new_items: list[dict], key_fields: tuple[str, ...]) -> int:
    # Build a seen set based on key_fields tuple
    def key_of(d: dict):
        return tuple((d.get(k) or "").strip() for k in key_fields)
    seen = {key_of(e) for e in existing}
    added = 0
    for it in new_items:
        if not it: 
            continue
        if key_of(it) in seen:
            continue
        existing.append(it)
        seen.add(key_of(it))
        added += 1
    return added

def main():
    args = parse_args()
    reports_root = Path(args.reports_root)
    search_root = find_latest_root(reports_root)
    if not search_root:
        raise SystemExit(f"[error] missing reports root: {reports_root}")
    print(f"[info] using harvest root: {search_root}")

    merged = 0
    total_added_book = 0
    total_added_talks = 0

    for sj in sorted(DOCS.glob("*/sources.json")):
        qid = sj.parent.name

        talks_json = find_pack_json(search_root, qid, "talks")
        book_json  = find_pack_json(search_root, qid, "book")

        if not talks_json and not book_json:
            print(f"[warn] no quote packs found for {qid}")
            continue

        data = json.loads(sj.read_text(encoding="utf-8"))

        # ensure structure
        book = data.setdefault("book", {})
        talks = data.setdefault("talks", {})
        book_chunks  = book.setdefault("chunks", [])
        talk_chunks  = talks.setdefault("chunks", [])

        added_book = 0
        added_talks = 0

        if book_json and book_json.exists():
            raw = json.loads(book_json.read_text(encoding="utf-8"))
            chunks = raw.get("chunks") if isinstance(raw, dict) else raw
            normed = [norm_book_chunk(c) for c in (chunks or []) if (c.get("text") or "").strip()]
            added_book = merge_chunks(book_chunks, normed, ("text", "citation", "chapter_code", "section_code"))

        if talks_json and talks_json.exists():
            raw = json.loads(talks_json.read_text(encoding="utf-8"))
            chunks = raw.get("chunks") if isinstance(raw, dict) else raw
            normed = [norm_talk_chunk(c) for c in (chunks or []) if (c.get("text") or "").strip()]
            added_talks = merge_chunks(talk_chunks, normed, ("text", "ts_url"))

        if added_book or added_talks:
            data.setdefault("meta", {})["date"] = datetime.today().date().isoformat()
            sj.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"[ok] {qid}: +{added_book} book, +{added_talks} talks → {sj}")
            merged += 1
            total_added_book += added_book
            total_added_talks += added_talks
        else:
            print(f"[=] {qid}: no new chunks")

    print(f"\nMerged {merged} module(s). Added {total_added_book} book and {total_added_talks} talk chunks total.")

if __name__ == "__main__":
    main()