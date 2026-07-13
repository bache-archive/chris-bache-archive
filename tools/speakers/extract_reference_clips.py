#!/usr/bin/env python3
"""Extract local speaker reference clips from a reference manifest."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def run_ffmpeg(audio: Path, start: float, end: float, out: Path) -> bool:
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
    result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.returncode == 0 and out.exists() and out.stat().st_size > 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--manifest", default="data/speakers/chris_bache.reference_manifest.json")
    parser.add_argument("--out-dir", default="build/speaker-reference-clips/chris_bache")
    args = parser.parse_args()

    root = Path(args.root)
    manifest = json.loads((root / args.manifest).read_text(encoding="utf-8"))
    out_dir = root / args.out_dir
    rows = []

    for ref in manifest.get("references", []):
        audio_path = root / ref["audio_path"]
        clip_path = out_dir / f"{ref['id'].replace('#', '__')}.wav"
        status = "missing_audio"
        if audio_path.exists():
            status = "ok" if run_ffmpeg(audio_path, ref["start_seconds"], ref["end_seconds"], clip_path) else "ffmpeg_failed"
        rows.append({**ref, "clip_path": str(clip_path.relative_to(root)), "status": status})

    report = {
        "schema": "bache-speaker-reference-clips-v1",
        "source_manifest": args.manifest,
        "out_dir": args.out_dir,
        "summary": {
            "ok": sum(1 for row in rows if row["status"] == "ok"),
            "missing_audio": sum(1 for row in rows if row["status"] == "missing_audio"),
            "failed": sum(1 for row in rows if row["status"] == "ffmpeg_failed"),
        },
        "clips": rows,
    }
    report_path = out_dir / "clips_manifest.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[ok] ok={report['summary']['ok']} missing_audio={report['summary']['missing_audio']} failed={report['summary']['failed']}")
    print(f"[ok] wrote {report_path}")


if __name__ == "__main__":
    main()
