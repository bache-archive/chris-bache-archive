#!/usr/bin/env python3
"""
tools/harvest_quote_packs.py

Harvest book and talk excerpts for educational topics via **separate** local RAG APIs.

Writes per-topic folders in the unified layout:
  reports/quote_packs/<DATE>/<QID>/
    ├── book.search.json
    └── talks.search.json

Env vars (optional):
  RAG_BOOK_API   — default http://127.0.0.1:9000/search
  RAG_TALKS_API  — default http://127.0.0.1:8000/search
  API_KEY        — default "dev"
  TOP_K          — default 12
  MIN            — optional pass-through (float) to API as min_score
  MAX            — optional pass-through (int) to API as max_chunks
  WITH_TIMECODES — "1/true/yes/y" to request timecodes when API supports it

CLI examples (per-topic):
  python3 tools/harvest_quote_packs.py --date $(date +%F) --qid future-human
  python3 tools/harvest_quote_packs.py --date 2025-10-22 --qid journey-structure --top-k 16
  python3 tools/harvest_quote_packs.py --date $(date +%F) --qid future-human --book-only
  python3 tools/harvest_quote_packs.py --qid future-human --out-dir reports/quote_packs/2025-10-22/future-human

NOTE:
- Prefer using --date and --qid; --out-dir is still accepted (must point to .../<DATE>/<QID>).
- Run this in a loop over all QIDs if you want to harvest the entire set.
"""

from __future__ import annotations
from pathlib import Path
import os, sys, json, argparse, datetime, requests, re

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
ENV_WTC   = os.getenv("WITH_TIMECODES", "").strip().lower() in ("1","true","yes","y")

# -------- helpers --------
def _norm(s):
    return (s or "").strip()

def query_rag(endpoint: str, query: str, top_k: int = 12, **extra) -> dict:
    """Send a search query to a RAG endpoint. Extra fields are passed through."""
    payload = {"query": query, "top_k": top_k}
    payload.update({k: v for k, v in extra.items() if v is not None})
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    r = requests.post(endpoint, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()

def _ensure_book_shape(res: dict) -> tuple[dict,int,int]:
    """
    Keep only book-appropriate chunks:
      - must have non-empty text
      - must have non-empty 'citation' (or 'label')
      - must NOT contain talk-ish fields (ts_url/start_hhmmss/recorded_date/url/date/hhmmss/time_hhmmss)
    Returns (filtered_res, bad_no_cite, bad_talkish)
    """
    chunks = res.get("chunks", []) or []
    good, bad_no_cite, bad_talkish = [], 0, 0
    for c in chunks:
        txt = _norm(c.get("text"))
        if not txt:
            continue
        cit = _norm(c.get("citation") or c.get("label"))
        talkish = any(_norm(c.get(k)) for k in ("ts_url","start_hhmmss","recorded_date","url","date","hhmmss","time_hhmmss"))
        if talkish:
            bad_talkish += 1
            continue
        if not cit:
            bad_no_cite += 1
            continue
        good.append(c)
    return ({"chunks": good}, bad_no_cite, bad_talkish)

def _ensure_talk_shape(res: dict) -> tuple[dict,int]:
    """
    Keep only talk-appropriate chunks:
      - must have non-empty text
      - must have at least ts_url OR recorded_date OR start_hhmmss (or hhmmss/time_hhmmss)
    Returns (filtered_res, dropped)
    """
    chunks = res.get("chunks", []) or []
    good, dropped = [], 0
    for c in chunks:
        txt = _norm(c.get("text"))
        if not txt:
            continue
        anchor = any(_norm(c.get(k)) for k in ("ts_url","recorded_date","start_hhmmss","hhmmss","time_hhmmss","url","date"))
        if not anchor:
            dropped += 1
            continue
        good.append(c)
    return ({"chunks": good}, dropped)

def _validate_files(out_dir: Path, book_only: bool=False) -> bool:
    """
    Validate the just-written files:
      - book.search.json: all chunks have citation; none have talk-ish keys
      - talks.search.json: all chunks have a talk anchor; none have book-like 'LSDMU' citations
    Prints a per-topic validation summary.
    Returns True if all checks pass (or talks skipped), else False.
    """
    ok = True
    bf = out_dir / "book.search.json"
    tf = out_dir / "talks.search.json"

    # BOOK
    if bf.exists():
        b = json.loads(bf.read_text(encoding="utf-8"))
        bchs = b.get("chunks", []) or []
        no_cit = sum(1 for c in bchs if not _norm(c.get("citation") or c.get("label")))
        talkish = sum(1 for c in bchs if any(_norm(c.get(k)) for k in ("ts_url","start_hhmmss","recorded_date","url","date","hhmmss","time_hhmmss")))
        if no_cit or talkish:
            ok = False
        print(f"[check] {bf}  chunks={len(bchs)}  no_citation={no_cit}  talk_like={talkish}")
    else:
        print(f"[warn] missing {bf}")
        ok = False

    # TALKS
    if not book_only:
        if tf.exists():
            t = json.loads(tf.read_text(encoding="utf-8"))
            tchs = t.get("chunks", []) or []
            no_anchor = sum(1 for c in tchs if not any(_norm(c.get(k)) for k in ("ts_url","recorded_date","start_hhmmss","hhmmss","time_hhmmss","url","date")))
            bookish = sum(1 for c in tchs if _norm(c.get("citation") or c.get("label")).startswith("LSDMU"))
            if no_anchor or bookish:
                ok = False
            print(f"[check] {tf}  chunks={len(tchs)}  no_anchor={no_anchor}  book_like_citation={bookish}")
        else:
            print(f"[warn] missing {tf}")
            ok = False

    return ok

# -------- CLI / main --------
def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=False)
    g.add_argument("--out-dir", help="(Optional) Explicit output dir: reports/quote_packs/<DATE>/<QID>")
    ap.add_argument("--date", help="Harvest date folder (YYYY-MM-DD). Default: today.")
    ap.add_argument("--qid", help="Topic id (e.g., 'future-human'). If --out-dir is not set, this is required.")
    ap.add_argument("--book-only", action="store_true", help="Only harvest book quotes (skip talks).")
    ap.add_argument("--top-k", type=int, default=ENV_TOP_K, help=f"Max results per query (default {ENV_TOP_K}).")
    ap.add_argument("--book-api", default=DEFAULT_BOOK_API, help=f"Book RAG endpoint (default {DEFAULT_BOOK_API}).")
    ap.add_argument("--talks-api", default=DEFAULT_TALKS_API, help=f"Talks RAG endpoint (default {DEFAULT_TALKS_API}).")
    args = ap.parse_args()

    # Resolve output directory to the standardized layout
    if args.out_dir:
        out_dir = Path(args.out_dir).resolve()
        # sanity: expect .../quote_packs/<DATE>/<QID>
        parts = out_dir.parts
        if "quote_packs" not in parts:
            print(f"[warn] --out-dir should be under reports/quote_packs/<DATE>/<QID>, got: {out_dir}")
        out_dir.mkdir(parents=True, exist_ok=True)
        qid = (args.qid or out_dir.name).strip()
        date_dir = out_dir.parent.name
    else:
        if not args.qid:
            sys.exit("[error] --qid is required when --out-dir is not provided")
        qid = args.qid.strip()
        date_dir = (args.date or datetime.date.today().isoformat()).strip()
        out_dir = (REPORTS / date_dir / qid).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

    human_topic = qid.replace("-", " ")

    # Compose optional pass-through knobs (safe if ignored by server)
    passthrough = {}
    if ENV_MIN is not None:
        passthrough["min_score"] = ENV_MIN
    if ENV_MAX is not None:
        passthrough["max_chunks"] = ENV_MAX
    if ENV_WTC:
        passthrough["with_timecodes"] = True

    print(f"[info] Harvesting topic: {qid}")
    print(f"[info] Layout: {REPORTS}/<DATE>/<QID> = {REPORTS}/{date_dir}/{qid}")
    print(f"[info] Endpoints → book: {args.book_api} | talks: {args.talks_api}")
    print(f"[info] top_k={args.top_k}  min_score={passthrough.get('min_score')}  max_chunks={passthrough.get('max_chunks')}  with_timecodes={passthrough.get('with_timecodes', False)}")

    # --- 1) Book search (book-only corpus/API) ---
    book_q = f"What does LSD and the Mind of the Universe say about {human_topic}?"
    book_count = 0
    try:
        book_res = query_rag(
            args.book_api,
            book_q,
            top_k=args.top_k,
            corpus="book",
            **passthrough
        )
        book_res, bad_no_cite, bad_talkish = _ensure_book_shape(book_res)
        (out_dir / "book.search.json").write_text(json.dumps(book_res, indent=2, ensure_ascii=False), encoding="utf-8")
        book_count = len(book_res.get("chunks", []))
        if bad_no_cite or bad_talkish:
            print(f"[warn] book.search.json: filtered {bad_no_cite} without citation, {bad_talkish} talk-like")
        print(f"[ok] wrote {out_dir/'book.search.json'} ({book_count} chunks)")
    except Exception as e:
        (out_dir / "book.search.fail.txt").write_text(f"{type(e).__name__}: {e}\n", encoding="utf-8")
        print(f"[warn] book search failed: {e}")

    # --- 2) Talks search (if not skipped) ---
    talk_count = 0
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
            talk_res, dropped = _ensure_talk_shape(talk_res)
            (out_dir / "talks.search.json").write_text(json.dumps(talk_res, indent=2, ensure_ascii=False), encoding="utf-8")
            talk_count = len(talk_res.get("chunks", []))
            if dropped:
                print(f"[warn] talks.search.json: filtered {dropped} without timestamps/links")
            print(f"[ok] wrote {out_dir/'talks.search.json'} ({talk_count} chunks)")
        except Exception as e:
            (out_dir / "talks.search.fail.txt").write_text(f"{type(e).__name__}: {e}\n", encoding="utf-8")
            print(f"[warn] talk search failed: {e}")

    # --- 3) Post-harvest validation & summary ---
    all_ok = _validate_files(out_dir, book_only=args.book_only)
    location_msg = f"{REPORTS}/{date_dir}/{qid}"
    print("\nSummary:")
    print(f"  QID: {qid}")
    print(f"  Date folder: {date_dir}")
    print(f"  Path: {location_msg}")
    print(f"  book.search.json chunks:  {book_count}")
    if not args.book_only:
        print(f"  talks.search.json chunks: {talk_count}")
    print(f"  Validation: {'OK' if all_ok else 'FAILED'}")

    if not all_ok:
        sys.exit(2)

if __name__ == "__main__":
    main()