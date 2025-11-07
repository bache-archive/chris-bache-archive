#!/usr/bin/env python3
"""
tools/site/build_site.py

Build styled static HTML wrappers for:
  • sources/transcripts/**/*.md
  • sources/captions/**/*.md
…and add a "Watch on YouTube" button using index.json mapping.

Usage:
  python3 tools/site/build_site.py
  python3 tools/site/build_site.py --site-base https://bache-archive.github.io/chris-bache-archive --stylesheet assets/style.css
"""

from __future__ import annotations
from pathlib import Path
import argparse, html, re, json
from datetime import datetime
import markdown

# Paths
ROOT = Path(__file__).resolve().parents[2]
SRC_TRANS = ROOT / "sources" / "transcripts"
SRC_CAP   = ROOT / "sources" / "captions"
INDEX_JSON = ROOT / "index.json"

# Regex
FM_RE = re.compile(r'^\s*---\s*\n(.*?)\n---\s*\n(.*)\Z', re.S)
META_LINE = re.compile(r'^\s*([A-Za-z0-9_]+)\s*:\s*("?)(.+?)\2\s*$', re.M)
H1_RE = re.compile(r'^\s*#\s+(.+?)\s*$', re.M)

def parse_front_matter(md_txt: str) -> tuple[dict, str]:
    m = FM_RE.match(md_txt)
    if not m:
        return ({}, md_txt)
    raw_meta, body = m.group(1), m.group(2)
    meta = {}
    for mm in META_LINE.finditer(raw_meta):
        k = mm.group(1).strip().lower()
        v = mm.group(3).strip()
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

def hero_block(pill: str, h1: str, subtitle_html: str, buttons: list[tuple[str,str,str]] | None = None) -> str:
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
    m = H1_RE.search(txt)
    if m:
        return m.group(1).strip()
    return p.stem.replace("-", " ").replace("_"," ").title()

def load_index_map(index_path: Path) -> dict[str, dict]:
    """
    Returns a mapping:
      key:   'sources/transcripts/YYYY-MM-DD-foo.md' (POSIX, relative to repo root)
      value: {
        'youtube_url': str|None,
        'youtube_id': str|None,
        'published': 'YYYY-MM-DD'|None
      }
    """
    mapping: dict[str, dict] = {}
    if not index_path.exists():
        return mapping
    data = json.loads(index_path.read_text(encoding="utf-8"))
    for entry in data:
        tpath = entry.get("transcript") or ""
        if not tpath:
            continue
        # normalize as POSIX relative (repo-root)
        key = Path(tpath).as_posix()
        mapping[key] = {
            "youtube_url": entry.get("youtube_url") or (
                f"https://youtu.be/{entry['youtube_id']}" if entry.get("youtube_id") else None
            ),
            "youtube_id": entry.get("youtube_id"),
            "published": entry.get("published")
        }
    return mapping

def process_source_page(md_path: Path, site_base: str, stylesheet: str, pill: str, idx_map: dict[str, dict]):
    style_href = f"{site_base.rstrip('/')}/{stylesheet.lstrip('/')}" if site_base.startswith("http") else f"{site_base.rstrip('/')}/{stylesheet.lstrip('/')}"
    text = md_path.read_text(encoding="utf-8")
    meta, body_md = parse_front_matter(text)  # tolerate front matter
    body_html = ensure_target_blank(md_to_html(body_md or text))

    title = meta.get("title") or title_guess_from_path(md_path)
    subtitle = meta.get("subtitle") or "Readable, speaker-attributed text with links back to the original recording."

    # Index lookup for YouTube
    rel_key = md_path.relative_to(ROOT).as_posix()  # e.g., sources/transcripts/...
    info = idx_map.get(rel_key, {})
    yt_url = info.get("youtube_url")

    buttons = [("View Markdown", md_path.name, "outline")]
    if yt_url:
        buttons.insert(0, ("Watch on YouTube", yt_url, "solid"))

    hero = hero_block(
        pill=pill,
        h1=title,
        subtitle_html=html.escape(subtitle),
        buttons=buttons
    )
    inner = "\n".join([hero, card_section("Document", body_html)])

    # canonical if site_base is absolute and page path is resolvable
    out_html = md_path.with_suffix(".html")
    rel_out = out_html.relative_to(ROOT).as_posix()
    canonical = (site_base.rstrip("/") + "/" + rel_out) if site_base.startswith("http") else None

    page_html = wrap_shell(f"{title} — Chris Bache Archive", style_href, inner, canonical=canonical)
    out_html.write_text(page_html, encoding="utf-8")
    print(f"[ok] SRC {out_html.relative_to(ROOT)}")

def convert_tree_sources(src: Path, site_base: str, stylesheet: str, pill: str, idx_map: dict[str, dict]):
    if not src.exists():
        print(f"[skip] {src.relative_to(ROOT)} (missing)")
        return
    for md in sorted(src.rglob("*.md")):
        process_source_page(md, site_base, stylesheet, pill, idx_map)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site-base", default="https://bache-archive.github.io/chris-bache-archive",
                    help="Base path or absolute URL for stylesheet/canonicals")
    ap.add_argument("--stylesheet", default="assets/style.css",
                    help="Path to CSS within repo")
    args = ap.parse_args()

    idx_map = load_index_map(INDEX_JSON)

    convert_tree_sources(SRC_TRANS, args.site_base, args.stylesheet, pill="Transcript", idx_map=idx_map)
    convert_tree_sources(SRC_CAP,   args.site_base, args.stylesheet, pill="Captions",   idx_map=idx_map)
    print("\nDone.")

if __name__ == "__main__":
    main()