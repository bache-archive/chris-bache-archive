#!/usr/bin/env python3
"""
tools/build_educational_docs_full.py

Full-mode builder (verbatim book excerpts + ALL transcript excerpts).

Guarantees:
- Book quotes render FIRST, talk quotes SECOND (never mixed).
- Book quotes always show a citation label; if missing, one is synthesized.
- Talk quotes prefer explicit start_hhmmss and otherwise derive [hh:mm:ss] from ts_url.
- Labels like "LSDMU ..." are normalized to "LSD and the Mind of the Universe ...".
- Appends a Fair Use notice to every page.

Usage:
  python3 tools/build_educational_docs_full.py            # build all topics
  python3 tools/build_educational_docs_full.py --qid astrology
  python3 tools/build_educational_docs_full.py --dry-run
"""

from __future__ import annotations
import os, sys, json, argparse, datetime, re, urllib.parse
from pathlib import Path
from typing import List, Dict, Any

# optional env loader
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

# optional LLM preface
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "educational"
TOOLS_ENV = Path(__file__).resolve().parent / ".env"
ROOT_ENV  = ROOT / ".env"

# ---------- env ----------

def load_env():
    if load_dotenv:
        if TOOLS_ENV.exists(): load_dotenv(TOOLS_ENV)
        if ROOT_ENV.exists():  load_dotenv(ROOT_ENV, override=True)
    return {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", "").strip(),
        "MODEL": (os.getenv("MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip(),
        "INCLUDE_PREFACE": os.getenv("INCLUDE_PREFACE", "true").lower() in ("1","true","yes","y"),
    }

def list_qids(one=None):
    if one:
        p = DOCS / one / "sources.json"
        if not p.exists():
            sys.exit(f"[error] missing {p}")
        return [one]
    qids = [p.parent.name for p in DOCS.glob("*/sources.json")]
    if not qids:
        sys.exit("[error] no docs/educational/*/sources.json found. Run harvest/merge first.")
    return sorted(qids)

# ---------- timecode helpers ----------

_time_hms_re = re.compile(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$", re.I)

def _seconds_to_hhmmss(total: int) -> str:
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def _parse_hms_token(token: str) -> int | None:
    m = _time_hms_re.search(token.strip())
    if not m: return None
    h = int(m.group(1) or 0)
    mi = int(m.group(2) or 0)
    s = int(m.group(3) or 0)
    if h == mi == s == 0: return None
    return h*3600 + mi*60 + s

def extract_time_from_url(url: str | None) -> str | None:
    """Return hh:mm:ss if url has t= or start= (seconds or h/m/s) or a #t= fragment."""
    if not url: return None
    try:
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)
        candidates = []
        if "t" in qs and qs["t"]:
            candidates.append(qs["t"][0])
        if "start" in qs and qs["start"]:
            candidates.append(qs["start"][0])
        if not candidates and parsed.fragment:
            frag = parsed.fragment
            if frag.startswith("t="):
                candidates.append(frag[2:])
        for tok in candidates:
            if tok.isdigit():
                return _seconds_to_hhmmss(int(tok))
            secs = _parse_hms_token(tok)
            if secs is not None:
                return _seconds_to_hhmmss(secs)
    except Exception:
        return None
    return None

def best_timecode(chunk: dict) -> str | None:
    """Prefer explicit start_hhmmss; else derive from ts_url."""
    hms = (chunk.get("start_hhmmss") or "").strip() or None
    if hms: return hms
    url = chunk.get("ts_url") or chunk.get("url")
    return extract_time_from_url(url)

# ---------- label normalization ----------

_LSDMU_RE = re.compile(r'^\s*LSDMU\b', re.I)

def normalize_citation_label(label: str | None) -> str:
    """Expand leading 'LSDMU' to the full book title."""
    if not label:
        return ""
    return _LSDMU_RE.sub("LSD and the Mind of the Universe", label).strip()

def synth_citation_from_ptr(citation: str | None, ch: str | None, sec: str | None) -> str:
    """Ensure we always have a readable book label."""
    label = (citation or "").strip()
    if not label:
        label = "LSD and the Mind of the Universe"
    label = normalize_citation_label(label)
    parts = []
    if ch: parts.append(str(ch).strip())
    if sec: parts.append(str(sec).strip())
    return f"{label} ({' · '.join(p for p in parts if p)})" if parts else label

# ---------- LLM preface (optional) ----------

SYS_PROMPT = (
    "You write a short, neutral preface (2–4 sentences) for an educational page on Christopher M. Bache. "
    "Do not include citations or timestamps. Be concise and non-promotional."
)

USER_TEMPLATE = """Topic/QID: {qid}

Book snippets (verbatim, may be partial):
{book_snips}

Transcript snippets (verbatim, may be partial):
{talk_snips}

Write a 2–4 sentence preface suitable for a scholarly reader. No quotes, no timestamps, no first person.
"""

def maybe_preface(client, model, qid, book_chunks, talk_chunks) -> str:
    if not client: return ""
    def lines(chs, n, each):
        out = []
        for c in chs[:n]:
            t = c.get("text","")
            t = re.sub(r"\s+", " ", t).strip()
            out.append("- " + t[:each])
        return "\n".join(out) if out else "(none)"
    user = USER_TEMPLATE.format(
        qid=qid,
        book_snips=lines(book_chunks, 6, 600),
        talk_snips=lines(talk_chunks, 6, 400),
    )
    try:
        resp = client.chat.completions.create(
            model=model,
            temperature=0.3,
            messages=[{"role":"system","content":SYS_PROMPT},
                      {"role":"user","content":user}],
        )
        return re.sub(r"\n{2,}", "\n", resp.choices[0].message.content.strip())
    except Exception:
        return ""

# ---------- rendering ----------

def esc(s: str) -> str:
    return (s or "").replace("\r\n","\n").replace("\r","\n")

def build_md(qid: str, meta_date: str, preface: str, book_chunks: list[dict], talk_chunks: list[dict]) -> str:
    title = qid.replace("-", " ").title()
    today = datetime.date.today().isoformat()

    fm = f"""---
title: "{title}"
id: "{qid}"
date: "{today}"
version: "v1"
source_policy: "Book-first. Public transcripts as color with timestamped links."
---"""

    preface_block = f"\n\n> {preface}\n" if preface else ""

    # BOOK — verbatim, all; ensure no talk-like contamination
    book_lines = ["## Primary citations (book — verbatim excerpts)"]
    def is_talkish(c: dict) -> bool:
        return bool((c.get("ts_url") or c.get("url") or "").strip() or (c.get("recorded_date") or "").strip())

    true_book_chunks = [c for c in (book_chunks or []) if not is_talkish(c)]
    if not true_book_chunks:
        book_lines.append("_(No book excerpts present in sources.json.)_")
    else:
        for c in true_book_chunks:
            raw_label = (c.get("citation") or c.get("archival_title") or "").strip()
            ch = (c.get("chapter_code") or "").strip() or None
            sec = (c.get("section_code") or "").strip() or None
            label = synth_citation_from_ptr(raw_label, ch, sec)
            book_lines.append(f"\n**{label}**\n")
            book_lines.append("> " + esc(c.get("text","")).replace("\n", "\n> ").rstrip())
    book_block = "\n".join(book_lines)

    # TALKS — verbatim, all; timecoded first then by score
    def sort_key(c):
        tc = 1 if best_timecode(c) else 0
        score = c.get("_score") or 0.0
        return (-tc, -(score or 0.0))
    talk_sorted = sorted((talk_chunks or []), key=sort_key)

    talk_lines = ["\n## Supporting transcript quotes (verbatim)"]
    if not talk_sorted:
        talk_lines.append("_(No transcript excerpts present in sources.json.)_")
    else:
        for c in talk_sorted:
            text = esc(c.get("text","")).strip()
            if not text:
                continue
            hms = best_timecode(c)
            ts = (c.get("ts_url") or c.get("url") or "").strip()
            ttitle = (c.get("archival_title") or "Untitled").strip()
            date = (c.get("recorded_date") or "").strip()
            if hms and ts:
                link = f"[{hms}]({ts})"
                cite_suffix = f" — *{ttitle}* ({date}) • {hms}"
            elif ts:
                link = f"[link]({ts})"
                cite_suffix = f" — *{ttitle}* ({date}) • no timecode"
            else:
                link = ""
                cite_suffix = f" — *{ttitle}* ({date}) • no link"
            header = f"{link} {cite_suffix}".strip()
            talk_lines.append(f"\n> {text}\n\n{header}")

    talk_block = "\n".join(talk_lines)

    provenance = f"""
## Provenance
Built from `sources.json` (harvested {meta_date}).
Cite as: _Christopher M. Bache — Public Talks (2014–2025), retrieved via Bache Talks RAG v1.2-rc1._
""".rstrip()

    fair_use = """
## Fair Use Notice
Excerpts from *LSD and the Mind of the Universe* are reproduced here under the fair use doctrine for **educational and scholarly purposes**.
They support study, research, and public understanding of Christopher M. Bache’s work on consciousness and spiritual evolution.
All quotations remain the intellectual property of their respective copyright holders.
""".rstrip()

    return "\n".join([fm, preface_block, book_block, talk_block, "", provenance, "", fair_use]) + "\n"

# ---------- validation ----------

def _has_talkish_keys(d: Dict[str, Any]) -> bool:
    return any((d.get(k) or "").strip() for k in ("ts_url","start_hhmmss","recorded_date","url","date","hhmmss","time_hhmmss"))

def _talk_has_anchor(d: Dict[str, Any]) -> bool:
    return any((d.get(k) or "").strip() for k in ("ts_url","recorded_date","start_hhmmss","hhmmss","time_hhmmss","url","date"))

def validate_sources(qid: str, data: Dict[str, Any]) -> tuple[bool, str]:
    """Ensure book/talk sections are not mingled and have minimal required fields."""
    book = (data.get("book") or {})
    talks = (data.get("talks") or {})
    bchs: List[Dict[str, Any]] = (book.get("chunks") or []) or []
    tchs: List[Dict[str, Any]] = (talks.get("chunks") or []) or []

    b_talkish = sum(1 for c in bchs if _has_talkish_keys(c))
    b_missing_cit = sum(1 for c in bchs if not (c.get("citation") or c.get("label") or "").strip())
    t_no_anchor = sum(1 for c in tchs if not _talk_has_anchor(c))
    t_bookish = sum(1 for c in tchs if (c.get("citation") or c.get("label") or "").strip().upper().startswith("LSDMU"))

    ok = (b_talkish == 0 and b_missing_cit == 0 and t_no_anchor == 0 and t_bookish == 0)
    note = (f"{qid}: book={len(bchs)} talks={len(tchs)} | "
            f"book:talkish={b_talkish} book:no_cit={b_missing_cit} | "
            f"talks:no_anchor={t_no_anchor} talks:bookish_cit={t_bookish}")
    return ok, note

def validate_render_counts(qid: str, md: str, data: Dict[str, Any]) -> tuple[bool, str]:
    """Rough check that rendered counts align with sources counts."""
    # slice sections
    book_start = md.find("## Primary citations (book")
    talk_start = md.find("## Supporting transcript quotes")
    if book_start == -1 or talk_start == -1:
        return False, f"{qid}: missing section headers"

    book_section = md[book_start:talk_start]
    # book entries are rendered as lines beginning with **label**
    book_rendered = len(re.findall(r"\n\*\*.+?\*\*\n", book_section))

    next_header = md.find("\n## ", talk_start + 4)
    talk_section = md[talk_start: (next_header if next_header != -1 else len(md))]
    # talk entries are rendered as blockquotes lines '> ' followed by a header on next line
    talk_rendered = len(re.findall(r"\n> [^\n]+", talk_section))

    src_book = len(((data.get("book") or {}).get("chunks") or []))
    src_talk = len(((data.get("talks") or {}).get("chunks") or []))

    # allow small mismatches (e.g., empty texts filtered)
    ok = (abs(book_rendered - src_book) <= 2) and (abs(talk_rendered - src_talk) <= 2)
    note = (f"{qid}: rendered book={book_rendered}/{src_book}, talks={talk_rendered}/{src_talk}")
    return ok, note

# ---------- main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qid", help="Only build this QID (folder under docs/educational/<qid>)")
    ap.add_argument("--dry-run", action="store_true", help="Print output instead of writing files")
    args = ap.parse_args()

    cfg = load_env()
    client = None
    if OpenAI and cfg["OPENAI_API_KEY"] and cfg["INCLUDE_PREFACE"]:
        client = OpenAI(api_key=cfg["OPENAI_API_KEY"])

    qids = list_qids(args.qid)
    wrote = 0
    all_ok = True
    notes: List[str] = []

    for qid in qids:
        src = DOCS / qid / "sources.json"
        data = json.loads(src.read_text(encoding="utf-8"))
        book_chunks  = (data.get("book",{}) or {}).get("chunks",[]) or []
        talk_chunks  = (data.get("talks",{}) or {}).get("chunks",[]) or []
        meta_date    = (data.get("meta",{}) or {}).get("date","")

        preface = maybe_preface(client, cfg["MODEL"], qid, book_chunks, talk_chunks) if client else ""
        md = build_md(qid, meta_date, preface, book_chunks, talk_chunks)

        if args.dry_run:
            print(f"\n=== {qid} ===\n")
            print(md[:2000] + ("\n...\n" if len(md)>2000 else ""))
        else:
            out = DOCS / qid / "index.md"
            out.write_text(md, encoding="utf-8")
            wrote += 1
            print(f"[ok] wrote {out}")

        # validations
        ok1, note1 = validate_sources(qid, data)
        ok2, note2 = validate_render_counts(qid, md, data)
        all_ok = all_ok and ok1 and ok2
        notes.append(f"[sources] {note1}")
        notes.append(f"[render ] {note2}")

    # summary
    if not args.dry_run:
        print(f"\nDone. Wrote {wrote} document(s).")

    print("\nValidation summary:")
    for n in notes:
        print(" - " + n)
    print(f"\nOverall: {'OK' if all_ok else 'FAILED'}")

    if not all_ok:
        sys.exit(2)

if __name__ == "__main__":
    main()