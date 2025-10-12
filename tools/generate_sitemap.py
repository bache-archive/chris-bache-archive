#!/usr/bin/env python3
# generate_sitemap.py
# Build a clean sitemap that only lists URLs GitHub Pages actually serves:
# - Root (/) and optionally /index.html (if present)
# - HTML versions of captions/transcripts (only if the .html file exists)
# - Plain-text diarist files (*.txt)
#
# Notes:
# - <loc> is emitted on a single line (no inner whitespace/newlines) to satisfy strict parsers.
# - Duplicate URLs are deduped and output in stable (sorted) order.

import re
import sys
from pathlib import Path
from urllib.parse import quote
from datetime import datetime

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://bache-archive.github.io/chris-bache-archive"
OUT  = sys.argv[2] if len(sys.argv) > 2 else "sitemap.xml"

root = Path(__file__).resolve().parents[1]

# Store entries as (rel_path, meta) tuples; `meta` may contain changefreq
entries: list[tuple[str, dict]] = []
_seen: set[str] = set()

def add(rel_path: str, changefreq: str | None = None) -> None:
    """Add a relative path once, with optional changefreq."""
    if rel_path in _seen:
        return
    _seen.add(rel_path)
    meta: dict[str, str] = {}
    if changefreq:
        meta["changefreq"] = changefreq
    entries.append((rel_path, meta))

def infer_lastmod(path_str: str) -> str | None:
    """Infer YYYY-MM-DD from the filename/path and return ISO date if valid."""
    m = re.search(r"(\d{4}-\d{2}-\d{2})", path_str)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d").date().isoformat()
    except Exception:
        return None

# 1) Root (/) and optionally /index.html (if present)
add("", "weekly")
if (root / "index.html").exists():
    add("index.html", "weekly")

# 2) Captions + Transcripts: include ONLY .html files that exist (skip _archive)
for subdir in ("sources/captions", "sources/transcripts"):
    base = root / subdir
    if not base.exists():
        continue
    for md in base.rglob("*.md"):
        # Skip anything under an _archive folder
        if "/_archive/" in md.as_posix():
            continue
        html_path = md.with_suffix(".html")
        if html_path.exists():
            rel_html = html_path.relative_to(root).as_posix()
            add(rel_html)
        # Do NOT add the .md itself to avoid 404s on Pages

# 3) Diarist .txt (served as plain text by Pages)
diarist = root / "sources/diarist"
if diarist.exists():
    for txt in diarist.rglob("*.txt"):
        add(txt.relative_to(root).as_posix())

# Sort entries by their final absolute URL for stable output
def abs_url(rel_path: str) -> str:
    # Ensure no stray whitespace ends up inside <loc>
    return (BASE.rstrip("/") + "/" + quote(rel_path, safe="/")).strip()

entries.sort(key=lambda item: abs_url(item[0]))

# 4) Build XML (single-line <loc>)
lines: list[str] = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
]
for rel_path, meta in entries:
    loc = abs_url(rel_path)
    lines.append("  <url>")
    lines.append(f"    <loc>{loc}</loc>")
    lm = infer_lastmod(rel_path)
    if lm:
        lines.append(f"    <lastmod>{lm}</lastmod>")
    if "changefreq" in meta:
        lines.append(f"    <changefreq>{meta['changefreq']}</changefreq>")
    lines.append("  </url>")
lines.append("</urlset>\n")

Path(OUT).write_text("\n".join(lines), encoding="utf-8")
print(f"Wrote {OUT} with {len(entries)} URLs.")