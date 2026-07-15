#!/usr/bin/env python3
"""Summarize a staged YouTube batch for future agents.

The canonical output is JSON. This repo assumes future operators are coding
agents with large context windows, so the status is optimized for direct machine
consumption rather than human-readable prose. It does not mutate archive index
data.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path):
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def slug_from_record(record: dict) -> str:
    transcript = record.get("transcript") or ""
    return Path(transcript).stem if transcript else ""


def build_summary(batch_dir: Path) -> dict:
    intake_rows = read_csv(batch_dir / "outputs" / "intake_status.csv")
    captions_rows = read_csv(batch_dir / "outputs" / "captions_manifest.csv")
    media_rows = read_csv(batch_dir / "outputs" / "media_manifest.csv")
    smoke_report = read_json(batch_dir / "outputs" / "diarization_smoke_report.json")
    metadata = read_json(batch_dir / "outputs" / "youtube_metadata.json")
    patch = read_json(batch_dir / "work" / "index.patch.metadata.json")
    promoted_patch = read_json(batch_dir / "work" / "index.patch.json")
    promotion_report = read_json(batch_dir / "outputs" / "promotion_report.json")
    ingestion_plan = read_json(batch_dir / "work" / "ingestion.plan.json")

    metadata_by_id = {item.get("youtube_id"): item for item in metadata if item.get("youtube_id")}
    patch_by_id = {item.get("youtube_id"): item for item in patch if item.get("youtube_id")}
    promoted_by_id = {item.get("youtube_id"): item for item in promoted_patch if item.get("youtube_id")}
    captions_by_id = {row.get("youtube_id"): row for row in captions_rows if row.get("youtube_id")}
    media_by_slug = {row.get("slug"): row for row in media_rows if row.get("slug")}

    items = []
    for row in intake_rows:
        video_id = row.get("video_id", "")
        meta = metadata_by_id.get(video_id, {})
        patch_record = patch_by_id.get(video_id, {})
        promoted_record = promoted_by_id.get(video_id, {})
        captions_record = captions_by_id.get(video_id, {})
        promoted_slug = slug_from_record(promoted_record or patch_record)
        media_record = media_by_slug.get(promoted_slug, {})
        items.append(
            {
                "youtube_id": video_id,
                "url": row.get("normalized_url", ""),
                "intake_status": row.get("status", ""),
                "metadata_status": meta.get("status", "not-fetched"),
                "promotion_status": "accepted" if promoted_record else ("not-applicable" if row.get("status") == "already-indexed" else "not-promoted"),
                "ingestion_state": ((promoted_record.get("ingestion") or {}).get("state") if promoted_record else ""),
                "captions_status": captions_record.get("status", "not-run" if promoted_record else "not-applicable"),
                "captions_auto_path": captions_record.get("auto_path", ""),
                "captions_human_path": captions_record.get("human_path", ""),
                "media_status": media_record.get("status", "not-run" if promoted_record else "not-applicable"),
                "audio_path": media_record.get("audio_path", ""),
                "video_path": media_record.get("video_path", ""),
                "published": meta.get("published") or patch_record.get("published", ""),
                "duration_hms": meta.get("duration_hms") or patch_record.get("duration_hms", ""),
                "channel": meta.get("channel") or patch_record.get("channel", ""),
                "title": meta.get("archival_title") or patch_record.get("archival_title", ""),
                "proposed_slug": promoted_slug,
                "existing_slug": row.get("existing_slug", ""),
                "existing_transcript": row.get("existing_transcript", ""),
            }
        )

    return {
        "schema": "bache.youtube_batch.agent_status.v1",
        "batch_dir": str(batch_dir),
        "counts": {
            "intake": dict(Counter(item["intake_status"] for item in items)),
            "metadata": dict(Counter(item["metadata_status"] for item in items)),
            "promotion": dict(Counter(item["promotion_status"] for item in items)),
            "captions": dict(Counter(item["captions_status"] for item in items)),
            "media": dict(Counter(item["media_status"] for item in items)),
            "metadata_patch_records": len(patch),
            "promoted_patch_records": len(promoted_patch),
            "ingestion_plan_items": len(ingestion_plan.get("items", [])) if isinstance(ingestion_plan, dict) else 0,
        },
        "promotion_report": promotion_report if promotion_report else None,
        "diarization_smoke_report": smoke_report if smoke_report else None,
        "items": items,
        "agent_next_actions": [
            {
                "id": "review_metadata_patch",
                "input": "work/index.patch.metadata.json",
                "output": "work/index.patch.json",
                "instruction": "Filter already-indexed/rejected candidates; verify public-source scope; normalize source_type, title, channel, published date, duration_hms, transcript path, diarist path, media paths, notes, and slug.",
            },
            {
                "id": "merge_index",
                "command": "python3 tools/curation/merge_index.py --base index.json --patch <batch>/work/index.patch.json --out <batch>/outputs/index.merged.json",
                "instruction": "Diff index.json against merged output before replacing index.json.",
            },
            {
                "id": "process_accepted_slugs",
                "per_slug_commands": [
                    "make captions SLUG=<slug>",
                    "stage ignored audio at downloads/audio/<slug>.mp3",
                    "make diarize DIAR_PYTHON=.venv-diarize/bin/python SLUG=<slug> AUDIO=downloads/audio/<slug>.mp3",
                    "make speaker-identify SPEAKER_PYTHON=.venv-speakers/bin/python SLUG=<slug> AUDIO=downloads/audio/<slug>.mp3",
                    "make transcript SLUG=<slug>",
                ],
            },
            {
                "id": "publish_and_downstream",
                "commands": [
                    "make finalize",
                    "python3 tools/rag/chunk_transcripts.py",
                    "python3 tools/rag/embed_and_faiss.py",
                    "make audit-parquet",
                    "cd ../bache-archive-web && npm run sync:archive && npm run typecheck && npm run lint && npm run build",
                    "make playlist-sync PLAYLIST_ID=<playlist-id> PLAYLIST_EXTRA='--dry-run'",
                ],
            },
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch_dir", help="Batch directory under patches/")
    args = parser.parse_args()

    batch_dir = Path(args.batch_dir)
    summary = build_summary(batch_dir)
    (batch_dir / "outputs").mkdir(parents=True, exist_ok=True)
    (batch_dir / "outputs" / "agent_status.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"[ok] wrote {batch_dir / 'outputs' / 'agent_status.json'}")


if __name__ == "__main__":
    main()
