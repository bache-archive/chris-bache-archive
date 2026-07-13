#!/usr/bin/env python3
"""Fetch public YouTube metadata for a prepared intake batch.

Writes review artifacts only. It does not mutate index.json.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
NON_SLUG_RE = re.compile(r"[^a-z0-9]+")


def extract_video_id(value: str) -> str:
    raw = value.strip()
    if YOUTUBE_ID_RE.match(raw):
        return raw
    parsed = urlparse(raw)
    host = parsed.netloc.lower()
    parts = [part for part in parsed.path.split("/") if part]
    if host.endswith("youtu.be") and parts and YOUTUBE_ID_RE.match(parts[0]):
        return parts[0]
    if "youtube.com" in host:
        query_id = parse_qs(parsed.query).get("v", [""])[0]
        if YOUTUBE_ID_RE.match(query_id):
            return query_id
        for marker in ("shorts", "embed", "live"):
            if marker in parts:
                idx = parts.index(marker)
                if idx + 1 < len(parts) and YOUTUBE_ID_RE.match(parts[idx + 1]):
                    return parts[idx + 1]
    raise ValueError(f"Could not extract YouTube ID from {value!r}")


def normalize_url(value: str) -> str:
    return f"https://youtu.be/{extract_video_id(value)}"


def load_urls(path: Path) -> list[str]:
    urls: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        urls.extend(part.strip() for part in line.split() if part.strip())
    return [normalize_url(url) for url in urls]


def slugify(text: str, max_words: int = 11) -> str:
    words = [word for word in NON_SLUG_RE.sub("-", text.casefold()).strip("-").split("-") if word]
    return "-".join(words[:max_words]) or "untitled-youtube-video"


def parse_upload_date(value: str | None) -> str:
    if not value:
        return ""
    value = value.strip()
    if re.fullmatch(r"\d{8}", value):
        return f"{value[:4]}-{value[4:6]}-{value[6:8]}"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return value[:10] if len(value) >= 10 else value


def duration_hms(duration: int | float | None, fallback: str | None) -> str:
    if fallback:
        return fallback
    if duration is None:
        return ""
    total = int(round(float(duration)))
    hours = total // 3600
    minutes = (total % 3600) // 60
    seconds = total % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"


def fetch_metadata(url: str, yt_dlp: str) -> dict:
    result = subprocess.run(
        [yt_dlp, "--skip-download", "--dump-json", url],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        return {
            "youtube_id": extract_video_id(url),
            "youtube_url": normalize_url(url),
            "status": "metadata_failed",
            "error": result.stderr.strip()[-1200:],
        }
    data = json.loads(result.stdout)
    video_id = data.get("id") or extract_video_id(url)
    return {
        "youtube_id": video_id,
        "youtube_url": f"https://youtu.be/{video_id}",
        "status": "metadata_ok",
        "archival_title": data.get("title") or "",
        "channel": data.get("channel") or data.get("uploader") or "",
        "published": parse_upload_date(data.get("upload_date") or data.get("release_date") or data.get("timestamp")),
        "duration_hms": duration_hms(data.get("duration"), data.get("duration_string")),
        "webpage_url": data.get("webpage_url") or url,
        "thumbnail": data.get("thumbnail") or "",
    }


def patch_record(meta: dict, default_source_type: str) -> dict:
    title = meta.get("archival_title") or f"TODO: title for {meta['youtube_id']}"
    date_prefix = meta.get("published") or "TODO-date"
    slug = f"{date_prefix}-{slugify(title)}"
    return {
        "archival_title": title,
        "channel": meta.get("channel", ""),
        "source_type": default_source_type,
        "transcript": f"sources/transcripts/{slug}.md",
        "diarist": f"sources/diarist/{slug}.txt",
        "youtube_id": meta["youtube_id"],
        "youtube_url": meta["youtube_url"],
        "web_url": "",
        "duration_hms": meta.get("duration_hms", ""),
        "media": {
            "audio": f"downloads/audio/{slug}.mp3",
            "video": f"downloads/video/{slug}.mp4",
        },
        "blob_url": "",
        "raw_url": "",
        "published": meta.get("published", ""),
        "status": "pending-review",
        "notes": "Auto-prepared from public YouTube metadata; review slug, title, source_type, and rights before merging.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--urls", required=True, help="Text file with URLs or YouTube IDs")
    parser.add_argument("--out-dir", required=True, help="Patch workspace directory")
    parser.add_argument("--yt-dlp", default="yt-dlp")
    parser.add_argument("--source-type", default="interview")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    outputs_dir = out_dir / "outputs"
    work_dir = out_dir / "work"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    metadata = [fetch_metadata(url, args.yt_dlp) for url in load_urls(Path(args.urls))]
    patch = [patch_record(item, args.source_type) for item in metadata if item["status"] == "metadata_ok"]

    (outputs_dir / "youtube_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (work_dir / "index.patch.metadata.json").write_text(json.dumps(patch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    ok = sum(1 for item in metadata if item["status"] == "metadata_ok")
    failed = len(metadata) - ok
    print(f"[ok] metadata_ok={ok} metadata_failed={failed}")
    print(f"[ok] wrote {outputs_dir / 'youtube_metadata.json'}")
    print(f"[ok] wrote {work_dir / 'index.patch.metadata.json'}")


if __name__ == "__main__":
    main()
