#!/usr/bin/env python3
"""
tools/transcripts/rebuild_transcripts_v2.py

Rebuild markdown transcripts from diarist .txt files using index metadata.

What’s new in this version
- --index PATH                Use a non-canonical index (e.g., patch preview merged index)
- --only-from-patch PATH      Restrict worklist to items listed in a patch JSON
- --out-dir DIR               Write output to a sandbox directory (e.g., build/patch-preview/.../transcripts)
- Robust index formats        Supports a top-level list OR {"items":[...]}
- Flexible ID resolution      Uses transcript basename, else id/slug/youtube_id
- Optional stubs              --allow-stubs will emit a minimal page if diarist .txt is missing
- Safer metadata              Tries several common field names for title/date

Usage examples
--------------
# Build only items from a patch into a preview directory
python tools/transcripts/rebuild_transcripts_v2.py \
  --root . \
  --index patches/2025-10-31-bache-youtube/outputs/index.merged.json \
  --only-from-patch patches/2025-10-31-bache-youtube/work/index.patch.json \
  --out-dir build/patch-preview/2025-10-31-bache-youtube/transcripts \
  --normalize-labels --sync-speakers-yaml --verbose

# Build a specific basename (matches sources/diarist/<basename>.txt)
python tools/transcripts/rebuild_transcripts_v2.py --root . --only ZeGh055Porc --verbose
"""

from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

# ─────────────────────────────── Paths ───────────────────────────────

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent  # repo root (…/tools/.. → /)


# ─────────────────────────────── Utils ───────────────────────────────

def info(enabled: bool, msg: str) -> None:
    if enabled:
        print(f"[INFO] {msg}", flush=True)

def warn(msg: str) -> None:
    print(f"[WARN] {msg}", flush=True)

def sha1_of_file(p: Path) -> str:
    h = hashlib.sha1()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def to_repo_rel(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(ROOT))
    except Exception:
        return str(p.resolve())


# ───────────────────── Index / Patch loading ─────────────────────

def load_index(index_path: Path, verbose: bool=False) -> List[Dict]:
    if not index_path.exists():
        raise FileNotFoundError(f"index not found: {index_path}")
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValueError(f"failed to parse index at {index_path}: {e}")
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError("index must be a list or {'items':[...]} at the top level")
    info(verbose, f"Loaded index items: {len(items)} from {to_repo_rel(index_path)}")
    return items

PATCH_KEYS = ("id", "slug", "youtube_id", "transcript")

def extract_ids_from_patch(patch_path: Path, verbose: bool=False) -> set[str]:
    ids: set[str] = set()
    if not patch_path.exists():
        warn(f"patch json not found: {patch_path}")
        return ids
    try:
        data = json.loads(patch_path.read_text(encoding="utf-8"))
    except Exception as e:
        warn(f"failed to parse patch: {patch_path} ({e})")
        return ids
    items = data if isinstance(data, list) else (data.get("items") or data.get("entries") or [])
    for it in items or []:
        # Prefer explicit identifiers
        for k in ("id", "slug", "youtube_id"):
            v = (it.get(k) or "").strip()
            if v:
                ids.add(v)
        # Allow transcript-derived basename fallback
        tr = (it.get("transcript") or "").strip()
        m = re.search(r"([^/]+)\.md$", tr)
        if m:
            ids.add(m.group(1))
    info(verbose, f"Filtered IDs from patch: {len(ids)} ({to_repo_rel(patch_path)})")
    return ids


# ───────────────────── Entry → basename resolution ─────────────────────

def basename_for_item(it: Dict) -> Optional[str]:
    """
    Determine the working 'basename' used for diarist and transcript files.
    Priority:
      1) transcript path stem (e.g., sources/transcripts/<stem>.md → <stem>)
      2) id
      3) slug
      4) youtube_id
    """
    tr = (it.get("transcript") or "").strip()
    if tr:
        m = re.search(r"([^/]+)\.md$", tr)
        if m:
            return m.group(1)
    for k in ("id", "slug", "youtube_id"):
        v = (it.get(k) or "").strip()
        if v:
            return v
    return None

def entries_by_basename(items: List[Dict]) -> Dict[str, Dict]:
    out: Dict[str, Dict] = {}
    for it in items:
        base = basename_for_item(it)
        if base:
            out[base] = it
    return out


# ───────────────────── Text parsing / cleaning ─────────────────────

TIME_RE = re.compile(r"\b(?:\d{1,2}:)?\d{1,2}:\d{2}\b")              # 1:23:45 or 12:34
LEADING_TIME_RE = re.compile(r"^\s*(?:\d{1,2}:)?\d{1,2}:\d{2}\s*[-–]\s*")  # "00:10 - "

def clean_line(line: str) -> str:
    line = TIME_RE.sub("", line)
    line = LEADING_TIME_RE.sub("", line)
    line = re.sub(r"\s+", " ", line).strip()
    return line

def is_speaker_line(line: str) -> bool:
    return bool(re.match(r"^[^\s].{0,100}:\s", line))

def split_speaker_line(line: str) -> Tuple[str, str]:
    parts = line.split(":", 1)
    spk = parts[0].strip()
    text = parts[1].strip() if len(parts) > 1 else ""
    return spk, text

def normalize_label(label: str) -> str:
    L = re.sub(r"\s+", " ", label.strip())
    aliases = {
        "host": "Interviewer",
        "moderator": "Interviewer",
        "interviewer": "Interviewer",
        "audience": "Audience",
        "audience member": "Audience",
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
    return aliases.get(L.lower(), L)

def gather_blocks(diar_lines: Iterable[str], do_norm: bool) -> List[Tuple[str, str]]:
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
        if raw.strip().startswith("<!--") and raw.strip().endswith("-->"):
            continue
        line = clean_line(raw.rstrip("\n"))
        if not line:
            continue
        if is_speaker_line(line):
            spk, text = split_speaker_line(line)
            spk = normalize_label(spk) if do_norm else spk.strip()
            flush()
            cur_spk = spk
            if text:
                cur_buf.append(text)
        else:
            if cur_spk is None:
                cur_spk = normalize_label("Unknown") if do_norm else "Unknown"
            cur_buf.append(line)
    flush()
    return blocks

def unique_ordered(seq: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for s in seq:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


# ───────────────────── Markdown emission ─────────────────────

def pick_title(meta: Dict, base: str) -> str:
    for k in ("archival_title", "title", "name"):
        v = (meta.get(k) or "").strip()
        if v:
            return v
    return base

def pick_date(meta: Dict) -> str:
    for k in ("published_at", "published", "date", "recorded_at"):
        v = (meta.get(k) or "").strip()
        if v:
            return v
    return ""

def to_markdown(
    base: str,
    blocks: List[Tuple[str, str]],
    meta: Dict,
    diar_sha1: Optional[str],
    sync_speakers_yaml: bool,
) -> str:
    title = pick_title(meta, base)
    date = pick_date(meta)

    body_speakers = unique_ordered([b[0] for b in blocks])
    speakers_yaml = body_speakers if sync_speakers_yaml else meta.get("speakers", body_speakers)

    lines: List[str] = []
    lines.append("---")
    lines.append(f'title: "{title}"')
    if date:
        lines.append(f"date: {date}")
    if speakers_yaml:
        quoted = [f'"{s}"' for s in speakers_yaml]
        lines.append(f"speakers: [{', '.join(quoted)}]")
    if diar_sha1:
        lines.append(f"diarist_sha1: {diar_sha1}")
    lines.append(f"source_basename: {base}")
    lines.append("---\n")

    for spk, text in blocks:
        lines.append(f"{spk}: {text}\n")

    return "".join(lines).rstrip() + "\n"


# ───────────────────── Core build routines ─────────────────────

def build_from_diarist(
    root: Path,
    base: str,
    meta: Dict,
    out_path: Path,
    normalize_labels: bool,
    sync_speakers_yaml: bool,
    verbose: bool,
) -> bool:
    diar = root / "sources" / "diarist" / f"{base}.txt"
    if not diar.exists():
        info(verbose, f"{base}: diarist not found: {to_repo_rel(diar)}")
        return False

    diar_lines = diar.read_text(encoding="utf-8").splitlines(True)
    info(verbose, f"{base}: diarist chars={sum(len(x) for x in diar_lines):,}")

    blocks = gather_blocks(diar_lines, do_norm=normalize_labels)
    if not blocks:
        info(verbose, f"{base}: no speaker blocks parsed")
        return False

    diar_sha1 = sha1_of_file(diar)
    md = to_markdown(
        base=base,
        blocks=blocks,
        meta=meta,
        diar_sha1=diar_sha1,
        sync_speakers_yaml=sync_speakers_yaml,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    return True

def build_stub(
    base: str,
    meta: Dict,
    out_path: Path,
    note: str = "No diarist file available at preview time.",
) -> None:
    title = pick_title(meta, base)
    date = pick_date(meta)
    lines = [
        "---",
        f'title: "{title}"',
    ]
    if date:
        lines.append(f"date: {date}")
    lines += [
        f"source_basename: {base}",
        "speakers: []",
        "---",
        "",
        f"> {note}",
        "",
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


# ─────────────────────────────── Main ───────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Rebuild markdown transcripts from diarist .txt files.")
    ap.add_argument("--root", default=".", help="Repo root (default: current directory)")
    ap.add_argument("--index", default=str(ROOT / "index.json"), help="Path to index JSON (supports list or {'items':[...]}).")
    ap.add_argument("--only", action="append", default=[], help="Limit to one or more basenames (no extension). Can be given multiple times.")
    ap.add_argument("--only-from-patch", help="Restrict worklist to items listed in a patch JSON (reads id/slug/youtube_id/transcript).")
    ap.add_argument("--out-dir", default=str(ROOT / "build" / "sources" / "transcripts"), help="Output directory for markdown transcripts.")
    ap.add_argument("--normalize-labels", action="store_true", help="Normalize common labels (Interviewer, Audience, Unknown, Chris Bache, etc.)")
    ap.add_argument("--sync-speakers-yaml", action="store_true", help="Populate speakers: in YAML from deduped body labels.")
    ap.add_argument("--allow-stubs", action="store_true", help="If diarist .txt missing, emit a minimal stub Markdown instead of failing.")
    ap.add_argument("--dry-run", action="store_true", help="Print planned outputs without writing files.")
    ap.add_argument("--verbose", action="store_true", help="Verbose logging.")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    index_path = Path(args.index).resolve()
    out_dir = Path(args.out_dir).resolve()

    items = load_index(index_path, verbose=args.verbose)
    ix_by_base = entries_by_basename(items)

    # Build worklist
    selected_ids: Optional[set[str]] = None
    if args.only_from_patch:
        selected_ids = extract_ids_from_patch(Path(args.only_from_patch), verbose=args.verbose)

    # Start with explicit --only (comma-friendly)
    explicits: List[str] = []
    for x in args.only:
        explicits += [w.strip() for w in x.split(",") if w.strip()]

    if explicits:
        work_bases = explicits
    elif selected_ids:
        # Map selected IDs to basenames present in index
        # If an ID equals an existing basename, use it directly; else try to find by id/slug/youtube_id match
        rev: Dict[str, str] = {}  # any(id/slug/youtube_id) -> base
        for base, it in ix_by_base.items():
            for k in ("id", "slug", "youtube_id"):
                v = (it.get(k) or "").strip()
                if v:
                    rev[v] = base
            rev[base] = base  # allow direct basename match
        tmp: List[str] = []
        for sid in selected_ids:
            b = rev.get(sid)
            if b:
                tmp.append(b)
        work_bases = sorted(set(tmp))
    else:
        work_bases = sorted(ix_by_base.keys())

    if not work_bases:
        warn("No work items found (check --only / --only-from-patch / index).")
        return 1

    info(args.verbose, f"Total index: {len(ix_by_base)} | Selected: {len(work_bases)} | Out: {to_repo_rel(out_dir)}")

    built = 0
    failed = 0
    for i, base in enumerate(work_bases, 1):
        it = ix_by_base.get(base, {})
        out_path = out_dir / f"{base}.md"
        info(args.verbose, f"[{i}/{len(work_bases)}] {base}")

        if args.dry_run:
            print(f"[DRY] would write {to_repo_rel(out_path)}")
            continue

        ok = build_from_diarist(
            root=root,
            base=base,
            meta=it,
            out_path=out_path,
            normalize_labels=args.normalize_labels,
            sync_speakers_yaml=args.sync_speakers_yaml,
            verbose=args.verbose,
        )
        if ok:
            built += 1
        else:
            if args.allow_stubs:
                build_stub(base, it, out_path)
                info(args.verbose, f"{base}: wrote stub → {to_repo_rel(out_path)}")
                built += 1
            else:
                failed += 1
                warn(f"{base}: missing diarist or parse failure")

    print(f"[DONE] built={built} failed={failed} out_dir={to_repo_rel(out_dir)}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())