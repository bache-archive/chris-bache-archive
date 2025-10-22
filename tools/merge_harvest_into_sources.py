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
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "educational"

# ---------- args / discovery ----------

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--reports-root",
        default=str(ROOT / "reports" / "quote_packs"),
        help="Path to quote_packs root (dated or flat).",
    )
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

# ---------- helpers ----------

def _norm_str(v: Any) -> str:
    """Convert any JSON scalar to a trimmed string; None -> ''."""
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    return str(v).strip()

def _clean_text(s: Any) -> str:
    return _norm_str(s).replace("\r\n", "\n").replace("\r", "\n")

def _extract_chunks(raw: Any) -> list[dict]:
    """Accept either {'chunks':[...]} or a raw list."""
    if isinstance(raw, dict):
        ch = raw.get("chunks")
        return ch if isinstance(ch, list) else []
    if isinstance(raw, list):
        return raw
    return []

# ---------- normalizers (with guardrails) ----------

def _is_talkish(c: dict) -> bool:
    return bool(_norm_str(c.get("ts_url")) or _norm_str(c.get("recorded_date")) or _norm_str(c.get("start_hhmmss")))

def norm_talk_chunk(c: dict) -> dict:
    out = {
        "text": _clean_text(c.get("text")),
        "ts_url": _norm_str(c.get("ts_url") or c.get("url")),
        "archival_title": _norm_str(c.get("archival_title") or c.get("title")),
        "recorded_date": _norm_str(c.get("recorded_date") or c.get("date")),
        "_score": c.get("_score"),
    }
    # prefer any present timecode field
    for k in ("start_hhmmss", "hhmmss", "time_hhmmss"):
        vv = _norm_str(c.get(k))
        if vv:
            out["start_hhmmss"] = vv
            break
    return out

def norm_book_chunk(c: dict) -> dict:
    """
    Normalize book chunks and guarantee a non-empty 'citation'.
    Also drop talk-like entries that slipped in (ts_url / recorded_date / timecode).
    """
    # Drop talk-like contamination
    if _is_talkish(c):
        return {}

    text = _clean_text(c.get("text"))
    citation = _norm_str(c.get("citation") or c.get("label"))
    chapter_code = _norm_str(c.get("chapter_code") or c.get("chapter"))
    section_code = _norm_str(c.get("section_code") or c.get("section"))

    # Synthesize a useful citation if missing
    if not citation:
        # Prefer structured pointer if present
        pointer = " ".join(p for p in (chapter_code, section_code) if p)
        citation = ("LSD and the Mind of the Universe " + pointer).strip() if pointer else "LSD and the Mind of the Universe"

    return {
        "text": text,
        "citation": citation,
        "chapter_code": chapter_code,
        "section_code": section_code,
        "archival_title": _norm_str(c.get("archival_title")),
        "_score": c.get("_score"),
    }

def merge_chunks(existing: list[dict], new_items: Iterable[dict], key_fields: tuple[str, ...]) -> int:
    """Dedup by key tuple; key elements are stringified safely."""
    def key_of(d: dict):
        return tuple(_norm_str(d.get(k, "")) for k in key_fields)

    seen = {key_of(e) for e in existing if isinstance(e, dict)}
    added = 0
    for it in new_items:
        if not isinstance(it, dict):
            continue
        # skip empties from filters
        if not _norm_str(it.get("text")):
            continue
        k = key_of(it)
        if k in seen:
            continue
        existing.append(it)
        seen.add(k)
        added += 1
    return added

# ---------- main ----------

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
            chunks = _extract_chunks(raw)
            normed = []
            dropped_talkish = 0
            missing_citation = 0
            for c in chunks:
                if not isinstance(c, dict):
                    continue
                if _is_talkish(c):
                    dropped_talkish += 1
                    continue
                nb = norm_book_chunk(c)
                if not _norm_str(nb.get("citation")):
                    missing_citation += 1
                    continue
                if _norm_str(nb.get("text")):
                    normed.append(nb)
            if dropped_talkish:
                print(f"[warn] {qid}: filtered {dropped_talkish} talk-like item(s) from book.search.json")
            if missing_citation:
                print(f"[warn] {qid}: filtered {missing_citation} book item(s) without citation after normalization")
            added_book = merge_chunks(book_chunks, normed, ("text", "citation", "chapter_code", "section_code"))

        if talks_json and talks_json.exists():
            raw = json.loads(talks_json.read_text(encoding="utf-8"))
            chunks = _extract_chunks(raw)
            normed = []
            for c in chunks:
                if not isinstance(c, dict):
                    continue
                # require some talk anchor
                if not (_norm_str(c.get("ts_url")) or _norm_str(c.get("recorded_date")) or _norm_str(c.get("start_hhmmss"))):
                    continue
                nt = norm_talk_chunk(c)
                if _norm_str(nt.get("text")):
                    normed.append(nt)
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