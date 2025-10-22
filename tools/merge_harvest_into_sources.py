#!/usr/bin/env python3
# tools/merge_harvest_into_sources.py
"""
Clean-merge harvested quote packs into docs/educational/*/sources.json,
using a single, explicit harvest layout:

  reports/quote_packs/<DATE>/<QID>/
    ├─ book.search.json   # BOOKS ONLY
    └─ talks.search.json  # TALKS ONLY

Behavior:
  • Backs up and clears ALL existing sources.json (fresh start).
  • Loads from the MOST RECENT <DATE> under reports/quote_packs.
  • Strict separation + guardrails (no talk fields in books; no book-citation in talks).
  • Prints a validation summary at the end.

Usage:
  python3 tools/merge_harvest_into_sources.py
  python3 tools/merge_harvest_into_sources.py --reports-root reports/quote_packs
"""

from __future__ import annotations
from pathlib import Path
import json, re, argparse, shutil
from datetime import datetime
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "educational"
BACKUPS = ROOT / "backups" / "sources_json"

# ---------- args / discovery ----------

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--reports-root",
        default=str(ROOT / "reports" / "quote_packs"),
        help="Path to quote_packs (contains <DATE>/...). We'll pick the latest date.",
    )
    return ap.parse_args()

def latest_date_dir(base: Path) -> Path | None:
    if not base.exists():
        return None
    dated = [p for p in base.iterdir() if p.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name)]
    return (sorted(dated, reverse=True)[0] if dated else None)

def pack_file(root_date: Path, qid: str, kind: str) -> Path:
    # kind: "book" | "talks"
    return root_date / qid / f"{kind}.search.json"

# ---------- small utils ----------

def _norm_str(v: Any) -> str:
    if v is None: return ""
    return v.strip() if isinstance(v, str) else str(v).strip()

def _clean_text(s: Any) -> str:
    return _norm_str(s).replace("\r\n", "\n").replace("\r", "\n")

def _extract_chunks(raw: Any) -> list[dict]:
    if isinstance(raw, dict):
        ch = raw.get("chunks")
        return ch if isinstance(ch, list) else []
    if isinstance(raw, list):
        return raw
    return []

# ---------- normalization (with guardrails) ----------

def _is_talkish(c: dict) -> bool:
    return bool(
        _norm_str(c.get("ts_url") or c.get("url")) or
        _norm_str(c.get("recorded_date") or c.get("date")) or
        _norm_str(c.get("start_hhmmss") or c.get("hhmmss") or c.get("time_hhmmss"))
    )

def norm_book_chunk(c: dict) -> dict:
    """
    Normalize book chunks and guarantee non-empty 'citation'.
    Drop any talk-like entries completely.
    """
    if _is_talkish(c):
        return {}
    text = _clean_text(c.get("text"))
    if not text:
        return {}
    citation = _norm_str(c.get("citation") or c.get("label"))
    chapter_code = _norm_str(c.get("chapter_code") or c.get("chapter"))
    section_code = _norm_str(c.get("section_code") or c.get("section"))
    # Synthesize fallback citation if missing
    if not citation:
        ptr = " ".join(p for p in (chapter_code, section_code) if p)
        citation = ("LSDMU " + ptr).strip() if ptr else "LSDMU"
    return {
        "text": text,
        "citation": citation,
        "chapter_code": chapter_code,
        "section_code": section_code,
        "archival_title": _norm_str(c.get("archival_title")),
        "_score": c.get("_score"),
    }

def norm_talk_chunk(c: dict) -> dict:
    """
    Normalize talk chunks; require at least one talk anchor (url/date/timecode).
    """
    text = _clean_text(c.get("text"))
    ts_url = _norm_str(c.get("ts_url") or c.get("url"))
    recorded_date = _norm_str(c.get("recorded_date") or c.get("date"))
    start_hms = ""
    for k in ("start_hhmmss", "hhmmss", "time_hhmmss"):
        v = _norm_str(c.get(k))
        if v:
            start_hms = v
            break
    if not (ts_url or recorded_date or start_hms):
        return {}
    if not text:
        return {}
    return {
        "text": text,
        "ts_url": ts_url,
        "archival_title": _norm_str(c.get("archival_title") or c.get("title")),
        "recorded_date": recorded_date,
        "start_hhmmss": start_hms if start_hms else None,
        "_score": c.get("_score"),
    }

def dedup_append(dst: list[dict], items: Iterable[dict], key_fields: tuple[str, ...]) -> int:
    def key_of(d: dict) -> tuple[str, ...]:
        return tuple(_norm_str(d.get(k, "")) for k in key_fields)
    seen = {key_of(x) for x in dst if isinstance(x, dict)}
    added = 0
    for it in items:
        if not isinstance(it, dict): continue
        if not _norm_str(it.get("text")): continue
        k = key_of(it)
        if k in seen: continue
        dst.append(it)
        seen.add(k)
        added += 1
    return added

# ---------- backup + clear ----------

def backup_and_clear_all():
    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = BACKUPS / stamp
    dest.mkdir(parents=True, exist_ok=True)
    for sj in sorted(DOCS.glob("*/sources.json")):
        qid = sj.parent.name
        # backup
        out = dest / f"{qid}.sources.json"
        shutil.copy2(sj, out)
        # clear (fresh skeleton)
        sj.write_text(json.dumps(
            {"book":{"chunks":[]},"talks":{"chunks":[]},"meta":{}},
            ensure_ascii=False, indent=2
        ), encoding="utf-8")
    return dest

# ---------- validation ----------

def validate_all() -> tuple[int,int]:
    talkish_in_books = 0
    bookish_in_talks = 0
    for sj in sorted(DOCS.glob("*/sources.json")):
        data = json.loads(sj.read_text(encoding="utf-8"))
        # book section must not have talk-like keys
        for c in data.get("book",{}).get("chunks",[]) or []:
            if _is_talkish(c):
                talkish_in_books += 1
                print(f"⚠️  talk-like in book: {sj}  -> {c.get('archival_title') or c.get('citation') or ''}")
        # talks section must not have LSDMU-style book citations
        for c in data.get("talks",{}).get("chunks",[]) or []:
            cit = _norm_str(c.get("citation") or c.get("label"))
            if cit.startswith("LSDMU"):
                bookish_in_talks += 1
                print(f"⚠️  book-like in talks: {sj}  -> {cit}")
    return talkish_in_books, bookish_in_talks

# ---------- main ----------

def main():
    args = parse_args()
    reports_root = Path(args.reports_root)
    date_root = latest_date_dir(reports_root)
    if not date_root:
        raise SystemExit(f"[error] No dated harvest folders found under {reports_root}")

    print(f"[info] using harvest date root: {date_root}")
    backup_dir = backup_and_clear_all()
    print(f"[info] backed up previous sources to: {backup_dir}")

    merged = 0
    tot_b_added = 0
    tot_t_added = 0

    for sj in sorted(DOCS.glob("*/sources.json")):
        qid = sj.parent.name
        book_path  = pack_file(date_root, qid, "book")
        talks_path = pack_file(date_root, qid, "talks")

        if not book_path.exists() and not talks_path.exists():
            print(f"[warn] no harvested packs for {qid} under {date_root}/{qid}/")
            continue

        data = json.loads(sj.read_text(encoding="utf-8"))
        book  = data.setdefault("book", {})
        talks = data.setdefault("talks", {})
        book_chunks = book.setdefault("chunks", [])
        talk_chunks = talks.setdefault("chunks", [])

        added_b = 0
        added_t = 0

        if book_path.exists():
            raw = json.loads(book_path.read_text(encoding="utf-8"))
            src = _extract_chunks(raw)
            normed = []
            dropped_talkish = 0
            missing_cit = 0
            for c in src:
                nb = norm_book_chunk(c if isinstance(c, dict) else {})
                if not nb:
                    if _is_talkish(c if isinstance(c, dict) else {}):
                        dropped_talkish += 1
                    else:
                        missing_cit += 1
                    continue
                normed.append(nb)
            if dropped_talkish:
                print(f"[warn] {qid}: dropped {dropped_talkish} talk-like item(s) from BOOK harvest")
            if missing_cit:
                print(f"[warn] {qid}: dropped {missing_cit} empty/uncitable BOOK item(s)")
            added_b = dedup_append(book_chunks, normed, ("text","citation","chapter_code","section_code"))

        if talks_path.exists():
            raw = json.loads(talks_path.read_text(encoding="utf-8"))
            src = _extract_chunks(raw)
            normed = []
            for c in src:
                nt = norm_talk_chunk(c if isinstance(c, dict) else {})
                if nt:
                    normed.append(nt)
            added_t = dedup_append(talk_chunks, normed, ("text","ts_url"))

        if added_b or added_t:
            data.setdefault("meta", {})["date"] = datetime.today().date().isoformat()
            sj.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"[ok] {qid}: +{added_b} book, +{added_t} talks")
            merged += 1
            tot_b_added += added_b
            tot_t_added += added_t
        else:
            print(f"[=] {qid}: no additions")

    # Summary
    print(f"\nMerged {merged} module(s). Added {tot_b_added} book and {tot_t_added} talk chunks total.")

    # Validation
    tb, bt = validate_all()
    print("\nValidation:")
    print(f"  book-sections with talk-like fields: {tb}")
    print(f"  talks-sections with LSDMU-style citations: {bt}")
    if tb == 0 and bt == 0:
        print("  ✅ separation looks clean.")
    else:
        print("  ⚠️ please inspect warnings above.")

if __name__ == "__main__":
    main()