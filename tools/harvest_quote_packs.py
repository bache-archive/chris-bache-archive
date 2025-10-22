#!/usr/bin/env python3
"""
tools/harvest_quote_packs.py
Harvest book and talk excerpts for educational topics via local RAG APIs.

Creates per-topic folders:
  reports/quote_packs/<DATE>/<qid>/
    ├── book.search.json
    └── talks.search.json

Drop-in replacement with **separate endpoints** for books vs talks.

Env vars (all optional):
  RAG_BOOK_API   — default http://127.0.0.1:9000/search
  RAG_TALKS_API  — default http://127.0.0.1:8000/search
  API_KEY        — default "dev"
  TOP_K          — default 12
  MIN            — optional passthrough (float) to API, e.g. min_score
  MAX            — optional passthrough (int) cap (kept for compatibility)
  WITH_TIMECODES — "1" to request timecodes when API supports it

CLI:
  python3 tools/harvest_quote_packs.py --out-dir reports/quote_packs/2025-10-22/future-human
  python3 tools/harvest_quote_packs.py --out-dir ... --qid future-human --top-k 16
  python3 tools/harvest_quote_packs.py --out-dir ... --book-only
  python3 tools/harvest_quote_packs.py --out-dir ... --book-api http://localhost:9000/search --talks-api http://localhost:8000/search
"""

from __future__ import annotations
from pathlib import Path
import os, sys, json, argparse, datetime, requests

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports" / "quote_packs"

# -------- defaults from env --------
DEFAULT_BOOK_API  = os.getenv("RAG_BOOK_API",  "http://127.0.0.1:9000/search").strip()
DEFAULT_TALKS_API = os.getenv("RAG_TALKS_API", "http://127.0.0.1:8000/search").strip()
API_KEY = os.getenv("API_KEY", "dev").strip()

def _env_int(name: str, default: int | None = None) -> int | None:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    try:
        return int(v)
    except Exception:
        return default

def _env_float(name: str, default: float | None = None) -> float | None:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    try:
        return float(v)
    except Exception:
        return default

ENV_TOP_K = _env_int("TOP_K", 12)
ENV_MIN   = _env_float("MIN", None)      # pass-through if present
ENV_MAX   = _env_int("MAX", None)        # pass-through if present
ENV_WTC   = os.getenv("WITH_TIMECODES", "").strip() in ("1","true","yes","y")

# -------- HTTP helper --------
def query_rag(endpoint: str, query: str, top_k: int = 12, **extra) -> dict:
    """Send a search query to a RAG endpoint. Extra fields are passed through."""
    payload = {"query": query, "top_k": top_k}
    # Pass-through extras (filters, toggles, etc.)
    payload.update(extra)
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    r = requests.post(endpoint, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()

# -------- CLI / main --------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True, help="Output directory for this harvest (per-topic).")
    ap.add_argument("--qid", help="Optional topic id (e.g., 'future-human'); defaults to basename of out-dir.")
    ap.add_argument("--book-only", action="store_true", help="Only harvest book quotes (skip talks).")
    ap.add_argument("--top-k", type=int, default=ENV_TOP_K, help=f"Max results per query (default {ENV_TOP_K}).")
    ap.add_argument("--book-api", default=DEFAULT_BOOK_API, help=f"Book RAG endpoint (default {DEFAULT_BOOK_API}).")
    ap.add_argument("--talks-api", default=DEFAULT_TALKS_API, help=f"Talks RAG endpoint (default {DEFAULT_TALKS_API}).")
    args = ap.parse_args()

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    topic = (args.qid or out_dir.name).strip()
    human_topic = topic.replace("-", " ")
    today = datetime.date.today().isoformat()

    # Compose optional pass-through knobs
    passthrough = {}
    # Common optional knobs many backends accept; safe if ignored by server
    if ENV_MIN is not None:
        passthrough["min_score"] = ENV_MIN
    if ENV_MAX is not None:
        passthrough["max_chunks"] = ENV_MAX
    if ENV_WTC:
        passthrough["with_timecodes"] = True

    print(f"[info] Harvesting topic: {topic}")
    print(f"[info] Endpoints → book: {args.book_api} | talks: {args.talks_api}")
    print(f"[info] top_k={args.top_k}  min_score={passthrough.get('min_score')}  max_chunks={passthrough.get('max_chunks')}  with_timecodes={passthrough.get('with_timecodes', False)}")

    # --- 1) Book search (book-only API / corpus) ---
    book_q = f"What does LSD and the Mind of the Universe say about {human_topic}?"
    try:
        # Include a corpus hint for servers that support it; harmless otherwise
        book_res = query_rag(
            args.book_api,
            book_q,
            top_k=args.top_k,
            corpus="book",
            **passthrough
        )
        (out_dir / "book.search.json").write_text(json.dumps(book_res, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[ok] wrote book.search.json ({len(book_res.get('chunks', []))} chunks)")
    except Exception as e:
        (out_dir / "book.search.fail.txt").write_text(f"{type(e).__name__}: {e}\n", encoding="utf-8")
        print(f"[warn] book search failed: {e}")

    # --- 2) Talks search (if not skipped) ---
    if not args.book_only:
        talk_q = f"What does Chris Bache say about {human_topic}?"
        try:
            talk_res = query_rag(
                args.talks_api,
                talk_q,
                top_k=args.top_k,
                corpus="talks",
                **passthrough
            )
            (out_dir / "talks.search.json").write_text(json.dumps(talk_res, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"[ok] wrote talks.search.json ({len(talk_res.get('chunks', []))} chunks)")
        except Exception as e:
            (out_dir / "talks.search.fail.txt").write_text(f"{type(e).__name__}: {e}\n", encoding="utf-8")
            print(f"[warn] talk search failed: {e}")

if __name__ == "__main__":
    main()