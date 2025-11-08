#!/usr/bin/env python3
"""
tools/site/build_site.py

Build styled static HTML wrappers ONLY for:
  • sources/transcripts/**/*.md
…and explicitly SKIP:
  • sources/transcripts/_archive/**
  • sources/transcripts/extras/**

Each HTML page embeds:
  • JSON-LD (schema.org CreativeWork + Person) for LLM ingestion
  • Dublin Core / citation / Open Graph meta tags
  • rel="alternate" to raw Markdown
  • "Watch on YouTube" button using index.json mapping (if present)

Usage:
  python3 tools/site/build_site.py
  # defaults:
  #   --site-base https://bache-archive.github.io/chris-bache-archive
  #   --stylesheet assets/style.css
"""

from __future__ import annotations
from pathlib import Path
import argparse, html, re, json
from datetime import date, datetime

# Optional YAML support (preferred for nested front matter)
try:
    import yaml  # type: ignore
    _YAML = True
except Exception:
    _YAML = False

import markdown

# Paths
ROOT       = Path(__file__).resolve().parents[2]
SRC_TRANS  = ROOT / "sources" / "transcripts"
INDEX_JSON = ROOT / "index.json"

# Regex
FM_RE   = re.compile(r'^\s*---\s*\n(.*?)\n---\s*\n(.*)\Z', re.S)
KV_LINE = re.compile(r'^\s*([A-Za-z0-9_]+)\s*:\s*("?)(.+?)\2\s*$', re.M)
H1_RE   = re.compile(r'^\s*#\s+(.+?)\s*$', re.M)

# Constants
WIKIDATA_PERSON = "Q112496741"
OPENALEX_PERSON = "A5045900737"
DEFAULT_DESC    = "Readable, styled pages from the Chris Bache Archive."

# ---------------- helpers ----------------

def _iso_or_str(x):
    if isinstance(x, (date, datetime)):
        return x.isoformat()
    return x

def _deep_jsonable(obj):
    # Recursively convert date/datetime to strings for JSON dumps
    if isinstance(obj, dict):
        return {k: _deep_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_jsonable(v) for v in obj]
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    return obj

# ------------- front matter parsing -------------

def parse_front_matter(md_txt: str) -> tuple[dict, str]:
    """
    Return a tuple (meta_dict, body_md). Prefer real YAML if available.
    """
    m = FM_RE.match(md_txt)
    if not m:
        return ({}, md_txt)
    raw_meta, body = m.group(1), m.group(2)
    if _YAML:
        try:
            meta = yaml.safe_load(raw_meta) or {}
            if not isinstance(meta, dict):
                meta = {}
            return (meta, body)
        except Exception:
            pass
    # Fallback: tolerant key:value parser (top-level only)
    meta: dict[str, str] = {}
    for mm in KV_LINE.finditer(raw_meta):
        k = mm.group(1).strip()
        v = mm.group(3).strip().strip('"').strip("'")
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

def wrap_shell(page_title: str, style_href: str, body_inner: str, canonical: str | None = None, meta_tags: str = "", ld_json: str = "") -> str:
    canonical_link = f'\n  <link rel="canonical" href="{canonical}" />' if canonical else ""
    ld_block = f'\n  <script type="application/ld+json">\n{ld_json}\n  </script>' if ld_json else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>{html.escape(page_title)}</title>{canonical_link}
  <meta name="robots" content="index,follow" />
  {meta_tags}
  <link rel="stylesheet" href="{style_href}">{ld_block}
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

def meta_kv_list(meta: dict) -> str:
    """
    Small human-readable metadata card.
    """
    title    = meta.get("title", "")
    date_    = _iso_or_str(meta.get("date", ""))
    typ      = meta.get("type", "")
    channel  = meta.get("channel", "")
    license_ = meta.get("license", "")
    identifiers = meta.get("identifiers") if isinstance(meta.get("identifiers"), dict) else {}
    wikidata = identifiers.get("wikidata_person") if identifiers else None
    openalex = identifiers.get("openalex_person") if identifiers else None

    lines = []
    def row(k, v):
        if v:
            lines.append(f"<div><strong>{html.escape(k)}:</strong> {html.escape(str(v))}</div>")
    row("Title", title)
    row("Date", date_)
    row("Type", typ)
    row("Channel", channel)
    row("License", license_)
    row("Wikidata (person)", wikidata)
    row("OpenAlex (person)", openalex)
    return "\n".join(lines)

def title_guess_from_path(p: Path) -> str:
    txt = p.read_text(encoding="utf-8", errors="ignore")
    m = H1_RE.search(txt)
    if m:
        return m.group(1).strip()
    return p.stem.replace("-", " ").replace("_"," ").title()

def load_index_map(index_path: Path) -> dict[str, dict]:
    """
    Returns mapping keyed by transcript path (POSIX, repo-relative):
      value includes youtube_url/id, published, raw_url, blob_url, channel, source_type, archival_title.
    Supports index.json as either array or {"items":[...]}.
    """
    mapping: dict[str, dict] = {}
    if not index_path.exists():
        return mapping
    data = json.loads(index_path.read_text(encoding="utf-8"))
    items = data.get("items") if isinstance(data, dict) else data
    for entry in (items or []):
        tpath = entry.get("transcript") or ""
        if not tpath:
            continue
        key = Path(tpath).as_posix()
        mapping[key] = {
            "youtube_url": entry.get("youtube_url") or (f"https://youtu.be/{entry['youtube_id']}" if entry.get("youtube_id") else None),
            "youtube_id": entry.get("youtube_id"),
            "published": entry.get("published"),
            "raw_url": entry.get("raw_url"),
            "blob_url": entry.get("blob_url"),
            "channel": entry.get("channel"),
            "source_type": entry.get("source_type"),
            "archival_title": entry.get("archival_title"),
        }
    return mapping

def build_json_ld(meta: dict, idx: dict, canonical_url: str | None, md_raw_url: str | None) -> str:
    """
    schema.org CreativeWork for the transcript + Person for Bache.
    Coerces any date/datetime to ISO strings to avoid JSON serialization errors.
    """
    title = meta.get("title") or idx.get("archival_title") or ""
    date_published = _iso_or_str(meta.get("date") or idx.get("published") or "")
    in_language = meta.get("language") or "en"
    typ = meta.get("type") or idx.get("source_type") or "other"
    identifiers = meta.get("identifiers") if isinstance(meta.get("identifiers"), dict) else {}
    wikidata = identifiers.get("wikidata_person") if identifiers else WIKIDATA_PERSON
    openalex = identifiers.get("openalex_person") if identifiers else OPENALEX_PERSON

    person = {
        "@type": "Person",
        "name": "Christopher M. Bache",
        "sameAs": [
            f"https://www.wikidata.org/wiki/{wikidata}",
            f"https://openalex.org/{openalex}",
        ]
    }

    schema_type = "CreativeWork"
    if typ in ("interview", "panel", "qanda"):
        schema_type = "CreativeWork"

    data = {
        "@context": "https://schema.org",
        "@type": schema_type,
        "name": title,
        "inLanguage": in_language,
        "datePublished": date_published or None,
        "isAccessibleForFree": True,
        "license": "https://creativecommons.org/publicdomain/zero/1.0/",
        "author": person,
        "creator": person,
        "about": "Public talk or interview featuring Christopher M. Bache.",
        "publisher": {
            "@type": "Organization",
            "name": "Chris Bache Archive"
        },
        "isPartOf": {
            "@type": "CreativeWork",
            "name": "Chris Bache Archive — Public Talks & Interviews"
        },
        "identifier": [
            {"@type": "PropertyValue", "propertyID": "Wikidata", "value": wikidata},
            {"@type": "PropertyValue", "propertyID": "OpenAlex", "value": openalex}
        ],
    }

    if canonical_url:
        data["url"] = canonical_url
    if md_raw_url:
        data["mainEntityOfPage"] = md_raw_url

    yt = idx.get("youtube_url")
    if yt:
        data["sameAs"] = [yt]

    data = {k: v for k, v in data.items() if v is not None}
    data = _deep_jsonable(data)
    return json.dumps(data, ensure_ascii=False, indent=2)

def build_meta_tags(meta: dict, idx: dict, canonical_url: str | None, md_raw_url: str | None, page_title: str, description: str) -> str:
    date_published = _iso_or_str(meta.get("date") or idx.get("published") or "")
    typ = meta.get("type") or idx.get("source_type") or "other"
    yt = idx.get("youtube_url")

    tags = []
    def add(name, content):  # generic name meta
        if content:
            tags.append(f'<meta name="{html.escape(name)}" content="{html.escape(str(content))}" />')
    def prop(p, content):  # og:*
        if content:
            tags.append(f'<meta property="{html.escape(p)}" content="{html.escape(str(content))}" />')

    add("dc.title", page_title)
    add("dc.creator", "Christopher M. Bache")
    add("dc.language", meta.get("language") or "en")
    add("dc.type", typ)
    add("dc.publisher", "Chris Bache Archive")
    add("dc.date", date_published)

    add("citation_title", page_title)
    add("citation_author", "Bache, Christopher M.")
    add("citation_publication_date", date_published)

    add("description", description)
    if md_raw_url:
        tags.append(f'<link rel="alternate" type="text/markdown" href="{html.escape(md_raw_url)}" />')
    if canonical_url:
        tags.append(f'<link rel="canonical" href="{html.escape(canonical_url)}" />')

    prop("og:title", page_title)
    prop("og:type", "article")
    prop("og:description", description)
    if canonical_url:
        prop("og:url", canonical_url)
    if yt:
        add("related_video", yt)

    return "\n  ".join(tags)

def process_source_page(md_path: Path, site_base: str, stylesheet: str, pill: str, idx_map: dict[str, dict]):
    style_href = f"{site_base.rstrip('/')}/{stylesheet.lstrip('/')}"
    text = md_path.read_text(encoding="utf-8")
    meta, body_md = parse_front_matter(text)

    # Render body
    body_html = ensure_target_blank(md_to_html(body_md or text))

    # Title/subtitle
    meta_title = meta.get("title") if isinstance(meta, dict) else None
    title = meta_title or title_guess_from_path(md_path)
    subtitle = "Readable, speaker-attributed text with links back to the original recording."

    # Index lookup
    rel_key = md_path.relative_to(ROOT).as_posix()  # e.g., sources/transcripts/...
    info = idx_map.get(rel_key, {})
    yt_url  = info.get("youtube_url")
    raw_url = info.get("raw_url")
    blob_url = info.get("blob_url")

    # Buttons
    buttons = []
    if yt_url:
        buttons.append(("Watch on YouTube", yt_url, "solid"))
    md_link = raw_url or blob_url or md_path.name
    buttons.append(("View Markdown", md_link, "outline"))

    # Hero + sections
    hero = hero_block(
        pill=pill,
        h1=title,
        subtitle_html=html.escape(subtitle),
        buttons=buttons
    )
    meta_card_html = meta_kv_list(meta if isinstance(meta, dict) else {})
    inner = "\n".join([
        hero,
        card_section("Metadata", meta_card_html),
        card_section("Document", body_html)
    ])

    # Canonical URL
    out_html = md_path.with_suffix(".html")
    rel_out = out_html.relative_to(ROOT).as_posix()
    canonical = (site_base.rstrip("/") + "/" + rel_out) if site_base.startswith("http") else None

    # SEO / LLM meta + JSON-LD
    page_title = f"{title} — Chris Bache Archive"
    description = DEFAULT_DESC
    the_meta = meta if isinstance(meta, dict) else {}
    meta_tags = build_meta_tags(the_meta, info, canonical, raw_url, page_title, description)
    ld_json   = build_json_ld(the_meta, info, canonical, raw_url)

    page_html = wrap_shell(page_title, style_href, inner, canonical=canonical, meta_tags=meta_tags, ld_json=ld_json)
    out_html.write_text(page_html, encoding="utf-8")
    print(f"[ok] SRC {out_html.relative_to(ROOT)}")

def should_skip(md: Path) -> bool:
    """
    Skip any markdown under _archive/ or extras/ within sources/transcripts.
    """
    # Make a posix, repo-relative path string for easy substring checks
    rel = md.relative_to(ROOT).as_posix()
    return (
        "/sources/transcripts/_archive/" in ("/" + rel) or
        "/sources/transcripts/extras/"   in ("/" + rel)
    )

def convert_tree_sources(src: Path, site_base: str, stylesheet: str, pill: str, idx_map: dict[str, dict]):
    if not src.exists():
        print(f"[skip] {src.relative_to(ROOT)} (missing)")
        return
    for md in sorted(src.rglob("*.md")):
        if should_skip(md):
            continue
        process_source_page(md, site_base, stylesheet, pill, idx_map)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site-base", default="https://bache-archive.github.io/chris-bache-archive",
                    help="Base path or absolute URL for stylesheet/canonicals")
    ap.add_argument("--stylesheet", default="assets/style.css",
                    help="Path to CSS within repo")
    args = ap.parse_args()

    idx_map = load_index_map(INDEX_JSON)
    # Build ONLY transcripts (skip captions and filtered subfolders)
    convert_tree_sources(SRC_TRANS, args.site_base, args.stylesheet, pill="Transcript", idx_map=idx_map)
    print("\nDone.")

if __name__ == "__main__":
    main()