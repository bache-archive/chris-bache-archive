#!/usr/bin/env python3
"""
tools/site/build_site.py  —  Drop-in replacement

Build styled static HTML wrappers ONLY for:
  • sources/transcripts/*.md    (skips subfolders like _archive/ and extras/)
Adds:
  • Canonical URL + OG/Twitter meta (+ og:site_name)
  • JSON-LD @graph: Person (sameAs→Wikidata/OpenAlex), VideoObject (url+embedUrl+thumbnailUrl), CreativeWork (transcript) with isBasedOn + mainEntityOfPage
  • Highwire/Google Scholar-style citation_* meta
  • <link rel="alternate" type="text/markdown"> pointing at the source .md
  • Speaker label normalizer (**Name:** …)
  • Editorial + identifier footer

Usage:
  python tools/site/build_site.py
  python tools/site/build_site.py --site-base https://bache-archive.github.io/chris-bache-archive --stylesheet assets/style.css
"""

from __future__ import annotations
from pathlib import Path
import argparse, html, re, json
import markdown

# -------- Paths (repo-root relative) --------
ROOT        = Path(__file__).resolve().parents[2]
SRC_TRANS   = ROOT / "sources" / "transcripts"
INDEX_JSON  = ROOT / "index.json"

# -------- Defaults --------
DEFAULT_SITE_BASE  = "https://bache-archive.github.io/chris-bache-archive"
DEFAULT_STYLESHEET = "assets/style.css"

# -------- Regex helpers --------
FM_RE     = re.compile(r'^\s*---\s*\n(.*?)\n---\s*\n(.*)\Z', re.S)
META_LINE = re.compile(r'^\s*([A-Za-z0-9_]+)\s*:\s*("?)(.+?)\2\s*$', re.M)
H1_RE     = re.compile(r'^\s*#\s+(.+?)\s*$', re.M)

# Fix common malformed speaker labels like "**Name: ** text" → "**Name:** text"
SPEAKER_LINE_RE = re.compile(
    r'^(?P<lead>\s*)\*\*\s*(?P<name>[^*:]{1,120}?)\s*:\s*\*\*(?P<tail>\s*)(?P<rest>.*)$',
    re.M
)
SPEAKER_WEIRD_RE = re.compile(
    r'^(?P<lead>\s*)\*\*\s*(?P<name>[^*:]{1,120}?)\s*\*\*\s*:\s*(?P<rest>.*)$',
    re.M
)
# Audience edge-cases:
AUDIENCE_RE_1 = re.compile(r'^(?P<lead>\s*)Audience\s*:\s*\*\*\s*(?P<rest>.*)$', re.M)
AUDIENCE_RE_2 = re.compile(r'^(?P<lead>\s*)\*?Audience\*?\s*:\s*(?P<rest>.*)$', re.M)

def normalize_speaker_labels(md: str) -> str:
    def _fix(m):
        lead = m.group('lead') or ''
        name = (m.group('name') or '').strip()
        rest = m.group('rest')
        return f"{lead}**{name}:** {rest}"
    md = SPEAKER_LINE_RE.sub(_fix, md)
    md = SPEAKER_WEIRD_RE.sub(lambda m: f"{m.group('lead')}**{m.group('name').strip()}:** {m.group('rest')}", md)
    md = AUDIENCE_RE_1.sub(lambda m: f"{m.group('lead')}**Audience:** {m.group('rest')}", md)
    md = AUDIENCE_RE_2.sub(lambda m: f"{m.group('lead')}**Audience:** {m.group('rest')}", md)
    return md

def parse_front_matter(md_txt: str) -> tuple[dict, str]:
    """
    Tolerant front-matter parser (simple key: value lines).
    Returns (meta_dict, body_md).
    """
    m = FM_RE.match(md_txt)
    if not m:
        return ({}, md_txt)
    raw_meta, body = m.group(1), m.group(2)
    meta = {}
    for mm in META_LINE.finditer(raw_meta):
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

def collapse_spaces(s: str) -> str:
    return re.sub(r'\s+', ' ', (s or '').strip())

def title_guess_from_path(p: Path) -> str:
    txt = p.read_text(encoding="utf-8", errors="ignore")
    m = H1_RE.search(txt)
    if m:
        return collapse_spaces(m.group(1))
    return collapse_spaces(p.stem.replace("-", " ").replace("_"," ").title())

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

def editorial_footer_block() -> str:
    return """
<section class="section">
  <div class="card muted">
    <p><strong>Editorial note.</strong> All published transcripts in the Chris Bache Archive are lightly edited for readability. Disfluencies and partial phrases have been removed where they do not affect meaning. Verbatim diarized transcripts are preserved separately for research and verification.</p>
  </div>
</section>""".strip()

def id_footer_block() -> str:
    return """
<footer class="metadata">
  <p>Identifiers:
     <a href="https://www.wikidata.org/wiki/Q112496741" target="_blank" rel="noopener noreferrer">Wikidata Q112496741</a> ·
     <a href="https://openalex.org/A5045900737" target="_blank" rel="noopener noreferrer">OpenAlex A5045900737</a>
  </p>
</footer>""".strip()

def wrap_shell(page_title: str, style_href: str, head_extras: str, body_inner: str, canonical: str | None = None, alternate_md: str | None = None) -> str:
    canonical_link = f'\n  <link rel="canonical" href="{canonical}" />' if canonical else ""
    alt_md_link   = f'\n  <link rel="alternate" type="text/markdown" href="{alternate_md}" />' if alternate_md else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>{html.escape(page_title)}</title>{canonical_link}{alt_md_link}
  <meta name="description" content="Readable, speaker-attributed pages from the Chris Bache Archive." />
  <link rel="stylesheet" href="{style_href}">
{head_extras}
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

# ---- Index mapping (YouTube, published, raw) ---------------------------
def load_index_map(index_path: Path) -> dict[str, dict]:
    mapping: dict[str, dict] = {}
    if not index_path.exists():
        return mapping
    raw = index_path.read_text(encoding="utf-8")
    data = json.loads(raw)
    items = data.get("items", data) if isinstance(data, dict) else data
    for entry in items:
        tpath = entry.get("transcript") or ""
        if not tpath:
            continue
        key = Path(tpath).as_posix()
        yt = entry.get("youtube_url") or (f"https://youtu.be/{entry['youtube_id']}" if entry.get("youtube_id") else None)
        mapping[key] = {
            "youtube_url": yt,
            "youtube_id": entry.get("youtube_id"),
            "published": entry.get("published"),
            "blob_url": entry.get("blob_url") or "",
            "raw_url": entry.get("raw_url") or ""
        }
    return mapping

# ---- JSON-LD + OG/Twitter builders -------------------------------------
def build_jsonld_graph(meta: dict, info: dict, canonical_url: str, h1_title: str) -> str:
    """
    Build a compact @graph:
      - Person with sameAs → Wikidata/OpenAlex
      - VideoObject for original recording (url, embedUrl, thumbnailUrl if YouTube)
      - CreativeWork for transcript (isBasedOn → VideoObject, mainEntityOfPage)
    """
    def nz(x): return (x or "").strip()
    # Prefer explicit recorded_date/datePublished keys, fallback to 'date'
    date = nz(meta.get("recorded_date")) or nz(meta.get("datePublished")) or nz(meta.get("date")) or None
    channel = nz(meta.get("channel")) or None
    publisher = {"@type": "Organization", "name": channel} if channel else None

    yt_url = info.get("youtube_url")
    yt_id  = info.get("youtube_id")
    thumb  = f"https://i.ytimg.com/vi/{yt_id}/hqdefault.jpg" if yt_id else None
    embed  = f"https://www.youtube.com/embed/{yt_id}" if yt_id else None

    # Stable fragment IDs on this page
    person_id = canonical_url + "#person"
    video_id  = canonical_url + "#video"
    tx_id     = canonical_url + "#transcript"

    # Identifiers as resolvable URLs plus value
    identifiers = []
    slug = nz(meta.get("slug"))
    if slug:
        identifiers.append({"@type":"PropertyValue","propertyID":"slug","value":slug})
    identifiers.append({
        "@type":"PropertyValue",
        "propertyID":"wikidata:QID",
        "value":"Q112496741",
        "url":"https://www.wikidata.org/wiki/Q112496741"
    })
    identifiers.append({
        "@type":"PropertyValue",
        "propertyID":"openalex:author",
        "value":"A5045900737",
        "url":"https://openalex.org/A5045900737"
    })

    graph = [
        {
            "@id": person_id,
            "@type": "Person",
            "name": "Christopher M. Bache",
            "sameAs": [
                "https://www.wikidata.org/wiki/Q112496741",
                "https://openalex.org/A5045900737"
            ]
        }
    ]

    video_obj: dict = {
        "@id": video_id,
        "@type": "VideoObject",
        "name": f"{h1_title} (original recording)",
        "inLanguage": "en"
    }
    if yt_url:
        video_obj["url"] = yt_url
        video_obj["sameAs"] = [yt_url]
    if embed:
        video_obj["embedUrl"] = embed
    if thumb:
        video_obj["thumbnailUrl"] = thumb
    # Only append the VideoObject if we have at least a URL or embed/thumbnail (i.e., some signal)
    if any(k in video_obj for k in ("url","embedUrl","thumbnailUrl")):
        graph.append(video_obj)

    transcript_obj: dict = {
        "@id": tx_id,
        "@type": "CreativeWork",
        "name": h1_title,
        "author": { "@id": person_id },
        "inLanguage": "en",
        "isAccessibleForFree": True,
        "license": "https://creativecommons.org/publicdomain/zero/1.0/",
        "url": canonical_url,
        "mainEntityOfPage": canonical_url,
        "identifier": identifiers
    }
    if date:
        transcript_obj["datePublished"] = date
    if publisher:
        transcript_obj["publisher"] = publisher
    if any(o.get("@id")==video_id for o in graph):
        transcript_obj["isBasedOn"] = {"@id": video_id}

    graph.append(transcript_obj)

    data = {"@context": "https://schema.org", "@graph": graph}
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))

def build_social_meta(title: str, description: str, url: str, site_name: str = "Chris Bache Archive") -> str:
    t = html.escape(title)
    d = html.escape(description)
    u = html.escape(url)
    sn = html.escape(site_name)
    return f"""  <meta property="og:type" content="article">
  <meta property="og:site_name" content="{sn}">
  <meta property="og:title" content="{t}">
  <meta property="og:description" content="{d}">
  <meta property="og:url" content="{u}">
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="{t}">
  <meta name="twitter:description" content="{d}">
"""

def build_citation_meta(title: str, author: str, pub_date: str | None, html_url: str) -> str:
    """Highwire/Google Scholar style meta (harmless if ignored)."""
    lines = [
        f'  <meta name="citation_title" content="{html.escape(title)}">',
        f'  <meta name="citation_author" content="{html.escape(author)}">',
        f'  <meta name="citation_fulltext_html_url" content="{html.escape(html_url)}">'
    ]
    if pub_date:
        # Use YYYY/MM/DD if available (Google Scholar often accepts this)
        pd = pub_date.replace("-", "/")
        lines.append(f'  <meta name="citation_publication_date" content="{html.escape(pd)}">')
    return "\n".join(lines) + "\n"

# ---- Page builder -------------------------------------------------------
def process_source_page(md_path: Path, site_base: str, stylesheet: str, pill: str, idx_map: dict[str, dict]):
    # Only top-level files in sources/transcripts (skip subfolders)
    if md_path.parent != SRC_TRANS:
        return

    style_href = f"{site_base.rstrip('/')}/{stylesheet.lstrip('/')}"

    text = md_path.read_text(encoding="utf-8")
    meta, body_md = parse_front_matter(text)
    # normalize speaker labels BEFORE markdown conversion
    body_md = normalize_speaker_labels(body_md or text)
    body_html = ensure_target_blank(md_to_html(body_md))

    # Title (collapse whitespace)
    raw_title = meta.get("title") or title_guess_from_path(md_path)
    title = collapse_spaces(raw_title)
    subtitle = "Readable, speaker-attributed text with links back to the original recording."

    # Index lookup
    rel_key = md_path.relative_to(ROOT).as_posix()
    info = idx_map.get(rel_key, {})
    yt_url = info.get("youtube_url")

    # Buttons
    buttons = [("View Markdown", md_path.name, "outline")]
    if yt_url:
        buttons.insert(0, ("Watch on YouTube", yt_url, "solid"))

    hero = hero_block(
        pill=pill,
        h1=title,
        subtitle_html=html.escape(subtitle),
        buttons=buttons
    )

    # transcript content
    content_block = f"""
<section class="section">
  <div class="card">
    <div class="stack">
      {body_html}
    </div>
  </div>
</section>""".strip()

    # editorial + id footer
    footers = "\n".join([editorial_footer_block(), id_footer_block()])
    inner = "\n".join([hero, content_block, footers])

    # Canonical + alternate (.md) URLs
    out_html = md_path.with_suffix(".html")
    rel_out  = out_html.relative_to(ROOT).as_posix()
    canonical = (site_base.rstrip("/") + "/" + rel_out)
    alt_md    = (site_base.rstrip("/") + "/" + md_path.relative_to(ROOT).as_posix())

    # JSON-LD graph + social meta + citation meta
    jsonld = build_jsonld_graph(meta if isinstance(meta, dict) else {}, info, canonical, title)
    social_meta = build_social_meta(f"{title} — Chris Bache Archive",
                                    "Readable, speaker-attributed transcript with source links and identifiers.",
                                    canonical)
    pub_date = meta.get("recorded_date") or meta.get("datePublished") or meta.get("date")
    citation_meta = build_citation_meta(title, "Christopher M. Bache", pub_date, canonical)

    head_extras = f'{social_meta}{citation_meta}  <script type="application/ld+json">{jsonld}</script>'

    page_html = wrap_shell(f"{title} — Chris Bache Archive", style_href, head_extras, inner,
                           canonical=canonical, alternate_md=alt_md)
    out_html.write_text(page_html, encoding="utf-8")
    print(f"[ok] SRC {out_html.relative_to(ROOT)}")

def build_transcripts(site_base: str, stylesheet: str, idx_map: dict[str, dict]):
    if not SRC_TRANS.exists():
        print(f"[skip] {SRC_TRANS.relative_to(ROOT)} (missing)")
        return
    for md in sorted(SRC_TRANS.glob("*.md")):  # no recursion
        process_source_page(md, site_base, stylesheet, pill="Transcript", idx_map=idx_map)

# ---- Main ---------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site-base", default=DEFAULT_SITE_BASE,
                    help=f"Base URL for canonicals/asset links (default: {DEFAULT_SITE_BASE})")
    ap.add_argument("--stylesheet", default=DEFAULT_STYLESHEET,
                    help=f"Path to CSS within repo (default: {DEFAULT_STYLESHEET})")
    args = ap.parse_args()

    idx_map = load_index_map(INDEX_JSON)
    build_transcripts(args.site_base, args.stylesheet, idx_map)
    print("\nDone.")

if __name__ == "__main__":
    main()