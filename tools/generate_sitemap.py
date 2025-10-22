#!/usr/bin/env python3
"""
generate_sitemap.py  — drop-in replacement

Usage:
  python3 tools/generate_sitemap.py BASE_URL [OUTFILE]

- Prefers build/site as the content root if it exists, otherwise uses repo root.
- Emits only URLs that GitHub Pages will actually serve (existing .html/.txt).
- Includes:
    / and /index.html (if present),
    docs/educational/**/index.html,
    sources/transcripts/**/*.html (skips _archive),
    sources/captions/**/*.html (skips _archive),
    sources/diarist/**/*.txt
- Single-line <loc>, stable sort, optional <lastmod> (YYYY-MM-DD inferred from path).
"""

import sys
import re
from pathlib import Path
from urllib.parse import quote
from datetime import datetime

# ---------------- CLI ----------------
BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "https://bache-archive.github.io/chris-bache-archive"
OUT  = sys.argv[2] if len(sys.argv) > 2 else "sitemap.xml"

# Repo root (tools/..)
REPO_ROOT = Path(__file__).resolve().parents[1]

# Prefer built site if present; else fall back to repo root
SITE_ROOT = (REPO_ROOT / "build" / "site")
if not SITE_ROOT.exists():
    SITE_ROOT = REPO_ROOT

# ------------- helpers --------------
_seen: set[str] = set()
entries: list[tuple[str, dict]] = []

def add(rel_path: str, changefreq: str | None = None) -> None:
    """Add a relative path once, with optional changefreq."""
    if rel_path in _seen:
        return
    _seen.add(rel_path)
    meta = {}
    if changefreq:
        meta["changefreq"] = changefreq
    entries.append((rel_path, meta))

def infer_lastmod(path_str: str) -> str | None:
    """Infer YYYY-MM-DD from filename/path; return ISO date or None."""
    m = re.search(r"(\d{4}-\d{2}-\d{2})", path_str)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d").date().isoformat()
    except Exception:
        return None

def abs_url(rel_path: str) -> str:
    # Keep path separators, escape others safely
    return (BASE + "/" + quote(rel_path, safe="/")).strip()

def rel_from_root(path: Path) -> str:
    # Relative to SITE_ROOT for hrefs
    return path.relative_to(SITE_ROOT).as_posix()

def exists_rel(rel_path: str) -> bool:
    return (SITE_ROOT / rel_path).exists()

# ---------- collect URLs ------------

# 1) Root and optional index.html
add("")  # "/"
if exists_rel("index.html"):
    add("index.html", "weekly")

# 2) docs/educational/**/index.html
edu_root = SITE_ROOT / "docs" / "educational"
if edu_root.exists():
    for idx in edu_root.rglob("index.html"):
        add(rel_from_root(idx), "monthly")

# 3) transcripts & captions (HTML only, skip _archive)
for subdir in ("sources/transcripts", "sources/captions"):
    base = SITE_ROOT / subdir
    if base.exists():
        for html in base.rglob("*.html"):
            if "/_archive/" in html.as_posix():
                continue
            add(rel_from_root(html))

# 4) diarist text
diarist = SITE_ROOT / "sources" / "diarist"
if diarist.exists():
    for txt in diarist.rglob("*.txt"):
        add(rel_from_root(txt))

# Sort entries by absolute URL for stable output
entries.sort(key=lambda item: abs_url(item[0]))

# ------------- write XML -------------
lines = [
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

out_path = (REPO_ROOT / OUT) if not Path(OUT).is_absolute() else Path(OUT)
out_path.write_text("\n".join(lines), encoding="utf-8")
print(f"Wrote {out_path} with {len(entries)} URLs.\nContent root: {SITE_ROOT}")