#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diarize a talk: ASR (WhisperX) + diarization (pyannote) → SRT + TXT (+ JSON)

Outputs in --out with consistent basenames:
  <basename>.srt   # timestamped, speaker-labeled segments
  <basename>.txt   # clean text with speaker labels, no timestamps
  <basename>.json  # rich metadata (segments, words, speakers)
Also appends/creates: diarist_manifest.csv

Heuristics & priorities:
- Reproducible, deterministic batching
- Robust to API/auth gaps (falls back to single-speaker if diarization fails)
- Reasonable SRT chunking (~10–20s / ~25–35 words per cue)
- Clean, stable filenames aligned to archive slugs
- Optional vocabulary priming and post-ASR lexicon normalization

Requirements (pip):
  pip install whisperx pyannote.audio torch torchaudio numpy pandas tqdm pyyaml

pyannote needs a HuggingFace token:
  export PYANNOTE_TOKEN=<hf_token>
  # or pass --hf_token

Example:
  python tools/diarist/diarize_talk.py \
    --input downloads/audio/2009-03-07-the-individual-and-matrix-consciousness-pt-1.mp3 \
    --out build/patch-preview/2025-11-01-bache-youtube/diarist/ \
    --basename 2009-03-07-the-individual-and-matrix-consciousness-pt-1 \
    --whisper-model large-v3 \
    --language en \
    --hf_token "$PYANNOTE_TOKEN" \
    --initial-prompt-file data/diarist/initial_prompt.txt \
    --lexicon data/diarist/lexicon.yml \
    --max-words 32 \
    --max-duration 16

Author: Bache Archive Project
License: CC0 on generated outputs; script under project’s repo license.
"""
import os
import sys
import re
import json
import csv
import time
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import torch
from tqdm import tqdm

import whisperx  # type: ignore
from pyannote.audio import Pipeline  # type: ignore

try:
    import yaml
except ImportError:
    yaml = None


# ---------------------------
# Utilities
# ---------------------------

def hhmmss_ms(seconds: float) -> str:
    ms = int(round((seconds - int(seconds)) * 1000))
    s = int(seconds) % 60
    m = (int(seconds) // 60) % 60
    h = (int(seconds) // 3600)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def safe_mkdir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def load_hf_token(cli_token: Optional[str]) -> Optional[str]:
    return cli_token or os.environ.get("PYANNOTE_TOKEN") or os.environ.get("HF_TOKEN")


def majority_speaker_for_span(spans, start, end, default="SPEAKER_00"):
    best_label, best_overlap = default, 0.0
    for s, e, spk in spans:
        overlap = max(0.0, min(end, e) - max(start, s))
        if overlap > best_overlap:
            best_overlap, best_label = overlap, spk
    return best_label


def normalize_speaker_name(raw: str, mapping: Dict[str, str]) -> str:
    return mapping.get(raw, raw)


def load_lines(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    lines = [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return ", ".join(lines) if lines else None


def load_lexicon(path: Optional[str]) -> Dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    if p.suffix in [".yml", ".yaml"] and yaml:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return json.loads(p.read_text(encoding="utf-8"))


def preserve_case(src: str, tgt: str) -> str:
    if src.isupper():
        return tgt.upper()
    if src[:1].isupper() and src[1:].islower():
        return tgt[:1].upper() + tgt[1:]
    return tgt


def apply_lexicon(text: str, lex: Dict[str, Any]) -> str:
    if not lex:
        return text
    pairs = []
    for canonical, variants in lex.items():
        if isinstance(variants, str):
            variants = [variants]
        for v in variants:
            pairs.append((v, canonical))
    pairs.sort(key=lambda kv: len(kv[0]), reverse=True)
    for v, c in pairs:
        pat = re.compile(rf"(?<!\w){re.escape(v)}(?!\w)", re.IGNORECASE)
        text = pat.sub(lambda m: preserve_case(m.group(0), c), text)
    return text


def chunk_words_to_segments(words, max_words=35, max_duration=18.0):
    segments, cur, seg_start = [], [], None
    for w in words:
        if w.get("start") is None or w.get("end") is None:
            continue
        if seg_start is None:
            seg_start = float(w["start"])
        cur.append(w)
        duration = float(w["end"]) - seg_start
        if len(cur) >= max_words or duration >= max_duration:
            text = " ".join(x["word"].strip() for x in cur).strip()
            segments.append({"start": seg_start, "end": float(w["end"]), "text": text, "words": cur.copy()})
            cur, seg_start = [], None
    if cur:
        text = " ".join(x["word"].strip() for x in cur).strip()
        segments.append({"start": float(cur[0]["start"]), "end": float(cur[-1]["end"]), "text": text, "words": cur.copy()})
    for seg in segments:
        seg["text"] = re.sub(r"\s{2,}", " ", seg["text"]).strip()
    return segments


def write_srt(path: Path, diarized_segments: List[Dict[str, Any]]):
    with path.open("w", encoding="utf-8") as f:
        for i, seg in enumerate(diarized_segments, 1):
            f.write(f"{i}\n{hhmmss_ms(seg['start'])} --> {hhmmss_ms(seg['end'])}\n")
            f.write(f"{seg.get('speaker', 'SPEAKER_00')}: {seg.get('text', '').strip()}\n\n")


def write_txt(path: Path, diarized_segments: List[Dict[str, Any]]):
    with path.open("w", encoding="utf-8") as f:
        for seg in diarized_segments:
            speaker, text = seg.get("speaker", "SPEAKER_00"), seg.get("text", "").strip()
            if text:
                f.write(f"{speaker}: {text}\n")


def write_json(path: Path, payload: Dict[str, Any]):
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def update_manifest(manifest_path: Path, row: Dict[str, Any]):
    header = ["basename", "input", "duration_sec", "language", "whisper_model", "device",
              "num_segments", "num_speakers", "srt", "txt", "json", "created_at"]
    file_exists = manifest_path.exists()
    with manifest_path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


# ---------------------------
# Core pipeline
# ---------------------------

def run_asr_align_whisperx(
    audio_path: Path,
    language: Optional[str],
    model_name: str,
    device: str,
    compute_type: str = "float16",
    batch_size: int = 16,
    initial_prompt: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run WhisperX ASR + alignment; return dict with:
      {
        "language": "en",
        "segments": [...aligned segments...],
        "words": [...aligned words...],
        "duration": float_seconds
      }
    """
    # CPU-safe default
    if device == "cpu" and compute_type.lower() in {"float16", "float32"}:
        compute_type = "int8"

    print(f"[whisperx] Loading model={model_name} device={device} compute_type={compute_type}")
    asr_opts = {"word_timestamps": True}
    if initial_prompt:
        asr_opts["initial_prompt"] = initial_prompt

    model = whisperx.load_model(model_name, device, compute_type=compute_type, asr_options=asr_opts)
    audio = whisperx.load_audio(str(audio_path))

    print("[whisperx] Transcribing…")
    result = model.transcribe(audio, language=language, batch_size=batch_size)
    detected_language = result.get("language", language) or "en"

    print("[whisperx] Loading alignment model…")
    align_model = metadata = None
    # Try newest API first (language_code), then older (language), then fallback (model_name)
    tried = []
    try:
        align_model, metadata = whisperx.load_align_model(language_code=detected_language, device=device)
    except TypeError as e1:
        tried.append(f"language_code ({e1})")
        try:
            align_model, metadata = whisperx.load_align_model(language=detected_language, device=device)
        except TypeError as e2:
            tried.append(f"language ({e2})")
            # Best-effort final fallback — common pattern used in some releases
            try:
                align_model, metadata = whisperx.load_align_model(
                    model_name=f"wav2vec2-{detected_language}", device=device
                )
            except TypeError as e3:
                tried.append(f"model_name ({e3})")
                raise RuntimeError(f"whisperx.load_align_model API mismatch. Tried: {', '.join(tried)}")

    aligned = whisperx.align(result["segments"], align_model, metadata, audio, device, return_char_alignments=False)

    # Flatten word list
    words: List[Dict[str, Any]] = []
    for seg in aligned.get("segments", []):
        for w in seg.get("words", []):
            if w.get("start") is not None and w.get("end") is not None and w.get("word"):
                words.append({"start": float(w["start"]), "end": float(w["end"]), "word": w["word"]})

    duration = float(result.get("duration", 0.0))
    print(f"[whisperx] Done. Duration ~{duration:.2f}s, segments={len(aligned.get('segments', []))}, words={len(words)}")
    return {"language": detected_language, "segments": aligned.get("segments", []), "words": words, "duration": duration}


def run_diarization_pyannote(audio_path: Path, hf_token: Optional[str], num_speakers: Optional[int] = None):
    token = load_hf_token(hf_token)
    if not token:
        raise RuntimeError("No HuggingFace token. Set PYANNOTE_TOKEN or pass --hf_token.")
    print("[pyannote] Loading diarization pipeline…")
    pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", use_auth_token=token)
    params = {"num_speakers": num_speakers} if num_speakers else {}
    diarization = pipeline(str(audio_path), **params)
    spans = [(float(turn.start), float(turn.end), str(speaker)) for turn, _, speaker in diarization.itertracks(yield_label=True)]
    spans.sort(key=lambda x: x[0])
    return spans


def merge_words_with_speakers(words, speaker_spans):
    if not speaker_spans:
        for w in words:
            w["speaker"] = "SPEAKER_00"
        return words
    for w in words:
        w["speaker"] = majority_speaker_for_span(speaker_spans, float(w["start"]), float(w["end"]), "SPEAKER_00")
    return words


def build_diarized_segments(words_with_speakers, max_words=35, max_duration=18.0):
    raw_segments = chunk_words_to_segments(words_with_speakers, max_words, max_duration)
    diarized = []
    for seg in raw_segments:
        counts = {}
        for w in seg["words"]:
            spk = w.get("speaker", "SPEAKER_00")
            counts[spk] = counts.get(spk, 0) + (w.get("end", 0) - w.get("start", 0))
        speaker = max(counts, key=counts.get) if counts else "SPEAKER_00"
        diarized.append({**seg, "speaker": speaker})
    return diarized


# ---------------------------
# Main
# ---------------------------

def main():
    ap = argparse.ArgumentParser(description="Diarize talk → SRT + TXT (+ JSON)")
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--basename", default=None)
    ap.add_argument("--language", default=None)
    ap.add_argument("--whisper-model", default="large-v3")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--compute-type", default="float16")
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--hf_token", default=None)
    ap.add_argument("--num-speakers", type=int, default=0)
    ap.add_argument("--map-speaker", action="append", default=[])
    ap.add_argument("--max-words", type=int, default=35)
    ap.add_argument("--max-duration", type=float, default=18.0)
    ap.add_argument("--initial-prompt-file", default=None)
    ap.add_argument("--lexicon", default=None)
    args = ap.parse_args()

    audio_path = Path(args.input).expanduser().resolve()
    if not audio_path.exists():
        sys.exit(f"ERROR: Input not found: {audio_path}")

    out_dir = Path(args.out).expanduser().resolve()
    safe_mkdir(out_dir)
    basename = args.basename or audio_path.stem
    srt_path, txt_path, json_path = out_dir / f"{basename}.srt", out_dir / f"{basename}.txt", out_dir / f"{basename}.json"
    manifest_path = out_dir / "diarist_manifest.csv"

    initial_prompt = load_lines(args.initial_prompt_file)
    asr = run_asr_align_whisperx(audio_path, args.language, args.whisper_model, args.device,
                                 args.compute_type, args.batch_size, initial_prompt)

    diar_spans, diar_failed = [], False
    try:
        diar_spans = run_diarization_pyannote(audio_path, args.hf_token,
                                              num_speakers=(args.num_speakers or None))
    except Exception as e:
        diar_failed = True
        print(f"[pyannote] Diarization failed: {e}. Fallback to single-speaker.", file=sys.stderr)

    words = merge_words_with_speakers(asr["words"], diar_spans)
    diarized_segments = build_diarized_segments(words, args.max_words, args.max_duration)

    mapping = {}
    for kv in args.map_speaker:
        if "=" in kv:
            k, v = kv.split("=", 1)
            mapping[k.strip()] = v.strip()
    if mapping:
        for seg in diarized_segments:
            seg["speaker"] = normalize_speaker_name(seg["speaker"], mapping)

    lex = load_lexicon(args.lexicon)
    if lex:
        for seg in diarized_segments:
            seg["text"] = apply_lexicon(seg["text"], lex)

    write_srt(srt_path, diarized_segments)
    write_txt(txt_path, diarized_segments)

    meta_payload = {
        "input": str(audio_path),
        "basename": basename,
        "duration_sec": asr.get("duration"),
        "language": asr.get("language"),
        "whisper_model": args.whisper_model,
        "device": args.device,
        "compute_type": args.compute_type,
        "diarization_failed": diar_failed,
        "num_speakers_detected": len(set(s["speaker"] for s in diarized_segments)) if diarized_segments else (1 if diar_failed else 0),
        "segments": diarized_segments,
    }
    write_json(json_path, meta_payload)

    created_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    update_manifest(manifest_path, {
        "basename": basename,
        "input": str(audio_path),
        "duration_sec": asr.get("duration"),
        "language": asr.get("language"),
        "whisper_model": args.whisper_model,
        "device": args.device,
        "num_segments": len(diarized_segments),
        "num_speakers": meta_payload["num_speakers_detected"],
        "srt": str(srt_path),
        "txt": str(txt_path),
        "json": str(json_path),
        "created_at": created_at
    })

    print(f"\n[done]\nSRT : {srt_path}\nTXT : {txt_path}\nJSON: {json_path}\nManifest updated: {manifest_path}")


if __name__ == "__main__":
    main()