#!/usr/bin/env python3
# tools/merge_harvest_into_sources.py
"""
Merge harvested quote packs into docs/educational/*/sources.json.

Compatible with BOTH layouts:
  reports/quote_packs/<DATE>/<qid>/talks.search.json
  reports/quote_packs/<qid>/talks.search.json

You can also point to a custom root:
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
    """If base has YYYY-MM-DD dirs, return newest; else return base."""
    if not base.exists():
        return None
    dated = [p for p in base.iterdir() if p.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name)]
    if dated:
        return sorted(dated, reverse=True)[0]
    return base

def find_pack_json(search_root: Path, qid: str) -> Path | None:
    """
    Look for talks.search.json under:
      <search_root>/<qid>/talks.search.json
    or any depth match: **/<qid>/talks.search.json
    Also tolerates alt names: search.json
    """
    candidates = [
        search_root / qid / "talks.search.json",
        search_root / qid / "search.json",
    ]
    for c in candidates:
        if c.exists():
            return c
    # last resort: glob
    for c in search_root.rglob("talks.search.json"):
        if c.parent.name == qid:
            return c
    for c in search_root.rglob("search.json"):
        if c.parent.name == qid:
            return c
    return None

def normalize_chunk(c: dict) -> dict:
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

def main():
    args = parse_args()
    reports_root = Path(args.reports_root)
    search_root = find_latest_root(reports_root)
    if not search_root:
        raise SystemExit(f"[error] missing reports root: {reports_root}")

    print(f"[info] using harvest root: {search_root}")

    merged = 0
    for sj in sorted(DOCS.glob("*/sources.json")):
        qid = sj.parent.name
        pack_json = find_pack_json(search_root, qid)
        if not pack_json or not pack_json.exists():
            print(f"[warn] no talks.search.json found for {qid} under {search_root}")
            continue

        data = json.loads(sj.read_text(encoding="utf-8"))
        talks = data.setdefault("talks", {})
        existing = talks.setdefault("chunks", [])

        seen = {(c.get("text","").strip(), c.get("ts_url") or c.get("url") or "") for c in existing}

        harvested = json.loads(pack_json.read_text(encoding="utf-8"))
        chunks = harvested.get("chunks") if isinstance(harvested, dict) else harvested
        if not chunks:
            print(f"[warn] empty chunks in {pack_json}")
            continue

        added = 0
        for c in chunks:
            nc = normalize_chunk(c)
            if not nc["text"]:
                continue
            key = (nc["text"], nc["ts_url"])
            if key in seen:
                continue
            existing.append(nc)
            seen.add(key)
            added += 1

        data.setdefault("meta", {})["date"] = datetime.today().date().isoformat()
        sj.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[ok] {qid}: +{added} chunks → {sj}")
        merged += 1

    print(f"\nMerged {merged} module(s).")

if __name__ == "__main__":
    main()