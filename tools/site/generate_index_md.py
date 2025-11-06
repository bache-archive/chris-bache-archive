#!/usr/bin/env python3
import json, pathlib, datetime, sys, re

# This file lives at tools/site/generate_index_md.py
# The repo root is two levels up: tools/site -> tools -> <repo root>
ROOT = pathlib.Path(__file__).resolve().parents[2]
INDEX_JSON = ROOT / "index.json"
INDEX_MD   = ROOT / "index.md"

def blob_url(relpath: str) -> str:
    relpath = (relpath or "").lstrip("./")
    if relpath.startswith("sources/"):
        return f"https://github.com/bache-archive/chris-bache-archive/blob/main/{relpath}"
    return relpath

def _as_items(obj):
    # Support either a top-level list or {"items": [...]}
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict) and isinstance(obj.get("items"), list):
        return obj["items"]
    raise ValueError("index.json must be a top-level list or an object with an 'items' array")

def load_items():
    with INDEX_JSON.open("r", encoding="utf-8") as f:
        data = json.load(f)
    items = _as_items(data)

    def k(it):
        d = (it.get("published") or "").strip()
        try:
            return datetime.date.fromisoformat(d)
        except Exception:
            return datetime.date.min

    items.sort(key=k)  # oldest -> newest (chronological)
    return items

# ---- Markdown safety helpers --------------------------------------------

def _collapse_ws(s: str) -> str:
    # collapse all internal whitespace to single spaces, strip edges
    return re.sub(r"\s+", " ", s or "").strip()

def md_escape_cell_text(s: str) -> str:
    """Escape characters that break markdown tables and links, and remove newlines."""
    s = _collapse_ws(str(s))
    # Escape pipes so they don't split columns
    s = s.replace("|", r"\|")
    # Escape brackets in link text to avoid closing prematurely
    s = s.replace("[", r"\[").replace("]", r"\]")
    return s

def md_link(text: str, url: str) -> str:
    if not url:
        return md_escape_cell_text(text)
    # text must be escaped for table safety; URL stays raw
    t = md_escape_cell_text(text)
    return f"[{t}]({url})"

# ---- Render --------------------------------------------------------------

def render_table(items):
    lines = []
    lines.append("# Chris Bache Archive — Index\n")
    lines.append("> Readable transcripts with diarized speaker attributions. See the full project on GitHub and mirrors below.\n")
    lines.append("")
    lines.append("**How to use this page**: Click a title to open the curated transcript. Use “Diarist” for raw speaker-attributed text. “YouTube” opens the original host video when available.\n")
    lines.append("")
    lines.append("| Date | Title (Transcript) | Channel | Type | Diarist | YouTube |")
    lines.append("|---|---|---|---|---|---|")

    for it in items:
        date    = md_escape_cell_text(it.get("published") or "—")
        title   = (it.get("archival_title") or "").strip() or "(untitled)"
        channel = md_escape_cell_text(it.get("channel") or "—")
        stype   = md_escape_cell_text(it.get("source_type") or "—")

        # Transcript URL
        transcript_path = (it.get("transcript") or "").strip()
        transcript_url  = (it.get("blob_url") or "").strip() or (it.get("raw_url") or "").strip()
        if not transcript_url and transcript_path:
            transcript_url = blob_url(transcript_path)

        # Diarist URL
        diarist_path = (it.get("diarist") or "").strip()
        diarist_url  = blob_url(diarist_path) if diarist_path else ""

        # YouTube only (ignore media.audio/video)
        youtube_url = (it.get("youtube_url") or "").strip()
        youtube_cell = md_link("YouTube", youtube_url) if youtube_url else "—"

        row = " | ".join([
            date,
            md_link(title, transcript_url) if transcript_url else md_escape_cell_text(title),
            channel,
            stype,
            md_link("Diarist", diarist_url) if diarist_url else "—",
            youtube_cell,
        ])
        row = _collapse_ws(row)
        lines.append(f"| {row} |")

    # Footer
    lines.append("\n---\n")
    lines.append(
        "**Mirrors & Citation**  \n"
        "- Concept DOI (latest snapshot): https://doi.org/10.5281/zenodo.17088457  \n"
        "- Audio collection (2009–2025): https://archive.org/details/chris-bache-archive-audio  \n"
        "- Video collection (2009–2025): https://archive.org/details/chris-bache-archive-video  \n"
    )
    lines.append("\n_All transcripts and metadata are dedicated to the public domain under CC0 1.0._\n")
    return "\n".join(lines)

def main():
    if not INDEX_JSON.exists():
        print(f"Missing {INDEX_JSON}", file=sys.stderr)
        sys.exit(2)
    items = load_items()
    out = render_table(items)
    INDEX_MD.write_text(out, encoding="utf-8")
    print(f"Wrote {INDEX_MD}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)