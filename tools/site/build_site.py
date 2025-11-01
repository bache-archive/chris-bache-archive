#!/usr/bin/env python3
"""
tools/site/build_site.py

Build *styled* static HTML wrappers for:
  • sources/transcripts/**/*.md
  • sources/captions/**/*.md

Notes:
- Outputs sit next to the source files as *.html (same directory).
- Adds a simple hero + card shell and hardens external links.
- No educational pages are built here (moved to a separate project).

Usage:
  python3 tools/site/build_site.py
  python3 tools/site/build_site.py --site-base /chris-bache-archive --stylesheet assets/style.css
"""

from __future__ import annotations
from pathlib import Path
import argparse, html, re, sys
import markdown

# repo root is two levels up from this file: .../tools/site/build_site.py -> parents[2]
ROOT = Path(__file__).resolve().parents[2]
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

def title_guess_from_path(p: Path) -> str:
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
    inner = "\n".join([hero, card_section("Document", body_html)])
    page_html = wrap_shell(f"{title} — Chris Bache Archive", style_href, inner)

    out_html = md_path.with_suffix(".html")
    out_html.write_text(page_html, encoding="utf-8")
    print(f"[ok] SRC {out_html.relative_to(ROOT)}")

def convert_tree_sources(src: Path, site_base: str, stylesheet: str, pill: str):
    if not src.exists(): 
        print(f"[skip] {src.relative_to(ROOT)} (missing)")
        return
    for md in sorted(src.rglob("*.md")):
        process_source_page(md, site_base, stylesheet, pill)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site-base", default="/chris-bache-archive",
                    help="Base path for GitHub Pages (used in stylesheet link/canonicals)")
    ap.add_argument("--stylesheet", default="assets/style.css",
                    help="Path to CSS within repo")
    args = ap.parse_args()

    # Build wrappers for transcripts and captions only
    convert_tree_sources(SRC_TRANS, args.site_base, args.stylesheet, pill="Transcript")
    convert_tree_sources(SRC_CAP,   args.site_base, args.stylesheet, pill="Captions")
    print("\nDone.")

if __name__ == "__main__":
    main()