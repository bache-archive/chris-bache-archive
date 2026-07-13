#!/usr/bin/env python3
"""Prepare an offline-safe YouTube intake batch workspace.

This script intentionally does not call YouTube. It normalizes public URLs,
dedupes them, checks the existing archive index, and writes review artifacts
that can be completed later with network-fetched metadata and transcript work.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def extract_video_id(value: str) -> str:
    raw = value.strip()
    if YOUTUBE_ID_RE.match(raw):
        return raw

    parsed = urlparse(raw)
    host = parsed.netloc.lower()
    path_parts = [part for part in parsed.path.split("/") if part]

    if host.endswith("youtu.be") and path_parts:
        candidate = path_parts[0]
        if YOUTUBE_ID_RE.match(candidate):
            return candidate

    if "youtube.com" in host:
        query_id = parse_qs(parsed.query).get("v", [""])[0]
        if YOUTUBE_ID_RE.match(query_id):
            return query_id
        for marker in ("shorts", "embed", "live"):
            if marker in path_parts:
                idx = path_parts.index(marker)
                if idx + 1 < len(path_parts) and YOUTUBE_ID_RE.match(path_parts[idx + 1]):
                    return path_parts[idx + 1]

    raise ValueError(f"Could not extract an 11-character YouTube ID from: {value}")


def load_urls(path: Path) -> list[str]:
    urls: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        urls.extend(part.strip() for part in line.split() if part.strip())
    return urls


def load_index(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise SystemExit(f"Unsupported index structure in {path}")
    return {
        item["youtube_id"]: item
        for item in items
        if isinstance(item, dict) and item.get("youtube_id")
    }


def slug_placeholder(video_id: str) -> str:
    return f"TODO-slug-for-{video_id}"


def patch_skeleton(video_id: str, source_type: str) -> dict:
    slug = slug_placeholder(video_id)
    return {
        "youtube_id": video_id,
        "youtube_url": f"https://youtu.be/{video_id}",
        "archival_title": f"TODO: fetch metadata/title for {video_id}",
        "channel": "",
        "source_type": source_type,
        "published": "",
        "duration_hms": "",
        "transcript": f"sources/transcripts/{slug}.md",
        "diarist": f"sources/diarist/{slug}.txt",
        "media": {
            "audio": f"downloads/audio/{slug}.mp3",
            "video": f"downloads/video/{slug}.mp4",
        },
        "status": "pending-metadata",
        "notes": "Generated from public YouTube batch. Fetch title/channel/date/duration and assign slug before merge.",
    }


def write_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--urls", required=True, help="Text file containing public YouTube URLs or IDs")
    parser.add_argument("--index", default="index.json", help="Archive index to check for existing IDs")
    parser.add_argument("--out-dir", required=True, help="Patch workspace directory to write")
    parser.add_argument("--source-type", default="interview", help="Default source_type for new skeleton rows")
    args = parser.parse_args()

    urls_path = Path(args.urls)
    index_path = Path(args.index)
    out_dir = Path(args.out_dir)

    existing_by_id = load_index(index_path)
    seen: set[str] = set()
    rows: list[dict[str, str]] = []
    skeletons: list[dict] = []

    for raw_url in load_urls(urls_path):
        video_id = extract_video_id(raw_url)
        normalized_url = f"https://youtu.be/{video_id}"
        duplicate_in_batch = video_id in seen
        seen.add(video_id)

        existing = existing_by_id.get(video_id)
        status = "duplicate-in-batch" if duplicate_in_batch else ("already-indexed" if existing else "new")
        slug = ""
        transcript = ""
        if existing:
            transcript = existing.get("transcript") or existing.get("file") or ""
            slug = Path(transcript).stem if transcript else ""
        elif not duplicate_in_batch:
            skeletons.append(patch_skeleton(video_id, args.source_type))

        rows.append(
            {
                "video_id": video_id,
                "normalized_url": normalized_url,
                "status": status,
                "existing_slug": slug,
                "existing_transcript": transcript,
            }
        )

    inputs_dir = out_dir / "inputs"
    work_dir = out_dir / "work"
    outputs_dir = out_dir / "outputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    write_lines(inputs_dir / "urls.normalized.txt", [row["normalized_url"] for row in rows])
    write_lines(work_dir / "new_video_ids.txt", [row["video_id"] for row in rows if row["status"] == "new"])
    write_lines(work_dir / "existing_video_ids.txt", [row["video_id"] for row in rows if row["status"] == "already-indexed"])

    (work_dir / "index.patch.skeleton.json").write_text(
        json.dumps(skeletons, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with (outputs_dir / "intake_status.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "video_id",
                "normalized_url",
                "status",
                "existing_slug",
                "existing_transcript",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"[ok] read {len(rows)} URL(s), {len(skeletons)} new item(s)")
    print(f"[ok] wrote {out_dir}")


if __name__ == "__main__":
    main()
