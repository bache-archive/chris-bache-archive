#!/usr/bin/env python3
"""
Quick preview builder for transcript pages.
- Uses existing assets/style.css and your shadcn-inspired shell.
- Builds a minimal index and N per-item pages (HTML-first).
- Safe: writes only under ./site/transcripts/

Usage:
  python tools/site/build_transcript_preview.py --limit 12
"""

from __future__ import annotations
from pathlib import Path
import argparse, json, re, html, datetime
import markdown

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets" / "style.css"
OUT_DIR = ROOT / "site" / "transcripts"

FM_RE = re.compile(r'^\s*---\s*\n(.*?)\n---\s*\n(.*)\Z', re.S)
META_LINE = re.compile(r'^\s*([A-Za-z0-9_]+)\s*:\s*"?(.+?)"?\s*$', re.M)

def parse_front_matter(md_txt: str):
    m = FM_RE.match(md_txt)
    if not m:
        return {}, md_txt
    raw_meta, body = m.group(1), m.group(2)
    meta = {}
    for mm in META_LINE.finditer(raw_meta):
        k, v = mm.group(1).strip().lower(), mm.group(2).strip()
        meta[k] = v.strip('"').strip("'")
    return meta, body

def md_to_html(md_txt: str) -> str:
    return markdown.markdown(md_txt, extensions=["tables", "fenced_code"])

def ensure_target_blank(html_txt: str) -> str:
    def repl(m):
        tag = m.group(0)
        if 'target=' not in tag:
            tag = tag.replace('<a ', '<a target="_blank" ', 1)
        if 'rel=' not in tag:
            tag = tag.replace('<a ', '<a rel="noopener noreferrer" ', 1)
        return tag
    return re.sub(r'<a\s+[^>]*href="https?://[^"]+"[^>]*>', repl, html_txt, flags=re.I)

def wrap_shell(page_title: str, body_inner: str, canonical: str | None = None) -> str:
    canonical_link = f'\n  <link rel="canonical" href="{canonical}" />' if canonical else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>{html.escape(page_title)}</title>{canonical_link}
  <meta name="description" content="Readable, styled pages from the Chris Bache Archive." />
  <link rel="stylesheet" href="/chris-bache-archive/assets/style.css" />
</head>
<body>
  <div class="container">
{body_inner}
    <div class="footer muted">
      Built by the Chris Bache Archive · <a href="/chris-bache-archive/">Home</a>
    </div>
  </div>
</body>
</html>"""

def hero_block(pill: str, h1: str, subtitle_html: str, buttons: list[tuple[str,str,str]] = None) -> str:
    btns = []
    for label, href, kind in (buttons or []):
        klass = "btn" if kind == "solid" else "btn-outline"
        btns.append(f'<a class="{klass}" href="{href}">{html.escape(label)}</a>')
    btnrow = f'<div class="btnrow">{"".join(btns)}</div>' if btns else ""
    return f"""
<header class="hero" aria-labelledby="page-title">
  <span class="pill">{html.escape(pill)}</span>
  <h1 id="page-title" class="title">{html.escape(h1)}</h1>
  <p class="subtitle">{subtitle_html}</p>
  {btnrow}
</header>""".strip()

def card_section(title: str, inner_html: str) -> str:
    safe = inner_html if inner_html.strip() else "<p class='muted'>(None)</p>"
    return f"""
<section class="section">
  <div class="card">
    <h2>{html.escape(title)}</h2>
    <div class="stack">
      {safe}
    </div>
  </div>
</section>""".strip()

def read_index() -> list[dict]:
    idx = json.loads((ROOT / "index.json").read_text(encoding="utf-8"))
    # accept either {"items":[...]} or plain list
    items = idx["items"] if isinstance(idx, dict) and "items" in idx else idx
    return items

def year_from_date(iso: str) -> str:
    try:
        return str(datetime.date.fromisoformat(iso).year)
    except Exception:
        return "unknown"

def render_transcript_page(item: dict) -> tuple[str, str]:
    """Return (out_rel_path, html_text)."""
    md_path = ROOT / item["transcript"]
    md_txt = md_path.read_text(encoding="utf-8", errors="ignore")
    fm, body_md = parse_front_matter(md_txt)
    body_html = ensure_target_blank(md_to_html(body_md or md_txt))

    title = item.get("archival_title") or fm.get("title") or md_path.stem.replace("-", " ").title()
    date = item.get("published") or fm.get("date") or ""
    channel = item.get("channel") or ""
    stype = item.get("source_type") or fm.get("type") or "talk"

    yt = item.get("youtube_url") or (f'https://youtu.be/{item["youtube_id"]}' if item.get("youtube_id") else "")
    blob = item.get("blob_url") or f'https://github.com/bache-archive/chris-bache-archive/blob/main/{item.get("transcript","")}'
    audio = (item.get("media") or {}).get("audio", "")
    video = (item.get("media") or {}).get("video", "")
    doi = item.get("zenodo_doi","")

    subtitle_bits = []
    if channel: subtitle_bits.append(html.escape(channel))
    if date:    subtitle_bits.append(html.escape(date))
    subtitle = " • ".join(subtitle_bits) if subtitle_bits else "Readable, speaker-attributed transcript."

    btns = [("View Markdown", blob, "outline")]
    if yt:   btns.append(("YouTube", yt, "outline"))
    if audio: btns.append(("Audio (MP3)", f"/chris-bache-archive/{audio}", "outline"))
    if video: btns.append(("Video (MP4)", f"/chris-bache-archive/{video}", "outline"))
    if doi:  btns.append(("Zenodo", f"https://doi.org/{doi}", "outline"))

    hero = hero_block("Transcript", title, subtitle, btns)
    doc = card_section("Transcript", f'<article class="md">{body_html}</article>')
    page = wrap_shell(f"{title} — Chris Bache Archive", "\n".join([hero, doc]))

    # output path
    slug = Path(item["transcript"]).stem
    year = year_from_date(date)
    out_rel = f"{year}/{slug}.html"
    return out_rel, page

def render_index_page(items: list[dict]) -> str:
    # simple cards list
    cards = []
    for it in items:
        date = it.get("published","")
        year = year_from_date(date)
        slug = Path(it["transcript"]).stem
        href = f"{year}/{slug}.html"
        title = it.get("archival_title") or slug.replace("-", " ").title()
        channel = it.get("channel","")
        stype = it.get("source_type","").title()
        pills = f'<span class="pill" style="background:var(--brand-600)">{html.escape(stype or "Talk")}</span>'
        subtitle = " • ".join(b for b in [channel, date] if b)
        cards.append(f"""
<div class="card">
  <h3 style="margin:0 0 6px 0"><a href="{href}">{html.escape(title)}</a></h3>
  <p class="muted" style="margin:0 0 8px 0">{html.escape(subtitle)}</p>
  {pills}
</div>""")
    body = f"""
<header class="hero" aria-labelledby="page-title">
  <span class="pill">Transcripts</span>
  <h1 id="page-title" class="title">All Transcripts (Preview)</h1>
  <p class="subtitle">HTML-first, Markdown-sourced transcript editions.</p>
</header>
<section class="section">
  <div class="stack">
    {''.join(cards) if cards else '<p class="muted">(none)</p>'}
  </div>
</section>"""
    return wrap_shell("Transcripts — Chris Bache Archive", body)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=8, help="How many items to render (for preview)")
    args = ap.parse_args()

    items = [it for it in read_index() if it.get("transcript","").endswith(".md")]
    # prefer newest first
    def sort_key(it):
        return it.get("published","")
    items.sort(key=sort_key, reverse=True)
    preview = items[:args.limit]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # per-item pages
    for it in preview:
        rel, html_txt = render_transcript_page(it)
        out_path = OUT_DIR / rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html_txt, encoding="utf-8")
        print(f"[ok] {out_path.relative_to(ROOT)}")

    # index page
    index_html = render_index_page(preview)
    (OUT_DIR / "index.html").write_text(index_html, encoding="utf-8")
    print(f"[ok] {(OUT_DIR / 'index.html').relative_to(ROOT)}")

if __name__ == "__main__":
    main()
