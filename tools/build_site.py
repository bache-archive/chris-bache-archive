#!/usr/bin/env python3
"""
tools/build_site.py

Build *styled* static HTML for:
  • docs/educational/<qid>/index.md  (hero + cards: book first, talks second)
  • sources/transcripts/**/*.md       (styled wrapper)
  • sources/captions/**/*.md          (styled wrapper)

Usage:
  python3 tools/build_site.py
  python3 tools/build_site.py --qid future-human
  python3 tools/build_site.py --site-base /chris-bache-archive --stylesheet assets/style.css
  python3 tools/build_site.py --skip-sources   # only rebuild educational pages
"""

from __future__ import annotations
from pathlib import Path
import argparse, html, re, sys
import markdown

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "educational"
SRC_TRANS = ROOT / "sources" / "transcripts"
SRC_CAP   = ROOT / "sources" / "captions"

FM_RE = re.compile(r'^\s*---\s*\n(.*?)\n---\s*\n(.*)\Z', re.S)
META_LINE = re.compile(r'^\s*([A-Za-z0-9_]+)\s*:\s*"?(.+?)"?\s*$', re.M)

def parse_front_matter(md_txt: str) -> tuple[dict, str]:
    m = FM_RE.match(md_txt)
    if not m:
        return ({}, md_txt)
    raw_meta, body = m.group(1), m.group(2)
    meta = {}
    for mm in META_LINE.finditer(raw_meta):
        k, v = mm.group(1).strip().lower(), mm.group(2).strip()
        meta[k] = v.strip('"').strip("'")
    return (meta, body)

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

# -------- Robust section extraction (HTML first, Markdown fallback) --------

def _normalize_heading_txt(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s

def extract_section(body_html: str, heading_text: str, *, original_md: str | None = None) -> str:
    """
    1) Primary: slice HTML between <h2>target</h2> and the next <h2>.
    2) Fallback: slice Markdown between '## target' and next '## ' if HTML match fails.
    """
    target_norm = _normalize_heading_txt(heading_text)

    # --- HTML path ---
    inner = body_html
    mbody = re.search(r'<body[^>]*>(.*)</body>', body_html, re.S | re.I)
    if mbody:
        inner = mbody.group(1)

    h2s = list(re.finditer(r'<h2[^>]*>(.*?)</h2>', inner, re.S | re.I))
    target_idx = None
    for i, h in enumerate(h2s):
        txt = re.sub(r'<.*?>', '', h.group(1))
        if _normalize_heading_txt(txt) == target_norm:
            target_idx = i
            break

    if target_idx is not None:
        start = h2s[target_idx].end()
        end = h2s[target_idx + 1].start() if (target_idx + 1) < len(h2s) else len(inner)
        return inner[start:end].strip()

    # --- Markdown fallback ---
    if original_md:
        # be generous about spaces and punctuation in the heading
        esc = re.escape(heading_text)
        md_re = re.compile(rf'(?im)^\#\#\s*{esc}\s*\n(.*?)(?=^\#\#\s|\Z)', re.S)
        m = md_re.search(original_md)
        if m:
            segment_md = m.group(1).strip()
            try:
                seg_html = markdown.markdown(segment_md, extensions=["tables", "fenced_code"])
                return seg_html.strip()
            except Exception:
                return segment_md
    return ""

def wrap_shell(page_title: str, style_href: str, body_inner: str, canonical: str | None = None) -> str:
    canonical_link = f'\n  <link rel="canonical" href="{canonical}" />' if canonical else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>{html.escape(page_title)}</title>{canonical_link}
  <meta name="description" content="Readable, styled pages from the Chris Bache Archive." />
  <link rel="stylesheet" href="{style_href}">
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

def hero_block(pill: str, h1: str, subtitle_html: str, buttons: list[tuple[str,str,str]] = None, right_note: str = "") -> str:
    btns = []
    for label, href, kind in (buttons or []):
        klass = "btn" if kind == "solid" else "btn-outline"
        btns.append(f'<a class="{klass}" href="{href}">{html.escape(label)}</a>')
    btnrow = f'<div class="btnrow">{"".join(btns)}{" " if btns else ""}{html.escape(right_note)}</div>' if (btns or right_note) else ""
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

# ---------- Educational pages (styled book-first/talks-second) ----------

def edu_subtitle(meta: dict, qid: str) -> str:
    pretty = (meta.get("title") or qid.replace("-", " ").title()).strip()
    return f'What does <strong>Chris Bache</strong> say about <strong>{html.escape(pretty)}</strong>?'

def process_educational(md_path: Path, site_base: str, stylesheet: str):
    qid = md_path.parent.name
    style_href = f"{site_base.rstrip('/')}/{stylesheet.lstrip('/')}"
    canonical = f"{site_base.rstrip('/')}/docs/educational/{qid}/"

    raw = md_path.read_text(encoding="utf-8")
    meta, body_md = parse_front_matter(raw)
    body_html = md_to_html(body_md)

    # Extract the sections our builder created (now with MD fallback)
    book_html  = extract_section(body_html, "Primary citations (book — verbatim excerpts)", original_md=body_md)
    talks_html = extract_section(body_html, "Supporting transcript quotes (verbatim)", original_md=body_md)
    prov_html  = extract_section(body_html, "Provenance", original_md=body_md)
    fair_html  = extract_section(body_html, "Fair Use Notice", original_md=body_md)

    # Harden external links
    book_html  = ensure_target_blank(book_html)
    talks_html = ensure_target_blank(talks_html)
    prov_html  = ensure_target_blank(prov_html)
    fair_html  = ensure_target_blank(fair_html)

    page_title = f'{meta.get("title") or qid.replace("-", " ").title()} — Educational Topic'
    hero = hero_block(
        pill="Educational Topic",
        h1=(meta.get("title") or qid.replace("-", " ").title()),
        subtitle_html=edu_subtitle(meta, qid),
        buttons=[
            ("View sources.json", "./sources.json", "solid"),
            ("View Markdown", "./index.md", "outline"),
        ],
        right_note=(f'ID: {qid} · {meta.get("date","")}'.strip(" ·"))
    )

    html_inner = "\n".join([
        hero,
        card_section("Primary citations (book — verbatim excerpts)", book_html),
        card_section("Supporting transcript quotes (verbatim)", talks_html),
        f"""
<section class="section">
  <details class="scholar">
    <summary>Scholarly notes &amp; provenance</summary>
    <div class="scholar-body">
      {prov_html if prov_html.strip() else "<p class='muted'>No provenance found.</p>"}
      <div class="hr"></div>
      {fair_html if fair_html.strip() else "<p class='muted'>No fair-use block found.</p>"}
    </div>
  </details>
</section>""".strip()
    ])

    out_html = md_path.with_suffix(".html")
    out_html.write_text(wrap_shell(page_title, style_href, html_inner, canonical), encoding="utf-8")
    print(f"[ok] EDU {qid}: wrote {out_html}")

# ---------- Generic “source page” wrapper (transcripts/captions) ----------

def title_guess_from_path(p: Path) -> str:
    # Try H1 in MD, else filename prettified
    txt = p.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r'^\s*#\s+(.+?)\s*$', txt, re.M)
    if m:
        return m.group(1).strip()
    return p.stem.replace("-", " ").replace("_"," ").title()

def process_source_page(md_path: Path, site_base: str, stylesheet: str, pill: str):
    style_href = f"{site_base.rstrip('/')}/{stylesheet.lstrip('/')}"
    text = md_path.read_text(encoding="utf-8")
    meta, body_md = parse_front_matter(text)  # tolerate front matter if present
    body_html = ensure_target_blank(md_to_html(body_md or text))

    title = meta.get("title") or title_guess_from_path(md_path)
    subtitle = meta.get("subtitle") or "Readable, speaker-attributed text with links back to the original recording."

    hero = hero_block(
        pill=pill,
        h1=title,
        subtitle_html=html.escape(subtitle),
        buttons=[("View Markdown", md_path.name, "outline")]
    )
    inner = "\n".join([
        hero,
        card_section("Document", body_html)
    ])
    page_html = wrap_shell(f"{title} — Chris Bache Archive", style_href, inner)
    out_html = md_path.with_suffix(".html")
    out_html.write_text(page_html, encoding="utf-8")
    print(f"[ok] SRC {out_html}")

def convert_tree_sources(src: Path, site_base: str, stylesheet: str, pill: str):
    if not src.exists(): return
    for md in sorted(src.rglob("*.md")):
        process_source_page(md, site_base, stylesheet, pill)

# ---------- main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site-base", default="/chris-bache-archive",
                    help="Base path for GitHub Pages (used in stylesheet link and canonicals)")
    ap.add_argument("--stylesheet", default="assets/style.css",
                    help="Path to CSS within repo")
    ap.add_argument("--qid", help="Build only this educational topic (docs/educational/<qid>)")
    ap.add_argument("--skip-sources", action="store_true",
                    help="Skip converting sources/transcripts and sources/captions")
    args = ap.parse_args()

    # 1) Educational pages (styled, book-first)
    if args.qid:
        md = DOCS / args.qid / "index.md"
        if not md.exists():
            sys.exit(f"[error] missing {md}")
        process_educational(md, args.site_base, args.stylesheet)
    else:
        for md in sorted(DOCS.glob("*/index.md")):
            process_educational(md, args.site_base, args.stylesheet)

    # 2) Sources (styled wrappers)
    if not args.skip_sources:
        convert_tree_sources(SRC_TRANS, args.site_base, args.stylesheet, pill="Transcript")
        convert_tree_sources(SRC_CAP,   args.site_base, args.stylesheet, pill="Captions")

    print("\nDone.")

if __name__ == "__main__":
    main()