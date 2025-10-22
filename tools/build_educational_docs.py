#!/usr/bin/env python3
"""
tools/build_educational_docs.py

Builds final educational documents from harvested RAG outputs.

Inputs:
  - docs/educational/<qid>/sources.json  (created by tools/harvest_quote_packs.py)
  - tools/.env  (reads OPENAI_API_KEY; optional MODEL, MAX_QUOTES, INCLUDE_PREFACE)

Outputs:
  - docs/educational/<qid>/index.md  (book-first, timecoded transcript quotes, optional preface)

Usage:
  python3 tools/build_educational_docs.py                 # build all QIDs found in docs/educational/*
  python3 tools/build_educational_docs.py --qid chod      # build one
  python3 tools/build_educational_docs.py --dry-run       # print summary, don’t write files

Env (.env in tools/):
  OPENAI_API_KEY=sk-...
  MODEL=gpt-4o-mini             # optional; defaults to gpt-4o-mini
  MAX_QUOTES=3                  # optional; defaults to 3 (1–3 recommended)
  INCLUDE_PREFACE=true          # optional; true/false (default true)
"""

from __future__ import annotations
import os, sys, json, argparse, glob, datetime, textwrap, re
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

# OpenAI SDK v1.x
try:
    from openai import OpenAI
except Exception as e:
    OpenAI = None

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "educational"
ENV_PATH = Path(__file__).resolve().parent / ".env"

def read_env():
    # Load tools/.env if present
    if load_dotenv and ENV_PATH.exists():
        load_dotenv(ENV_PATH)
    cfg = {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", "").strip(),
        "MODEL": os.getenv("MODEL", "gpt-4o-mini").strip(),
        "MAX_QUOTES": int(os.getenv("MAX_QUOTES", "3")),
        "INCLUDE_PREFACE": os.getenv("INCLUDE_PREFACE", "true").lower() in ("1","true","yes","y"),
    }
    return cfg

def find_qids(single_qid: str | None) -> list[str]:
    if single_qid:
        p = DOCS / single_qid / "sources.json"
        if not p.exists():
            sys.exit(f"[error] sources.json missing for qid={single_qid}: {p}")
        return [single_qid]
    qids = []
    for path in sorted((DOCS).glob("*/sources.json")):
        qids.append(path.parent.name)
    if not qids:
        sys.exit("[error] No docs/educational/*/sources.json found. Did you run tools/harvest_quote_packs.py?")
    return qids

def safe_excerpt(s: str, max_len=500):
    s = re.sub(r"\s+", " ", s or "").strip()
    return (s[:max_len] + "…") if len(s) > max_len else s

def pick_timecoded_quotes(chunks: list[dict], max_quotes: int) -> list[dict]:
    # Prefer items with start_hhmmss; stable sort by:
    # 1) has_start desc, 2) higher _score if present, else keep order
    def key(c):
        has_start = 1 if c.get("start_hhmmss") else 0
        score = c.get("_score", 0.0) or 0.0
        # negative because we want higher score first
        return (-has_start, -score)
    sorted_chunks = sorted(chunks, key=key)
    picks = [c for c in sorted_chunks if c.get("start_hhmmss")][:max_quotes]
    return picks

LLM_SYS_PROMPT = """You are helping produce a short educational page about Christopher M. Bache.
Rules:
- The BOOK (LSD and the Mind of the Universe) is PRIMARY: summarize its relevant content in your own words.
- DO NOT include any verbatim book quotations. Summarize only.
- You MAY include 1–2 sentence paraphrases referencing chapter/section/paragraph if the signals are present.
- Keep the tone neutral, scholarly, and concise.
- Length targets:
  * Preface: 2–4 sentences (optional section).
  * Book summary: 3–6 sentences, crisp, book-first.
- Do NOT invent references; only infer what’s reasonably supported by the provided snippets/metadata.
"""

LLM_USER_TEMPLATE = """Topic/QID: {qid}

Book snippets (may be partial and noisy; summarize without quoting):
{book_snippets}

Talk snippets (context only; transcript quotes will be added separately):
{talk_snippets}

Tasks:
1) Write a 2–4 sentence PREFACE that orients a general reader to what Bache says on this topic. Avoid jargon, cite nothing, and do not include timestamps.
2) Write a BOOK-FIRST SUMMARY (3–6 sentences) that captures the main points relevant to this topic, without any verbatim quoting from the book.
3) Suggest a BOOK CITATION POINTER in the style: Ch. <##> “<Chapter Title>”, §<##> ¶<##> (only if you can infer it from the snippets; otherwise return a best-guess short pointer like “Ch. 10 (Diamond Luminosity), mid-chapter”).
Return JSON with keys: preface, summary, book_citation_pointer.
"""

def make_llm(client: OpenAI | None, model: str, api_key: str):
    if client is None or not api_key:
        return None
    return client

def llm_summarize(client: OpenAI, model: str, qid: str, book_chunks: list[dict], talk_chunks: list[dict]) -> dict:
    # Build short snippet context (truncate aggressively to keep token use sane)
    def fmt(chs, max_items=6, max_each=400):
        out = []
        for c in chs[:max_items]:
            out.append("- " + safe_excerpt(c.get("text",""), max_each))
        return "\n".join(out) if out else "(none)"
    user = LLM_USER_TEMPLATE.format(
        qid=qid,
        book_snippets=fmt(book_chunks, max_items=6, max_each=500),
        talk_snippets=fmt(talk_chunks, max_items=4, max_each=300),
    )
    resp = client.chat.completions.create(
        model=model,
        temperature=0.3,
        messages=[
            {"role":"system","content":LLM_SYS_PROMPT},
            {"role":"user","content":user},
        ],
        response_format={"type":"json_object"},
    )
    try:
        data = json.loads(resp.choices[0].message.content)
    except Exception:
        data = {"preface":"","summary":"","book_citation_pointer":""}
    return {
        "preface": (data.get("preface") or "").strip(),
        "summary": (data.get("summary") or "").strip(),
        "book_citation_pointer": (data.get("book_citation_pointer") or "").strip(),
    }

def build_document(qid: str, meta_date: str, picks: list[dict], llm_bits: dict, include_preface: bool) -> str:
    # Titleize qid (simple)
    title = qid.replace("-", " ").strip().title()
    today = datetime.date.today().isoformat()
    preface = llm_bits.get("preface","").strip()
    summary = llm_bits.get("summary","").strip()
    book_ptr = llm_bits.get("book_citation_pointer","").strip() or "<add chapter/§/¶>"

    # Build quotes block
    if not picks:
        quotes_md = "_(No timecoded quotes found in this harvest; consider adjusting queries.)_"
    else:
        lines = []
        for c in picks:
            text = safe_excerpt(c.get("text",""), 1200)
            start = c.get("start_hhmmss","")
            ts = c.get("ts_url") or c.get("url","")
            title_line = c.get("archival_title","Untitled")
            d = c.get("recorded_date","")
            lines.append(f'- “{text}” **[{start}]({ts})** — *{title_line}* ({d})')
        quotes_md = "\n".join(lines)

    front_matter = f"""---
title: "{title}"
id: "{qid}"
date: "{today}"
version: "v1"
source_policy: "Book-first. Public transcripts as color with timestamped links."
---
""".rstrip()

    preface_block = f"\n> {preface}\n" if (include_preface and preface) else ""
    book_block = f"""## Primary citation (book)
**LSD and the Mind of the Universe** — {book_ptr}.
_Summary:_ {summary}
""".rstrip()

    talk_block = f"""## Supporting transcript quotes
{quotes_md}
""".rstrip()

    provenance = f"""## Provenance
Built from `sources.json` (harvested {meta_date}).
Cite as: _Christopher M. Bache — Public Talks (2014–2025), retrieved via Bache Talks RAG v1.2-rc1._
""".rstrip()

    return "\n\n".join([front_matter, preface_block, book_block, "", talk_block, "", provenance]) + "\n"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qid", help="Build only this QID (folder under docs/educational/<qid>)")
    ap.add_argument("--dry-run", action="store_true", help="Print summary; do not write files")
    args = ap.parse_args()

    cfg = read_env()
    if not cfg["OPENAI_API_KEY"]:
        print("[warn] OPENAI_API_KEY missing; will build without LLM preface/summary.")
    client = None
    if OpenAI and cfg["OPENAI_API_KEY"]:
        client = OpenAI(api_key=cfg["OPENAI_API_KEY"])

    qids = find_qids(args.qid)
    wrote = 0

    for qid in qids:
        src_path = DOCS / qid / "sources.json"
        data = json.load(open(src_path, "r", encoding="utf-8"))

        talks_chunks = data.get("talks",{}).get("chunks",[]) or []
        book_chunks  = data.get("book",{}).get("chunks",[]) or []
        meta_date    = data.get("meta",{}).get("date","")

        picks = pick_timecoded_quotes(talks_chunks, cfg["MAX_QUOTES"])
        if not picks and talks_chunks:
            # fallback: take 1 non-timecoded if absolutely nothing timecoded
            picks = talks_chunks[:1]

        llm_bits = {"preface":"","summary":"","book_citation_pointer":""}
        if client:
            try:
                llm_bits = llm_summarize(client, cfg["MODEL"], qid, book_chunks, talks_chunks)
            except Exception as e:
                print(f"[warn] LLM call failed for {qid}: {e}")

        doc_md = build_document(qid, meta_date, picks, llm_bits, include_preface=cfg["INCLUDE_PREFACE"])

        if args.dry_run:
            print(f"\n=== {qid} ===")
            print(doc_md[:800] + ("...\n" if len(doc_md)>800 else ""))
        else:
            out_path = DOCS / qid / "index.md"
            out_path.write_text(doc_md, encoding="utf-8")
            wrote += 1
            print(f"[ok] wrote {out_path}")

    if not args.dry_run:
        print(f"\nDone. Wrote {wrote} document(s).")

if __name__ == "__main__":
    main()
