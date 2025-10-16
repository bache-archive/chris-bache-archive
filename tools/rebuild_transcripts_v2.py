#!/usr/bin/env python3
"""
rebuild_transcripts_v2.py

Rebuild markdown transcripts from diarist .txt files using index.json metadata.

Key features
- Uses diarist speaker labels (more accurate attribution).
- Strips timestamps and Otter-style cruft.
- Optional normalization of common labels (Interviewer, Audience, etc).
- Emits YAML front matter with a deduped speakers list.
- Looks up title/date from index.json (fallback to slug).
- Writes to build/sources/transcripts/<basename>.md by default.

Usage examples
--------------
# Rebuild one transcript
python tools/rebuild_transcripts_v2.py --root . --only <slug> --normalize-labels --sync-speakers-yaml --verbose

# Rebuild all listed in index.json
python tools/rebuild_transcripts_v2.py --root . --normalize-labels --sync-speakers-yaml --verbose
"""

from __future__ import annotations
import argparse
import json
import os
import re
import sys
import hashlib
from pathlib import Path
from typing import Dict, List, Iterable, Tuple, Optional

# -------- Util helpers --------

def info(enabled: bool, msg: str) -> None:
    if enabled:
        print(f"[info] {msg}", flush=True)

def sha1_of_file(p: Path) -> str:
    h = hashlib.sha1()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def load_index(index_path: Path, verbose: bool=False) -> List[Dict]:
    if not index_path.exists():
        raise FileNotFoundError(f"index.json not found at: {index_path}")
    with index_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("index.json must be a top-level JSON array")
    info(verbose, f"Loaded index.json entries: {len(data)}")
    return data

def entries_by_basename(entries: List[Dict]) -> Dict[str, Dict]:
    m = {}
    for e in entries:
        tr = e.get("transcript", "")
        base = Path(tr).stem if tr else ""
        if base:
            m[base] = e
    return m

# -------- Parsing / cleaning --------

TIME_RE = re.compile(r"\b(?:\d{1,2}:)?\d{1,2}:\d{2}\b")  # 1:23:45 or 12:34
LEADING_TIME_RE = re.compile(r"^\s*(?:\d{1,2}:)?\d{1,2}:\d{2}\s*[-–]\s*")  # "00:10 - " etc.

def clean_line(line: str) -> str:
    # Remove inline timestamps like 01:23 or 1:02:03
    line = TIME_RE.sub("", line)
    line = LEADING_TIME_RE.sub("", line)
    # Collapse excessive spaces
    line = re.sub(r"\s+", " ", line).strip()
    return line

def is_speaker_line(line: str) -> bool:
    # Treat "Name:" at beginning of line as a speaker label
    # Avoid false positives: require some letters before colon
    return bool(re.match(r"^[^\s].{0,100}:\s", line))

def split_speaker_line(line: str) -> Tuple[str, str]:
    # Split on first colon
    parts = line.split(":", 1)
    spk = parts[0].strip()
    text = parts[1].strip() if len(parts) > 1 else ""
    return spk, text

def normalize_label(label: str) -> str:
    # Basic normalizations; expand as needed
    L = label.strip()
    L = re.sub(r"\s+", " ", L)

    # Common aliases
    aliases = {
        "host": "Interviewer",
        "moderator": "Interviewer",
        "interviewer": "Interviewer",
        "audience member": "Audience",
        "audience": "Audience",
        "unknown": "Unknown",
        "unknown speaker": "Unknown",
        "speaker": "Unknown",
        "speaker 1": "Speaker 1",
        "speaker 2": "Speaker 2",
        "speaker 3": "Speaker 3",
        "dr. chris bache": "Chris Bache",
        "christopher bache": "Chris Bache",
        "chris": "Chris Bache",
        "chris bache": "Chris Bache",
    }

    key = L.lower()
    return aliases.get(key, L)

def gather_blocks(diar_lines: Iterable[str], do_norm: bool) -> List[Tuple[str, str]]:
    """
    Return a list of (speaker, text) blocks. Coalesce consecutive lines for same speaker.
    """
    blocks: List[Tuple[str, str]] = []
    cur_spk: Optional[str] = None
    cur_buf: List[str] = []

    def flush():
        nonlocal cur_spk, cur_buf
        if cur_spk is not None and cur_buf:
            text = " ".join(cur_buf).strip()
            if text:
                blocks.append((cur_spk, text))
        cur_spk, cur_buf = None, []

    for raw in diar_lines:
        # Skip HTML comments or provenance lines
        if raw.strip().startswith("<!--") and raw.strip().endswith("-->"):
            continue

        line = clean_line(raw.rstrip("\n"))
        if not line:
            continue

        if is_speaker_line(line):
            spk, text = split_speaker_line(line)
            spk = normalize_label(spk) if do_norm else spk.strip()
            # New speaker: flush previous
            flush()
            cur_spk = spk
            if text:
                cur_buf.append(text)
        else:
            # Continuation line
            if cur_spk is None:
                # If no current speaker yet, assume Unknown (rare in Otter exports)
                cur_spk = "Unknown" if not do_norm else normalize_label("Unknown")
            cur_buf.append(line)

    flush()
    return blocks

def unique_ordered(seq: Iterable[str]) -> List[str]:
    seen = set()
    out = []
    for s in seq:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out

# -------- Markdown emission --------

def to_markdown(
    base: str,
    blocks: List[Tuple[str, str]],
    meta: Dict,
    diar_sha1: str,
    sync_speakers_yaml: bool,
) -> str:
    # Title/date from index.json if present
    title = meta.get("archival_title") or base
    date = meta.get("published", "") or ""

    body_speakers = unique_ordered([b[0] for b in blocks])
    # Front matter speakers list
    speakers_yaml = body_speakers if sync_speakers_yaml else meta.get("speakers", body_speakers)

    # YAML front matter
    lines = []
    lines.append("---")
    lines.append(f'title: "{title}"')
    if date:
        lines.append(f"date: {date}")
    if speakers_yaml:
        # quote speakers to be safe
        quoted = [f'"{s}"' for s in speakers_yaml]
        lines.append(f"speakers: [{', '.join(quoted)}]")
    # record provenance in YAML to avoid being parsed in body
    lines.append(f"diarist_sha1: {diar_sha1}")
    lines.append(f"source_basename: {base}")
    lines.append("---")
    lines.append("")  # spacer

    # Body: "Speaker: text"
    for spk, text in blocks:
        lines.append(f"{spk}: {text}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"

# -------- Main pipeline --------

def rebuild_one(
    root: Path,
    base: str,
    index_map: Dict[str, Dict],
    out_dir: Path,
    normalize_labels: bool,
    sync_speakers_yaml: bool,
    verbose: bool,
) -> Tuple[bool, Optional[Path]]:
    diar = root / f"sources/diarist/{base}.txt"
    if not diar.exists():
        info(verbose, f"{base}: diarist not found: {diar}")
        return False, None

    meta = index_map.get(base, {})
    if not meta:
        info(verbose, f"{base}: not found in index.json (will still build with fallback title)")
    with diar.open("r", encoding="utf-8") as f:
        diar_lines = f.readlines()

    info(verbose, f"{base}: diarist chars={sum(len(x) for x in diar_lines):,}")

    blocks = gather_blocks(diar_lines, do_norm=normalize_labels)
    if not blocks:
        info(verbose, f"{base}: no blocks parsed")
        return False, None

    diar_sha1 = sha1_of_file(diar)
    md = to_markdown(
        base=base,
        blocks=blocks,
        meta=meta,
        diar_sha1=diar_sha1,
        sync_speakers_yaml=sync_speakers_yaml,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{base}.md"
    out_path.write_text(md, encoding="utf-8")
    return True, out_path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", help="Repo root (default: current directory)")
    ap.add_argument("--only", action="append", default=[], help="Limit to one or more basenames (no extension). Can be provided multiple times.")
    ap.add_argument("--normalize-labels", action="store_true", help="Normalize common labels (Interviewer, Audience, Unknown, Chris Bache, etc.)")
    ap.add_argument("--sync-speakers-yaml", action="store_true", help="Populate speakers: in YAML from body labels.")
    ap.add_argument("--verbose", action="store_true", help="Verbose logging")
    ap.add_argument("--out-dir", default="build/sources/transcripts", help="Output directory for markdown transcripts.")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    out_dir = (root / args.out_dir).resolve()
    index_path = root / "index.json"

    entries = load_index(index_path, verbose=args.verbose)
    ix = entries_by_basename(entries)

    # Determine worklist
    work: List[str]
    if args.only:
        work = []
        for item in args.only:
            # allow comma-separated list in one flag for convenience
            work.extend([w.strip() for w in item.split(",") if w.strip()])
    else:
        work = list(ix.keys())

    if not work:
        print("[info] No work items found (check --only or index.json).", file=sys.stderr)
        sys.exit(1)

    ok = 0
    fail = 0
    for i, base in enumerate(work, 1):
        info(args.verbose, f"{base}: sending ({i}/{len(work)})")
        success, outp = rebuild_one(
            root=root,
            base=base,
            index_map=ix,
            out_dir=out_dir,
            normalize_labels=args.normalize_labels,
            sync_speakers_yaml=args.sync_speakers_yaml,
            verbose=args.verbose,
        )
        if success:
            ok += 1
            if args.verbose:
                print(f"[ok] {base} -> {outp}")
        else:
            fail += 1
            print(f"[fail] {base}", file=sys.stderr)

    print(f"[done] built={ok} failed={fail}")

if __name__ == "__main__":
    main()
