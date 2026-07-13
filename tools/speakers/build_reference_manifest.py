#!/usr/bin/env python3
"""Build a reviewed speaker reference manifest from timecoded diarist files.

The manifest records public source/time ranges that can be used to extract
local reference clips later. It does not create or commit audio embeddings.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


SPEAKER_TS_RE = re.compile(r"^(.+?)\s+(\d{1,2}:\d{2}(?::\d{2})?)\s*$")
SPACE_RE = re.compile(r"\s+")


@dataclass
class Block:
    speaker: str
    start: float
    end: float
    text: str


def parse_timecode(value: str) -> float:
    parts = [int(part) for part in value.split(":")]
    if len(parts) == 2:
        minutes, seconds = parts
        return float(minutes * 60 + seconds)
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return float(hours * 3600 + minutes * 60 + seconds)
    raise ValueError(f"Unsupported timecode: {value}")


def fmt_hhmmss(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def clean_text(lines: Iterable[str]) -> str:
    return SPACE_RE.sub(" ", " ".join(line.strip() for line in lines if line.strip())).strip()


def normalize_speaker(name: str) -> str:
    normalized = SPACE_RE.sub(" ", name.strip()).strip(" :-").casefold()
    normalized = normalized.replace(".", "")
    return normalized


def is_target_speaker(name: str, aliases: set[str]) -> bool:
    return normalize_speaker(name) in aliases


def parse_otter_txt(path: Path) -> list[Block]:
    pending_speaker: str | None = None
    pending_start: float | None = None
    pending_lines: list[str] = []
    raw_blocks: list[tuple[str, float, str]] = []

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = SPEAKER_TS_RE.match(line.strip())
        if match:
            if pending_speaker is not None and pending_start is not None:
                raw_blocks.append((pending_speaker, pending_start, clean_text(pending_lines)))
            pending_speaker = match.group(1).strip()
            pending_start = parse_timecode(match.group(2))
            pending_lines = []
        else:
            pending_lines.append(line)

    if pending_speaker is not None and pending_start is not None:
        raw_blocks.append((pending_speaker, pending_start, clean_text(pending_lines)))

    blocks: list[Block] = []
    for index, (speaker, start, text) in enumerate(raw_blocks):
        if not text:
            continue
        next_start = raw_blocks[index + 1][1] if index + 1 < len(raw_blocks) else start + 45
        if next_start <= start:
            next_start = start + 1
        blocks.append(Block(speaker=speaker, start=start, end=next_start, text=text))
    return blocks


def slug_from_path(path: Path) -> str:
    return path.stem


def load_index(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise SystemExit(f"Unsupported index structure in {path}")
    by_slug: dict[str, dict] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        transcript = item.get("transcript") or item.get("file") or ""
        slug = Path(transcript).stem if transcript else item.get("slug")
        if slug:
            by_slug[str(slug)] = item
    return by_slug


def speaker_set(blocks: list[Block]) -> set[str]:
    return {normalize_speaker(block.speaker) for block in blocks if block.speaker.strip()}


def choose_windows(
    blocks: list[Block],
    aliases: set[str],
    min_seconds: float,
    max_seconds: float,
    max_per_talk: int,
) -> list[Block]:
    windows: list[Block] = []
    for block in blocks:
        if not is_target_speaker(block.speaker, aliases):
            continue
        duration = min(block.end - block.start, max_seconds)
        if duration < min_seconds:
            continue
        windows.append(Block(block.speaker, block.start, block.start + duration, block.text))
        if len(windows) >= max_per_talk:
            break
    return windows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--index", default="index.json", help="Archive index")
    parser.add_argument("--diarist-dir", default="sources/diarist", help="Directory with Otter-style diarist TXT files")
    parser.add_argument("--out", default="data/speakers/chris_bache.reference_manifest.json")
    parser.add_argument("--speaker", default="Chris Bache")
    parser.add_argument("--alias", action="append", default=["Christopher Bache", "Dr Christopher Bache", "Dr. Christopher Bache"])
    parser.add_argument("--max-speakers", type=int, default=2, help="Only use talks with this many or fewer speaker labels")
    parser.add_argument("--min-window", type=float, default=12.0)
    parser.add_argument("--max-window", type=float, default=35.0)
    parser.add_argument("--max-per-talk", type=int, default=6)
    args = parser.parse_args()

    root = Path(args.root)
    diarist_dir = root / args.diarist_dir
    index_by_slug = load_index(root / args.index)
    aliases = {normalize_speaker(args.speaker), *(normalize_speaker(alias) for alias in args.alias)}

    references: list[dict] = []
    skipped: list[dict] = []

    for txt_path in sorted(diarist_dir.glob("*.txt")):
        slug = slug_from_path(txt_path)
        blocks = parse_otter_txt(txt_path)
        if not blocks:
            skipped.append({"slug": slug, "reason": "no_timecoded_blocks"})
            continue
        speakers = speaker_set(blocks)
        if not any(is_target_speaker(block.speaker, aliases) for block in blocks):
            skipped.append({"slug": slug, "reason": "no_target_speaker", "speaker_count": len(speakers)})
            continue
        if len(speakers) > args.max_speakers:
            skipped.append({"slug": slug, "reason": "too_many_speakers", "speaker_count": len(speakers)})
            continue

        item = index_by_slug.get(slug, {})
        windows = choose_windows(blocks, aliases, args.min_window, args.max_window, args.max_per_talk)
        if not windows:
            skipped.append({"slug": slug, "reason": "no_suitable_windows", "speaker_count": len(speakers)})
            continue

        for idx, window in enumerate(windows, 1):
            references.append(
                {
                    "id": f"{slug}#chris-{idx:02d}",
                    "person": "Christopher M. Bache",
                    "speaker_label": window.speaker,
                    "slug": slug,
                    "diarist_txt": str(txt_path.relative_to(root)),
                    "source_url": item.get("youtube_url") or item.get("web_url") or "",
                    "youtube_id": item.get("youtube_id") or "",
                    "audio_path": (item.get("media") or {}).get("audio", f"downloads/audio/{slug}.mp3"),
                    "start_seconds": round(window.start, 3),
                    "end_seconds": round(window.end, 3),
                    "start_hhmmss": fmt_hhmmss(window.start),
                    "end_hhmmss": fmt_hhmmss(window.end),
                    "duration_seconds": round(window.end - window.start, 3),
                    "text_excerpt": window.text[:320],
                    "basis": "timecoded diarist label; source has <= max-speakers speaker labels",
                }
            )

    payload = {
        "schema": "bache-speaker-reference-manifest-v1",
        "person": {
            "name": "Christopher M. Bache",
            "aliases": sorted(aliases),
        },
        "selection": {
            "diarist_dir": args.diarist_dir,
            "max_speakers": args.max_speakers,
            "min_window_seconds": args.min_window,
            "max_window_seconds": args.max_window,
            "max_per_talk": args.max_per_talk,
        },
        "summary": {
            "reference_count": len(references),
            "talk_count": len({ref["slug"] for ref in references}),
            "skipped_count": len(skipped),
        },
        "references": references,
        "skipped": skipped,
    }

    out_path = root / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[ok] references={len(references)} talks={payload['summary']['talk_count']} skipped={len(skipped)}")
    print(f"[ok] wrote {out_path}")


if __name__ == "__main__":
    main()
