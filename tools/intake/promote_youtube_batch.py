#!/usr/bin/env python3
"""Promote fetched YouTube metadata into an agent-reviewed batch plan.

This script is intentionally machine-oriented. It creates the artifacts that a
future coding agent needs to continue a public-video ingestion without reading
prose:

- work/index.patch.json
- work/download.index.json
- work/ingestion.plan.json
- outputs/promotion_report.json

It does not mutate index.json.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

NAME_RE = re.compile(r"\b(chris|christopher)(\s+m\.?)?\s+bache\b", re.I)
BOOK_RE = re.compile(r"\b(lsd and the mind of the universe|diamonds? from heaven|living classroom)\b", re.I)


def load_items(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data["items"]
    if isinstance(data, list):
        return data
    raise SystemExit(f"Unsupported JSON structure: {path}")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def slug_from_record(record: dict[str, Any]) -> str:
    transcript = record.get("transcript") or ""
    return Path(transcript).stem if transcript else ""


def existing_youtube_ids(index_path: Path) -> set[str]:
    return {
        (item.get("youtube_id") or "").strip()
        for item in load_items(index_path)
        if isinstance(item, dict) and item.get("youtube_id")
    }


def metadata_has_required_fields(record: dict[str, Any]) -> bool:
    return all(
        (record.get(field) or "").strip()
        for field in ("youtube_id", "youtube_url", "archival_title", "channel", "published", "duration_hms")
    )


def heuristic_accept(record: dict[str, Any]) -> tuple[bool, list[str]]:
    title = record.get("archival_title") or ""
    channel = record.get("channel") or ""
    reasons: list[str] = []
    if NAME_RE.search(title):
        reasons.append("name_in_title")
    if BOOK_RE.search(title):
        reasons.append("book_phrase_in_title")
    if NAME_RE.search(channel):
        reasons.append("name_in_channel")
    return bool(reasons), reasons


def normalize_record(record: dict[str, Any], policy: str, reason: str) -> dict[str, Any]:
    slug = slug_from_record(record)
    normalized = dict(record)
    normalized["status"] = "metadata-reviewed"
    normalized["notes"] = (
        "Agent-reviewed public YouTube metadata. Proceed through captions, "
        "audio staging, diarization, speaker identity QA, transcript build, "
        "fixity, RAG, web sync, and playlist sync before publication complete."
    )
    normalized["ingestion"] = {
        "schema": "bache.ingestion.record_state.v1",
        "state": "metadata_reviewed",
        "policy": policy,
        "decision_reason": reason,
        "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
        "slug": slug,
        "required_next_states": [
            "captions_captured",
            "audio_staged",
            "diarized",
            "speaker_identity_scored",
            "transcript_built",
            "corpus_finalized",
            "rag_rebuilt_and_checked",
            "web_synced_built_deployed",
            "playlist_synced",
        ],
    }
    return normalized


def build_per_slug_plan(record: dict[str, Any]) -> dict[str, Any]:
    slug = slug_from_record(record)
    audio = ((record.get("media") or {}).get("audio")) or f"downloads/audio/{slug}.mp3"
    return {
        "slug": slug,
        "youtube_id": record.get("youtube_id"),
        "youtube_url": record.get("youtube_url"),
        "title": record.get("archival_title"),
        "published": record.get("published"),
        "artifacts": {
            "captions_auto": f"sources/captions/{slug}.vtt",
            "captions_human": f"sources/captions/{slug}-human.vtt",
            "audio": audio,
            "diarist_txt": f"sources/diarist/{slug}.txt",
            "diarist_srt": f"sources/diarist/{slug}.srt",
            "diarist_json": f"sources/diarist/{slug}.json",
            "speaker_identity_report": f"reports/diarization/{slug}.speaker_identity.json",
            "transcript": f"sources/transcripts/{slug}.md",
        },
        "commands": [
            f"python3 tools/intake/grab_all_captions.py --index <batch>/work/index.patch.json --only {slug}",
            f"python3 tools/media/download_media.py --index <batch>/work/download.index.json --mode audio --audio-dir downloads/audio",
            f"make diarize DIAR_PYTHON=.venv-diarize/bin/python SLUG={slug} AUDIO={audio}",
            f"make speaker-identify SPEAKER_PYTHON=.venv-speakers/bin/python SLUG={slug} AUDIO={audio}",
            f"make transcript SLUG={slug}",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-out", required=True, help="Batch workspace directory")
    parser.add_argument("--index", default="index.json", help="Canonical index used for duplicate checks")
    parser.add_argument(
        "--policy",
        choices=["operator-supplied", "heuristic"],
        default="operator-supplied",
        help="Acceptance policy for metadata_ok new videos",
    )
    args = parser.parse_args()

    batch_dir = Path(args.batch_out)
    metadata_patch = batch_dir / "work" / "index.patch.metadata.json"
    existing_ids = existing_youtube_ids(Path(args.index))
    candidates = load_items(metadata_patch)

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for record in candidates:
        youtube_id = (record.get("youtube_id") or "").strip()
        reasons: list[str] = []
        accept = True

        if not metadata_has_required_fields(record):
            accept = False
            reasons.append("missing_required_metadata")
        if youtube_id in existing_ids:
            accept = False
            reasons.append("already_indexed")

        if args.policy == "heuristic":
            heuristic_ok, heuristic_reasons = heuristic_accept(record)
            reasons.extend(heuristic_reasons)
            if not heuristic_ok:
                accept = False
                reasons.append("heuristic_rejected")
        else:
            reasons.append("operator_supplied_public_url_batch")

        if accept:
            accepted.append(normalize_record(record, args.policy, ",".join(reasons)))
        else:
            rejected.append(
                {
                    "youtube_id": youtube_id,
                    "youtube_url": record.get("youtube_url"),
                    "title": record.get("archival_title"),
                    "reasons": reasons,
                }
            )

    download_index = {
        "schema": "bache.download_index.v1",
        "items": [
            {
                "youtube_id": item.get("youtube_id"),
                "youtube_url": item.get("youtube_url"),
                "slug": slug_from_record(item),
            }
            for item in accepted
        ],
    }
    plan = {
        "schema": "bache.youtube_ingestion_plan.v1",
        "batch_dir": str(batch_dir),
        "policy": args.policy,
        "counts": {
            "candidates": len(candidates),
            "accepted": len(accepted),
            "rejected": len(rejected),
        },
        "commands": {
            "merge_index_preview": (
                f"python3 tools/curation/merge_index.py --base index.json "
                f"--patch {batch_dir}/work/index.patch.json "
                f"--out {batch_dir}/outputs/index.merged.json"
            ),
            "capture_captions_for_batch": (
                f"python3 tools/intake/grab_all_captions.py "
                f"--index {batch_dir}/work/index.patch.json "
                f"--only-from-patch {batch_dir}/work/index.patch.json"
            ),
            "download_audio_for_batch": (
                f"python3 tools/media/download_media.py "
                f"--index {batch_dir}/work/download.index.json "
                f"--mode audio --audio-dir downloads/audio"
            ),
            "refresh_batch_status": f"make youtube-batch-status BATCH_OUT={batch_dir}",
        },
        "items": [build_per_slug_plan(item) for item in accepted],
    }
    report = {
        "schema": "bache.youtube_batch.promotion_report.v1",
        "batch_dir": str(batch_dir),
        "policy": args.policy,
        "accepted_youtube_ids": [item.get("youtube_id") for item in accepted],
        "rejected": rejected,
    }

    write_json(batch_dir / "work" / "index.patch.json", accepted)
    write_json(batch_dir / "work" / "download.index.json", download_index)
    write_json(batch_dir / "work" / "ingestion.plan.json", plan)
    write_json(batch_dir / "outputs" / "promotion_report.json", report)

    print(f"[ok] accepted={len(accepted)} rejected={len(rejected)}")
    print(f"[ok] wrote {batch_dir / 'work' / 'index.patch.json'}")
    print(f"[ok] wrote {batch_dir / 'work' / 'download.index.json'}")
    print(f"[ok] wrote {batch_dir / 'work' / 'ingestion.plan.json'}")
    print(f"[ok] wrote {batch_dir / 'outputs' / 'promotion_report.json'}")


if __name__ == "__main__":
    main()
