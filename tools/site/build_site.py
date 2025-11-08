#!/usr/bin/env python3
"""
tools/site/build_site.py

Build styled static HTML wrappers ONLY for:
  • sources/transcripts/*.md    (skips _archive/ and extras/)
Adds:
  • Compact JSON-LD in <head> (Google-preferred)
  • Hidden mirrored text block at bottom of <body> (LLM-friendly)
  • "Watch on YouTube" button via index.json
  • Speaker label normalizer (**Name:** …), incl. Audience fixes
  • Editorial note appended at end of page

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

# Speaker normalization patterns
# 1) "**Name: ** rest"  -> "**Name:** rest"
SPEAKER_LINE_RE = re.compile(
    r'^(?P<lead>\s*)\*\*\s*(?P<name>[^*:]{1,120}?)\s*:\s*\*\*(?P<tail>\s*)(?P<rest>.*)$',
    re.M
)
# 2) "** Name **: rest" -> "**Name:** rest"
SPEAKER_WEIRD_RE = re.compile(
    r'^(?P<lead>\s*)\*\*\s*(?P<name>[^*:]{1,120}?)\s*\*\*\s*:\s*(?P<rest>.*)$',
    re.M
)
# 3) Leading italics before a label: "* Name: ** rest" -> "**Name:** rest"
SPEAKER_ITALIC_LEAD_RE = re.compile(
    r'^(?P<lead>\s*)[*_]{1,3}\s*(?P<name>[A-Z][^*:]{0,120}?)\s*:\s*\*\*\s*(?P<rest>.*)$',
    re.M
)
# 4) Specific Audience fixes:
#    "Audience: ** rest" -> "**Audience:** rest"
AUDIENCE_TRAIL_BOLD_RE = re.compile(
    r'^(?P<lead>\s*)Audience\s*:\s*\*\*\s*(?P<rest>.*)$',
    re.M | re.I
)
#    plain "Audience: rest" -> "**Audience:** rest"
AUDIENCE_PLAIN_RE = re.compile(
    r'^(?P<lead>\s*)Audience\s*:\s*(?P<rest>.+)$',
    re.M | re.I
)

# Optionally broaden to Host/Moderator if helpful later:
GENERIC_LABELS = ("Audience","Host","Moderator","MC","Interviewer","Participant")

def normalize_speaker_labels(md: str) -> str:
    def _mk(name: str, rest: str, lead: str = "") -> str:
        return f"{lead}**{name.strip()}:** {rest.strip()}"

    # 1/2) Core bold-ordering fixes
    md = SPEAKER_LINE_RE.sub(lambda m: _mk(m.group('name'), m.group('rest'), m.group('lead')), md)
    md = SPEAKER_WEIRD_RE.sub(lambda m: _mk(m.group('name'), m.group('rest'), m.group('lead')), md)

    # 3) Strip leading italics around a label that then has "**" before text
    md = SPEAKER_ITALIC_LEAD_RE.sub(lambda m: _mk(m.group('name'), m.group('rest'), m.group('lead')), md)

    # 4a) Audience: ** rest  -> **Audience:** rest
    md = AUDIENCE_TRAIL_BOLD_RE.sub(lambda m: _mk("Audience", m.group('rest'), m.group('lead')), md)

    # 4b) Audience: rest (plain) -> **Audience:** rest
    # Guard against double-normalizing lines already starting with "**Audience:**"
    def _aud_plain(m):
        lead, rest = m.group('lead') or "", m.group('rest') or ""
        if rest.lstrip().startswith("**"):  # already normalized form
            return m.group(0)
        return _mk("Audience", rest, lead)
    md = AUDIENCE_PLAIN_RE.sub(_aud_plain, md)

    return md

def parse_front_matter(md_txt: str) -> tuple[dict, str]:
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

def title_guess_from_path(p: Path) -> str:
    txt = p.read_text(encoding="utf-8", errors="ignore")
    m = H1_RE.search(txt)
    if m:
        return m.group(1).strip()
    return p.stem.replace("-", " ").replace("_"," ").title()

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

def wrap_shell(page_title: str, style_href: str, head_jsonld: str, body_inner: str, hidden_tail: str, canonical: str | None = None) -> str:
    canonical_link = f'\n  <link rel="canonical" href="{canonical}" />' if canonical else ""
    jsonld_block  = f'\n  <script type="application/ld+json">{head_jsonld}</script>' if head_jsonld else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>{html.escape(page_title)}</title>{canonical_link}
  <meta name="description" content="Readable, styled pages from the Chris Bache Archive." />
  <link rel="stylesheet" href="{style_href}">{jsonld_block}
</head>
<body>
  <div class="container">
{body_inner}
    <div class="footer muted">
      Built by the Chris Bache Archive · <a href="/chris-bache-archive/">Home</a>
    </div>
  </div>
{hidden_tail}
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

# ---- Compact JSON-LD for <head> (strings only) -------------------------
def build_json_ld_compact(meta: dict, info: dict, canonical_url: str | None) -> str:
    def nz(x): return (x or "").strip()
    title   = nz(meta.get("title")) or "Transcript"
    date    = nz(meta.get("date")) or None
    channel = nz(meta.get("channel"))
    slug    = nz(meta.get("slug"))
    youtube = info.get("youtube_url")
    data = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "datePublished": date,
        "inLanguage": "en",
        "isAccessibleForFree": True,
        "license": "https://creativecommons.org/publicdomain/zero/1.0/",
        "author": [{"@type": "Person", "name": "Christopher M. Bache"}],
        "identifier": [
            {"@type": "PropertyValue", "propertyID": "slug", "value": slug},
            {"@type": "PropertyValue", "propertyID": "wikidata_person", "value": "Q112496741"},
            {"@type": "PropertyValue", "propertyID": "openalex_person", "value": "A5045900737"}
        ],
        "url": canonical_url or None,
        "sameAs": [youtube] if youtube else None,
        "publisher": {"@type":"Organization","name": channel} if channel else None
    }
    clean = {k: v for k, v in data.items() if v not in (None, [], "")}
    return json.dumps(clean, ensure_ascii=False, separators=(",", ":"))

def hidden_mirror_text(meta: dict, info: dict) -> str:
    esc = lambda s: html.escape((s or "").strip())
    title   = esc(meta.get("title"))
    date    = esc(meta.get("date"))
    typ     = esc(meta.get("type"))
    channel = esc(meta.get("channel"))
    slug    = esc(meta.get("slug"))
    yt_url  = esc(info.get("youtube_url") or "")
    wid     = "Q112496741"
    oid     = "A5045900737"
    return f"""
<!-- machine-readable metadata (hidden mirror) -->
<section aria-hidden="true" style="display:none">
  <p data-meta="title">{title}</p>
  <p data-meta="date">{date}</p>
  <p data-meta="type">{typ}</p>
  <p data-meta="channel">{channel}</p>
  <p data-meta="slug">{slug}</p>
  <p data-meta="wikidata_person">{wid}</p>
  <p data-meta="openalex_person">{oid}</p>
  {"<p data-meta='youtube_url'>" + yt_url + "</p>" if yt_url else ""}
</section>""".strip()

# ---- Page builder -------------------------------------------------------
def process_source_page(md_path: Path, site_base: str, stylesheet: str, pill: str, idx_map: dict[str, dict]):
    # Only top-level files in sources/transcripts (skip _archive/ and extras/)
    if md_path.parent != SRC_TRANS:
        return

    style_href = f"{site_base.rstrip('/')}/{stylesheet.lstrip('/')}"

    text = md_path.read_text(encoding="utf-8")
    meta, body_md = parse_front_matter(text)

    # normalize speaker labels BEFORE markdown conversion
    body_md = normalize_speaker_labels(body_md or text)
    body_html = ensure_target_blank(md_to_html(body_md))

    title = meta.get("title") or title_guess_from_path(md_path)
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

    # Transcript card (no "Document" heading)
    content_block = f"""
<section class="section">
  <div class="card">
    <div class="stack">
      {body_html}
    </div>
  </div>
</section>""".strip()

    # Editorial note at the very end (visible)
    editorial_note = """
<section class="section">
  <div class="card">
    <p class="muted" style="font-size:0.95rem; line-height:1.5">
      <strong>Editorial note.</strong> All published transcripts in the Chris Bache Archive are lightly edited for readability.
      Disfluencies and partial phrases have been removed where they do not affect meaning.
      Verbatim diarized transcripts are preserved separately for research and verification.
    </p>
  </div>
</section>""".strip()

    inner = "\n".join([hero, content_block, editorial_note])

    # Canonical URL
    out_html = md_path.with_suffix(".html")
    rel_out  = out_html.relative_to(ROOT).as_posix()
    canonical = (site_base.rstrip("/") + "/" + rel_out)

    # Compact JSON-LD in <head>
    head_jsonld = build_json_ld_compact(meta if isinstance(meta, dict) else {}, info, canonical)

    # Hidden mirror at bottom of <body>
    hidden_tail = hidden_mirror_text(meta, info)

    page_html = wrap_shell(f"{title} — Chris Bache Archive", style_href, head_jsonld, inner, hidden_tail, canonical=canonical)
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