#!/usr/bin/env python3
"""
tools/generate_sitemaps.py

Creates a sitemap index (sitemap.xml) and section sitemaps:
- sitemap-educational.xml        (docs/educational/**/index.html)
- sitemap-captions.xml           (sources/captions/**/*.html)
- sitemap-transcripts.xml        (sources/transcripts/**/*.html, skip _archive)
- sitemap-diarist.xml            (sources/diarist/**/*.txt)

Rules:
- Absolute <loc> URLs (required by GSC)
- Single-line <loc>
- <lastmod> prefers file mtime (UTC, date only); falls back to YYYY-MM-DD found in path
- Stable sort
- Enforces only URLs that actually exist in the built site (or repo if no build)
- Designed for GitHub Pages under: https://bache-archive.github.io/chris-bache-archive

Usage:
  python3 tools/generate_sitemaps.py [BASE_URL] [OUTDIR]
  # BASE_URL default: https://bache-archive.github.io/chris-bache-archive
  # OUTDIR   default: repo root
"""

import sys, re, os, time
from pathlib import Path
from urllib.parse import quote
from datetime import datetime, timezone

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://bache-archive.github.io/chris-bache-archive").rstrip("/")
OUTDIR = Path(sys.argv[2]) if len(sys.argv) > 2 else None

REPO_ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = REPO_ROOT / "build" / "site"
if not SITE_ROOT.exists():
    SITE_ROOT = REPO_ROOT

if OUTDIR is None:
    OUTDIR = REPO_ROOT

def abs_url(rel_path: str) -> str:
    return BASE + "/" + quote(rel_path.lstrip("/"), safe="/")

def rel_from_root(path: Path) -> str:
    return path.relative_to(SITE_ROOT).as_posix()

def infer_lastmod_from_name(path_str: str) -> str | None:
    m = re.search(r"(\d{4}-\d{2}-\d{2})", path_str)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d").date().isoformat()
    except Exception:
        return None

def lastmod_for(path: Path) -> str | None:
    try:
        ts = path.stat().st_mtime
        dt = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
        return dt
    except Exception:
        return infer_lastmod_from_name(path.as_posix())

def write_urlset(file_path: Path, rel_paths: list[str], changefreq: str | None = None) -> None:
    rel_paths = sorted(set(rel_paths), key=lambda p: abs_url(p))
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    ]
    for rp in rel_paths:
        p = SITE_ROOT / rp
        lm = lastmod_for(p)
        lines.append("  <url>")
        lines.append(f"    <loc>{abs_url(rp)}</loc>")
        if lm:
            lines.append(f"    <lastmod>{lm}</lastmod>")
        if changefreq:
            lines.append(f"    <changefreq>{changefreq}</changefreq>")
        lines.append("  </url>")
    lines.append("</urlset>\n")
    file_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {file_path} with {len(rel_paths)} URLs.")

def write_sitemap_index(index_path: Path, children: list[tuple[str, Path]]) -> None:
    # children: [(title, absolute_path_to_child_xml), ...]
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    ]
    for _title, child in children:
        rel = child.relative_to(OUTDIR).as_posix()
        loc = abs_url(rel)
        # lastmod = now for the file; fine for index
        try:
            ts = child.stat().st_mtime
            lm = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
        except Exception:
            lm = None
        lines.append("  <sitemap>")
        lines.append(f"    <loc>{loc}</loc>")
        if lm:
            lines.append(f"    <lastmod>{lm}</lastmod>")
        lines.append("  </sitemap>")
    lines.append("</sitemapindex>\n")
    index_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {index_path} (index of {len(children)} sitemaps).")

def collect_educational() -> list[str]:
    out = []
    base = SITE_ROOT / "docs" / "educational"
    if base.exists():
        for idx in base.rglob("index.html"):
            out.append(rel_from_root(idx))
    # also include site root and /index.html if present (nice for discovery)
    out.append("")  # "/"
    if (SITE_ROOT / "index.html").exists():
        out.append("index.html")
    return out

def collect_html_under(sub: str, skip_archive: bool = False) -> list[str]:
    out = []
    base = SITE_ROOT / sub
    if not base.exists():
        return out
    for html in base.rglob("*.html"):
        posix = html.as_posix()
        if skip_archive and "/_archive/" in posix:
            continue
        out.append(rel_from_root(html))
    return out

def collect_txt_under(sub: str) -> list[str]:
    out = []
    base = SITE_ROOT / sub
    if not base.exists():
        return out
    for txt in base.rglob("*.txt"):
        out.append(rel_from_root(txt))
    return out

def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)

    sm_edu  = OUTDIR / "sitemap-educational.xml"
    sm_cap  = OUTDIR / "sitemap-captions.xml"
    sm_tran = OUTDIR / "sitemap-transcripts.xml"
    sm_dia  = OUTDIR / "sitemap-diarist.xml"
    sm_idx  = OUTDIR / "sitemap.xml"  # <-- index for GSC

    # Collect
    edu_paths  = collect_educational()                        # monthly cadence
    cap_paths  = collect_html_under("sources/captions")       # html only
    tran_paths = collect_html_under("sources/transcripts", skip_archive=True)
    dia_paths  = collect_txt_under("sources/diarist")         # txt

    # Write section sitemaps
    write_urlset(sm_edu,  edu_paths,  changefreq="monthly")
    write_urlset(sm_cap,  cap_paths,  changefreq=None)
    write_urlset(sm_tran, tran_paths, changefreq=None)
    write_urlset(sm_dia,  dia_paths,  changefreq=None)

    # Write index that points to all four
    write_sitemap_index(sm_idx, [
        ("Educational", sm_edu),
        ("Captions",    sm_cap),
        ("Transcripts", sm_tran),
        ("Diarist",     sm_dia),
    ])

if __name__ == "__main__":
    main()