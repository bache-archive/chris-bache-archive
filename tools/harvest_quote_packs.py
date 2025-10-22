#!/usr/bin/env python3
"""
tools/harvest_quote_packs.py
Harvest book and talk excerpts for educational topics via local RAG API.

Creates per-topic folders:
  reports/quote_packs/<DATE>/<qid>/
    ├── book.search.json
    └── talks.search.json
"""

from __future__ import annotations
from pathlib import Path
import os, sys, json, argparse, datetime, requests

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports" / "quote_packs"

API = os.getenv("RAG_API", "http://127.0.0.1:8000/search")
API_KEY = os.getenv("API_KEY", "dev")

def query_rag(query: str, top_k: int = 12) -> dict:
    """Send a search query to local RAG API."""
    r = requests.post(
        API,
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={"query": query, "top_k": top_k},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", help="Output directory for this harvest", required=True)
    ap.add_argument("--qid", help="Optional single topic id (e.g., 'future-human')")
    ap.add_argument("--book-only", action="store_true", help="Skip talk search")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.date.today().isoformat()
    topic = args.qid or out_dir.name
    print(f"[info] Harvesting topic: {topic}")

    # 1. Book search
    book_q = f"What does LSD and the Mind of the Universe say about {topic.replace('-', ' ')}?"
    try:
        book_res = query_rag(book_q)
        (out_dir / "book.search.json").write_text(json.dumps(book_res, indent=2), encoding="utf-8")
        print(f"[ok] wrote book.search.json ({len(book_res.get('chunks', []))} chunks)")
    except Exception as e:
        print(f"[warn] book search failed: {e}")

    # 2. Talks search (if not skipped)
    if not args.book_only:
        talk_q = f"What does Chris Bache say about {topic.replace('-', ' ')}?"
        try:
            talk_res = query_rag(talk_q)
            (out_dir / "talks.search.json").write_text(json.dumps(talk_res, indent=2), encoding="utf-8")
            print(f"[ok] wrote talks.search.json ({len(talk_res.get('chunks', []))} chunks)")
        except Exception as e:
            print(f"[warn] talk search failed: {e}")

if __name__ == "__main__":
    main()