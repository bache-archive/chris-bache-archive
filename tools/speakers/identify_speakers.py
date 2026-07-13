#!/usr/bin/env python3
"""Compare diarized speakers against a reviewed Chris Bache reference set.

This command is intentionally an archival QA aid, not an automatic labeler.
It produces suggestions that must be reviewed before transcript labels are
accepted.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Iterable


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


def extract_clip(audio: Path, start: float, end: float, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        str(start),
        "-to",
        str(end),
        "-i",
        str(audio),
        "-ac",
        "1",
        "-ar",
        "16000",
        str(out),
    ]
    subprocess.run(cmd, check=True)


def load_speechbrain_encoder():
    try:
        import torch  # type: ignore
        from speechbrain.inference.speaker import EncoderClassifier  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "ERROR: speaker identification needs speechbrain and torch. Install in a local ML venv:\n"
            "  pip install speechbrain torch torchaudio\n"
        ) from exc

    classifier = EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb")

    def encode(path: Path) -> list[float]:
        signal = classifier.load_audio(str(path))
        embedding = classifier.encode_batch(signal)
        vector = embedding.squeeze().detach().cpu()
        return [float(x) for x in vector.tolist()]

    return encode


def representative_segments(segments: Iterable[dict], max_per_speaker: int, min_seconds: float, max_seconds: float) -> dict[str, list[dict]]:
    by_speaker: dict[str, list[dict]] = defaultdict(list)
    for segment in segments:
        speaker = segment.get("speaker") or "UNKNOWN"
        start = float(segment.get("start", 0))
        end = float(segment.get("end", start))
        duration = end - start
        if duration < min_seconds:
            continue
        by_speaker[speaker].append({**segment, "start": start, "end": min(end, start + max_seconds)})

    selected: dict[str, list[dict]] = {}
    for speaker, speaker_segments in by_speaker.items():
        speaker_segments.sort(key=lambda seg: seg["end"] - seg["start"], reverse=True)
        selected[speaker] = speaker_segments[:max_per_speaker]
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--audio", required=True, help="Audio for the newly diarized item")
    parser.add_argument("--diarization-json", required=True, help="Diarization JSON from tools/diarist/diarize_talk.py")
    parser.add_argument("--reference-clips", default="build/speaker-reference-clips/chris_bache/clips_manifest.json")
    parser.add_argument("--out", required=True, help="JSON report path")
    parser.add_argument("--max-reference-clips", type=int, default=40)
    parser.add_argument("--max-per-speaker", type=int, default=4)
    parser.add_argument("--min-seconds", type=float, default=8.0)
    parser.add_argument("--max-seconds", type=float, default=30.0)
    args = parser.parse_args()

    root = Path(args.root)
    audio = root / args.audio
    if not audio.exists():
        raise SystemExit(f"ERROR: audio not found: {audio}")

    clips_manifest_path = root / args.reference_clips
    if not clips_manifest_path.exists():
        raise SystemExit(f"ERROR: reference clips manifest not found: {clips_manifest_path}")

    reference_clips = json.loads(clips_manifest_path.read_text(encoding="utf-8")).get("clips", [])
    usable_refs = [row for row in reference_clips if row.get("status") == "ok" and (root / row["clip_path"]).exists()]
    if not usable_refs:
        raise SystemExit("ERROR: no usable reference clips. Run make speaker-reference-clips after staging audio.")
    usable_refs = usable_refs[: args.max_reference_clips]

    diarization = json.loads((root / args.diarization_json).read_text(encoding="utf-8"))
    selected = representative_segments(diarization.get("segments", []), args.max_per_speaker, args.min_seconds, args.max_seconds)
    if not selected:
        raise SystemExit("ERROR: no suitable diarized segments to compare")

    encode = load_speechbrain_encoder()

    reference_embeddings = [encode(root / row["clip_path"]) for row in usable_refs]
    reference_centroid = [
        sum(vector[i] for vector in reference_embeddings) / len(reference_embeddings)
        for i in range(len(reference_embeddings[0]))
    ]

    report_rows = []
    with tempfile.TemporaryDirectory(prefix="bache-speaker-identify-") as tmp_name:
        tmp = Path(tmp_name)
        for speaker, segments in selected.items():
            scores: list[float] = []
            samples: list[dict] = []
            for index, segment in enumerate(segments, 1):
                clip = tmp / f"{speaker}_{index}.wav"
                extract_clip(audio, segment["start"], segment["end"], clip)
                score = cosine(encode(clip), reference_centroid)
                scores.append(score)
                samples.append(
                    {
                        "start": segment["start"],
                        "end": segment["end"],
                        "duration": round(segment["end"] - segment["start"], 3),
                        "score": round(score, 4),
                        "text_excerpt": (segment.get("text") or "")[:220],
                    }
                )

            mean_score = sum(scores) / len(scores)
            report_rows.append(
                {
                    "speaker": speaker,
                    "mean_similarity_to_chris_reference": round(mean_score, 4),
                    "sample_count": len(samples),
                    "samples": samples,
                }
            )

    report_rows.sort(key=lambda row: row["mean_similarity_to_chris_reference"], reverse=True)
    payload = {
        "schema": "bache-speaker-identity-report-v1",
        "audio": args.audio,
        "diarization_json": args.diarization_json,
        "reference_clips": args.reference_clips,
        "review_required": True,
        "suggested_chris_speaker": report_rows[0]["speaker"] if report_rows else None,
        "speakers": report_rows,
    }
    out_path = root / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[ok] suggested_chris_speaker={payload['suggested_chris_speaker']}")
    print(f"[ok] wrote {out_path}")


if __name__ == "__main__":
    main()
