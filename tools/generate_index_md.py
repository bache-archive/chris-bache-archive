#!/usr/bin/env python3
import json, pathlib, datetime, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]  # repo root
index_json = ROOT / "index.json"
index_md   = ROOT / "index.md"

def blob_url(relpath: str) -> str:
    relpath = relpath.lstrip("./")
    if relpath.startswith("sources/"):
        return f"https://github.com/bache-archive/chris-bache-archive/blob/main/{relpath}"
    return relpath  # if it's already a URL, keep as-is

def load_items():
    with index_json.open("r", encoding="utf-8") as f:
        return json.load(f)

def sort_key(x):
    d = (x.get("published") or "").strip()
    try:
        return (datetime.date.fromisoformat(d), x.get("archival_title",""))
    except Exception:
        # push undated to top with minimal date, still deterministic
        return (datetime.date.min, x.get("archival_title",""))

def md_link(text, url):
    if not url:
        return text
    return f"[{text}]({url})"

def main():
    items = load_items()
    items.sort(key=sort_key)

    lines = []
    lines.append("# Chris Bache Archive — Index\n")
    lines.append("> Readable transcripts with diarized speaker attributions. See the full project on GitHub and mirrors below.\n")
    lines.append("")
    lines.append("**How to use this page**: Click a title to open the curated transcript. Use “Diarist” for raw speaker-attributed text. “YouTube” links open the original host video when available.\n")
    lines.append("")
    lines.append("| Date | Title (Transcript) | Channel | Type | Diarist | YouTube |")
    lines.append("|---|---|---|---|---|---|")

    for it in items:
        date    = (it.get("published") or "").strip() or "—"
        title   = (it.get("archival_title") or "").strip() or "(untitled)"
        channel = (it.get("channel") or "").strip() or "—"
        stype   = (it.get("source_type") or "").strip() or "—"

        # Transcript link: prefer explicit blob/raw URLs if present, else build blob URL from path under sources/
        transcript_path = (it.get("transcript") or "").strip()
        transcript_url  = (it.get("blob_url") or "").strip() or (it.get("raw_url") or "").strip()
        if not transcript_url and transcript_path:
            transcript_url = blob_url(transcript_path)

        # Diarist link (if present)
        diarist_path = (it.get("diarist") or "").strip()
        diarist_url  = blob_url(diarist_path) if diarist_path else ""

        # Only include YouTube; ignore media.audio/media.video
        youtube_url = (it.get("youtube_url") or "").strip()
        youtube_cell = md_link("YouTube", youtube_url) if youtube_url else "—"

        row = [
            date,
            md_link(title, transcript_url) if transcript_url else title,
            channel,
            stype,
            md_link("Diarist", diarist_url) if diarist_url else "—",
            youtube_cell,
        ]
        lines.append("| " + " | ".join(row) + " |")

    # footer mirrors / licensing
    lines.append("\n---\n")
    lines.append("**Mirrors & Citation**  \n"
                 "- Concept DOI (latest snapshot): https://doi.org/10.5281/zenodo.17100583  \n"
                 "- Latest release v2.4: https://doi.org/10.5281/zenodo.17238386  \n"
                 "- Internet Archive transcripts snapshot (v2.4): https://archive.org/details/chris-bache-archive-v2.4  \n"
                 "- Audio collection (2014–2025): https://archive.org/details/chris-bache-archive-audio  \n"
                 "- Video collection (2014–2025): https://archive.org/details/chris-bache-archive-video  \n")
    lines.append("\n_All transcripts and metadata are dedicated to the public domain under CC0 1.0._\n")

    index_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {index_md}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)