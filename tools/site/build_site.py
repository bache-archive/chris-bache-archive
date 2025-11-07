#!/usr/bin/env python3
"""
tools/site/build_site.py

Build *styled* static HTML wrappers for:
  • sources/transcripts/**/*.md  -> alongside .html
  • sources/captions/**/*.md     -> alongside .html
And generate:
  • catalog/transcripts.html      -> chronological index of transcript HTML pages

Usage:
  python3 tools/site/build_site.py
  python3 tools/site/build_site.py --site-base /chris-bache-archive --stylesheet assets/style.css
  python3 tools/site/build_site.py --site-base https://bache-archive.github.io/chris-bache-archive
"""

from __future__ import annotations
from pathlib import Path
import argparse, html, re, sys, urllib.parse
from datetime import datetime
import markdown

# repo root is two levels up from this file: .../tools/site/build_site.py -> parents[2]
ROOT = Path(__file__).resolve().parents[2]
SRC_TRANS = ROOT / "sources" / "transcripts"
SRC_CAP   = ROOT / "sources" / "captions"
CATALOG_DIR = ROOT / "catalog"
CATALOG_PATH = CATALOG_DIR / "transcripts.html"

FM_RE = re.compile(r'^\s*---\s*\n(.*?)\n---\s*\n(.*)\Z', re.S)
# Accept simple k: v lines in front matter. (Nested YAML fields are ignored here.)
META_LINE = re.compile(r'^\s*([A-Za-z0-9_]+)\s*:\s*("?)(.+?)\2\s*$', re.M)

DATE_IN_NAME = re.compile(r'(\d{4}-\d{2}-\d{2})')

def parse_front_matter(md_txt: str) -> tuple[dict, str]:
    m = FM_RE.match(md_txt)
    if not m:
        return ({}, md_txt)
    raw_meta, body = m.group(1), m.group(2)
    meta = {}
    for mm in META_LINE.finditer(raw_meta):
        k = mm.group(1).strip().lower()
        v = mm.group(3).strip()
        meta[k] = v
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

def is_absolute_url(s: str) -> bool:
    try:
        u = urllib.parse.urlparse(s)
        return bool(u.scheme and u.netloc)
    except Exception:
        return False

def wrap_shell(page_title: str, style_href: str, body_inner: str, canonical: str | None = None) -> str:
    canonical_link = f'\n  <link rel="canonical" href="{canonical}"/>' if canonical else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>{html.escape(page_title)}</title>{canonical_link}
  <meta name="description" content="Readable, styled pages from the Chris Bache Archive."/>
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
    try:
        txt = p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        txt = ""
    m = re.search(r'^\s*#\s+(.+?)\s*$', txt, re.M)
    if m:
        return m.group(1).strip()
    return p.stem.replace("-", " ").replace("_"," ").title()

def date_from_meta_or_name(meta: dict, p: Path) -> str | None:
    # Prefer front matter "date: YYYY-MM-DD"
    d = (meta.get("date") or "").strip()
    if d:
        # Normalize to YYYY-MM-DD if possible
        try:
            return datetime.strptime(d[:10], "%Y-%m-%d").date().isoformat()
        except Exception:
            pass
    # Fallback: capture from filename
    m = DATE_IN_NAME.search(p.stem)
    if m:
        return m.group(1)
    return None

def compute_canonical(site_base: str, out_html_rel_to_root: str) -> str | None:
    # If site_base is absolute, join; otherwise omit canonical.
    if not is_absolute_url(site_base):
        return None
    # Ensure single slash join
    return site_base.rstrip("/") + "/" + out_html_rel_to_root.lstrip("/")

def process_source_page(md_path: Path, site_base: str, stylesheet: str, pill: str) -> dict:
    """
    Returns a dict with listing metadata for catalogs when pill == 'Transcript':
      { "title":..., "date":..., "channel":..., "html_rel":..., "md_rel":... }
    """
    style_href = f"{site_base.rstrip('/')}/{stylesheet.lstrip('/')}" if not is_absolute_url(stylesheet) else stylesheet
    text = md_path.read_text(encoding="utf-8")
    meta, body_md = parse_front_matter(text)
    body_html = ensure_target_blank(md_to_html(body_md or text))

    title = meta.get("title") or title_guess_from_path(md_path)
    subtitle = meta.get("subtitle") or "Readable, speaker-attributed text with links back to the original recording."

    # 🎥 Optional YouTube link
    yt = meta.get("youtube_id")
    buttons = [("View Markdown", md_path.name, "outline")]
    if yt:
        yt_url = f"https://www.youtube.com/watch?v={yt}"
        buttons.insert(0, ("Watch on YouTube", yt_url, "solid"))

    hero = hero_block(
        pill=pill,
        h1=title,
        subtitle_html=html.escape(subtitle),
        buttons=buttons
    )
    inner = "\n".join([hero, card_section("Document", body_html)])

    # Canonical (only when site_base is an absolute URL)
    out_html = md_path.with_suffix(".html")
    out_rel = out_html.relative_to(ROOT).as_posix()
    canonical = compute_canonical(site_base, out_rel)

    page_html = wrap_shell(f"{title} — Chris Bache Archive", style_href, inner, canonical=canonical)
    out_html.write_text(page_html, encoding="utf-8")
    print(f"[ok] SRC {out_rel}")

    listing = {
        "title": title,
        "date": date_from_meta_or_name(meta, md_path),
        "channel": meta.get("channel") or meta.get("chan") or "",
        "html_rel": out_rel,
        "md_rel": md_path.relative_to(ROOT).as_posix()
    }
    return listing

def convert_tree_sources(src: Path, site_base: str, stylesheet: str, pill: str) -> list[dict]:
    listings: list[dict] = []
    if not src.exists():
        print(f"[skip] {src.relative_to(ROOT)} (missing)")
        return listings
    for md in sorted(src.rglob("*.md")):
        listing = process_source_page(md, site_base, stylesheet, pill)
        if pill.lower().startswith("transcript"):
            listings.append(listing)
    return listings

def build_catalog(transcript_listings: list[dict], site_base: str, stylesheet: str):
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)

    # Sort by date ascending; undated go last
    def sort_key(x):
        return (x["date"] is None, x["date"] or "9999-12-31", x["title"].lower())
    transcript_listings = sorted(transcript_listings, key=sort_key)

    # Build list HTML items
    items = []
    for it in transcript_listings:
        date_label = it["date"] or "—"
        channel = it["channel"]
        channel_html = f"<span class='muted'> · {html.escape(channel)}</span>" if channel else ""
        items.append(
            f"<li><a href='/{it['html_rel']}'>{html.escape(date_label)} — {html.escape(it['title'])}</a>{channel_html}</li>"
        )

    body = f"""
<header class="hero" aria-labelledby="cat-title">
  <span class="pill">Catalog</span>
  <h1 id="cat-title" class="title">Transcript Catalog (Chronological)</h1>
  <p class="subtitle">All cleaned transcripts from earliest to latest, each with a styled HTML view and its source Markdown.</p>
  <div class="btnrow">
    <a class="btn-outline" href="https://github.com/bache-archive/chris-bache-archive">View Repository</a>
  </div>
</header>

<section class="section card">
  <h2>Transcripts</h2>
  <ol class="stack">
    {"".join(items) if items else "<p class='muted'>(No transcripts found)</p>"}
  </ol>
</section>
""".strip()

    style_href = f"{site_base.rstrip('/')}/{stylesheet.lstrip('/')}" if not is_absolute_url(stylesheet) else stylesheet
    out_rel = CATALOG_PATH.relative_to(ROOT).as_posix()
    canonical = compute_canonical(site_base, out_rel)
    page = wrap_shell("Transcript Catalog — Chris Bache Archive", style_href, body, canonical=canonical)
    CATALOG_PATH.write_text(page, encoding="utf-8")
    print(f"[ok] CATALOG {out_rel}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site-base", default="/chris-bache-archive",
                    help="Base path or absolute URL for the site (used for stylesheet link/canonical).")
    ap.add_argument("--stylesheet", default="assets/style.css",
                    help="Path or absolute URL to CSS.")
    args = ap.parse_args()

    # Build wrappers
    transcript_listings = convert_tree_sources(SRC_TRANS, args.site_base, args.stylesheet, pill="Transcript")
    convert_tree_sources(SRC_CAP,   args.site_base, args.stylesheet, pill="Captions")

    # Build catalog
    build_catalog(transcript_listings, args.site_base, args.stylesheet)
    print("\nDone.")

if __name__ == "__main__":
    main()