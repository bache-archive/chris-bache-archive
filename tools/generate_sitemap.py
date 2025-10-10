#!/usr/bin/env python3
import re, sys
from pathlib import Path
from urllib.parse import quote
from datetime import datetime

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://bache-archive.github.io/chris-bache-archive"
OUT  = sys.argv[2] if len(sys.argv) > 2 else "sitemap.xml"

root = Path(__file__).resolve().parents[1]
entries = []

def add(rel_path, changefreq=None):
    meta = {}
    if changefreq:
        meta["changefreq"] = changefreq
    entries.append((rel_path, meta))

def infer_lastmod(path_str):
    m = re.search(r"(\d{4}-\d{2}-\d{2})", path_str)
    if not m: return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d").date().isoformat()
    except Exception:
        return None

# root + index.html
add("", "weekly")
add("index.html", "weekly")

# captions + transcripts as raw .md (exclude _archive)
for subdir in ("sources/captions", "sources/transcripts"):
    base = (root / subdir)
    if not base.exists(): continue
    for p in base.rglob("*.md"):
        if "/_archive/" in p.as_posix(): continue
        rel = p.relative_to(root).as_posix()  # keep .md
        add(rel)

# diarist .txt
diarist = root / "sources/diarist"
if diarist.exists():
    for p in diarist.rglob("*.txt"):
        add(p.relative_to(root).as_posix())

# Build XML
lines = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
for rel_path, meta in entries:
    loc = BASE.rstrip("/") + "/" + quote(rel_path, safe="/")
    lines.append("  <url>")
    lines.append(f"    <loc>{loc}</loc>")
    lm = infer_lastmod(rel_path)
    if lm: lines.append(f"    <lastmod>{lm}</lastmod>")
    if "changefreq" in meta: lines.append(f"    <changefreq>{meta['changefreq']}</changefreq>")
    lines.append("  </url>")
lines.append("</urlset>")

Path(OUT).write_text("\n".join(lines), encoding="utf-8")
print(f"Wrote {OUT} with {len(entries)} URLs.")
