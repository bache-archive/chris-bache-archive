#!/usr/bin/env python3
import json, pathlib, datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]  # repo root
index_json = ROOT / "index.json"
index_md   = ROOT / "index.md"

def md_link(text, url):
    return f"[{text}]({url})" if url else text

def has_ext(media_dict, key, ext):
    try:
        return media_dict.get(key, "").lower().endswith(ext)
    except Exception:
        return False

with index_json.open("r", encoding="utf-8") as f:
    items = json.load(f)

# sort by published date (YYYY-MM-DD), falling back to 'archival_title'
def keyfunc(x):
    d = x.get("published", "") or ""
    try:
        return (datetime.date.fromisoformat(d), x.get("archival_title",""))
    except Exception:
        return (datetime.date.min, x.get("archival_title",""))
items.sort(key=keyfunc)

lines = []
lines.append("# Chris Bache Archive — Index\n")
lines.append("> Readable transcripts with diarized speaker attributions. See the full project on GitHub and mirrors below.\n")
lines.append("")
lines.append("**How to use this page**: Click a title to open the curated transcript. Use “Diarist” for raw speaker-attributed text. “Media” shows available audio/video/YouTube links.\n")
lines.append("")
lines.append("| Date | Title (Transcript) | Channel | Type | Diarist | Media |")
lines.append("|---|---|---|---|---|---|")

for it in items:
    date = it.get("published","")
    title = it.get("archival_title","").strip() or "(untitled)"
    channel = it.get("channel","").strip()
    stype = it.get("source_type","").strip()
    # links
    transcript_url = it.get("blob_url") or it.get("raw_url") or it.get("transcript")
    diarist_rel    = it.get("diarist") or ""
    diarist_url    = f"https://github.com/bache-archive/chris-bache-archive/blob/main/{diarist_rel}" if diarist_rel and diarist_rel.startswith("sources/") else diarist_rel

    # media flags/links
    media = it.get("media", {}) or {}
    audio = md_link("audio", media.get("audio")) if has_ext(media, "audio", ".mp3") else ""
    video = md_link("video", media.get("video")) if has_ext(media, "video", ".mp4") else ""
    yt    = md_link("YouTube", it.get("youtube_url")) if it.get("youtube_url") else ""

    media_bits = " · ".join([b for b in (audio, video, yt) if b]) or "—"

    # row
    row = [
        date or "—",
        md_link(title, transcript_url) if transcript_url else title,
        channel or "—",
        stype or "—",
        md_link("Diarist", diarist_url) if diarist_url else "—",
        media_bits
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
