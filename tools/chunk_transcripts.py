#!/usr/bin/env python3
"""
tools/chunk_transcripts.py

Create stable, citation-friendly chunks from cleaned Markdown transcripts.

• Reads:   index.json (existing schema; uses the `transcript` path if present and non-null)
• Writes:  build/chunks/bache-talks.chunks.jsonl  (one JSON object per chunk)
           reports/chunk_stats.json               (basic QA stats)

This version:
  - Silently SKIPS entries without a usable `transcript` path (e.g., book registries).
  - Fixes UTC timestamp deprecation by using timezone-aware datetimes.
  - Passes CLI args into stats writer (bugfix).

Chunking rules (defaults; configurable via CLI):
  - Target ~1000–1500 characters per chunk (default target=1200)
  - Character overlap between adjacent chunks (default overlap=100)
  - Prefer paragraph boundaries (split on blank lines); collapse whitespace
  - Preserve simple speaker labels already present in text (e.g., "CHRIS:")

Deterministic IDs:
  - talk_id: basename of transcript path without ".md"
  - chunk_index: 1-based, zero-padded "ckNNN"
  - chunk_id: "{talk_id}:{ckNNN}:{hash6}" where hash6 = first 6 of sha1(normalized_chunk_text)

Usage:
  python tools/chunk_transcripts.py \
      --index index.json \
      --out build/chunks/bache-talks.chunks.jsonl \
      --stats reports/chunk_stats.json \
      --target 1200 \
      --overlap 100
"""

import argparse
import hashlib
import io
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

# ----------------------------
# Markdown → plain-ish text
# ----------------------------

MD_CODEBLOCK_FENCE_RE = re.compile(r"(^```.*?$)(.*?)(^```$)", re.DOTALL | re.MULTILINE)
MD_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
MD_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
MD_BLOCKQUOTE_RE = re.compile(r"^\s{0,3}>\s?", re.MULTILINE)
MD_BULLET_RE = re.compile(r"^\s*([-*+]\s+|\d+\.\s+)", re.MULTILINE)
MD_LINK_RE = re.compile(r"$begin:math:display$([^$end:math:display$]+)\]$begin:math:text$[^)]+$end:math:text$")  # keep link text
MD_IMAGE_RE = re.compile(r"!$begin:math:display$([^$end:math:display$]*)\]$begin:math:text$[^)]+$end:math:text$")  # drop image, keep alt
MD_EMPH_RE = re.compile(r"(\*\*|__|\*|_)(.*?)\1", re.DOTALL)
MD_HTML_TAG_RE = re.compile(r"</?[^>]+>")  # drop basic HTML tags

def markdown_to_text(md: str) -> str:
    """
    Strip common Markdown constructs while preserving line breaks that cue paragraphs.
    We deliberately do NOT touch lines like 'CHRIS:' if they're already present.
    """
    # Remove fenced code blocks (replace with blank line to keep paragraph structure)
    md = MD_CODEBLOCK_FENCE_RE.sub("\n", md)
    # Inline code → plain text
    md = MD_INLINE_CODE_RE.sub(lambda m: m.group(1), md)
    # Strip heading markers, keep the heading text on the line
    md = MD_HEADING_RE.sub("", md)
    # Remove blockquote markers
    md = MD_BLOCKQUOTE_RE.sub("", md)
    # Remove list bullets/numbers, keep content
    md = MD_BULLET_RE.sub("", md)
    # Links: keep link text
    md = MD_LINK_RE.sub(lambda m: m.group(1), md)
    # Images: keep alt text (often empty), but generally drop
    md = MD_IMAGE_RE.sub(lambda m: (m.group(1) or ""), md)
    # Emphasis markers → plain
    md = MD_EMPH_RE.sub(lambda m: m.group(2), md)
    # Drop simple HTML tags
    md = MD_HTML_TAG_RE.sub("", md)

    # Normalize line endings
    md = md.replace("\r\n", "\n").replace("\r", "\n")

    # Collapse excessive blank lines (but keep paragraph breaks)
    lines = [ln.rstrip() for ln in md.split("\n")]
    normalized = []
    blank_run = 0
    for ln in lines:
        if ln.strip() == "":
            blank_run += 1
            if blank_run <= 1:
                normalized.append("")  # single blank line
        else:
            blank_run = 0
            normalized.append(ln)
    text = "\n".join(normalized).strip()

    # Collapse internal whitespace sequences (but keep newlines)
    text = re.sub(r"[ \t\f\v]+", " ", text)
    # Remove stray spaces around newlines
    text = re.sub(r" *\n *", "\n", text)

    return text


# ----------------------------
# Paragraph-first chunking
# ----------------------------

def split_paragraphs(text: str) -> list:
    """Split on blank lines into paragraphs; keep internal line breaks."""
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    return paragraphs

def _sha1_6(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:6]

def build_chunks_for_paragraphs(
    paragraphs: list,
    target: int = 1200,
    overlap: int = 100,
    hard_max: int = 1800,
) -> list:
    """
    Assemble chunks ≈ target characters using paragraph boundaries when possible.
    After finalizing a chunk, prepend the last `overlap` characters of the previous
    chunk to the next chunk (character-level overlap), ensuring context continuity.

    If a single paragraph exceeds hard_max, it will be split at sentence-ish boundaries.
    """
    chunks = []
    i = 0
    n = len(paragraphs)
    prev_tail = ""

    while i < n:
        buf = io.StringIO()
        # If we have prev tail, insert it once at the top of the new chunk
        if prev_tail:
            buf.write(prev_tail)
            if not prev_tail.endswith("\n"):
                buf.write("\n")

        # Add paragraphs while under target
        first_para_in_chunk = True
        while i < n:
            para = paragraphs[i]
            sep = "" if first_para_in_chunk or buf.getvalue().endswith("\n") else "\n\n"
            prospective = buf.getvalue() + sep + para
            if len(prospective) <= target or first_para_in_chunk:
                if not first_para_in_chunk and not buf.getvalue().endswith("\n"):
                    buf.write("\n\n")
                buf.write(para)
                i += 1
                first_para_in_chunk = False
                if len(buf.getvalue()) >= target:
                    break
            else:
                # Big paragraph edge-case
                if (len(buf.getvalue()) == 0 or buf.getvalue() == prev_tail + ("\n" if prev_tail else "")) and len(para) > hard_max:
                    # Sentence-ish split
                    split_pts = re.split(r"(?<=[.!?])\s+", para)
                    forced = []
                    cur = ""
                    for seg in split_pts:
                        prospective_seg = (cur + " " + seg) if cur else seg
                        if len(prospective_seg) <= target:
                            cur = prospective_seg
                        else:
                            if cur:
                                forced.append(cur)
                            cur = seg
                    if cur:
                        forced.append(cur)
                    # Write first piece
                    if forced:
                        if not first_para_in_chunk and not buf.getvalue().endswith("\n"):
                            buf.write("\n\n")
                        buf.write(forced[0])
                        remainder = " ".join(forced[1:]).strip()
                        if remainder:
                            paragraphs[i] = remainder
                        else:
                            i += 1
                    break
                else:
                    break

        chunk_text = buf.getvalue().strip()
        if not chunk_text:
            if i < n:
                chunk_text = paragraphs[i]
                i += 1
            else:
                break

        # Compute new tail for overlap (from this chunk)
        prev_tail = chunk_text[-overlap:] if len(chunk_text) > overlap else chunk_text
        chunks.append(chunk_text)

    return chunks


# ----------------------------
# Utilities
# ----------------------------

def estimate_tokens(text: str) -> int:
    # Crude: 1 token ≈ 4 characters (English, no CJK)
    return max(1, len(text) // 4)

def read_text_file(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def ensure_parent_dir(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)

def make_talk_id_from_transcript_path(transcript_path: str) -> str:
    return Path(transcript_path).name.replace(".md", "")

def zero_pad(n: int, width: int = 3) -> str:
    return str(n).zfill(width)

# ----------------------------
# Main pipeline
# ----------------------------

def process_entry(entry: dict, args) -> list:
    """
    Produce chunk JSON objects for a single talk entry from index.json.
    Skip entries with missing/null/empty `transcript`.
    """
    transcript_rel = entry.get("transcript")
    if not transcript_rel:
        return []  # skip gracefully (e.g., book registry without transcript)

    transcript_rel = transcript_rel.strip()
    if transcript_rel.lower() == "null":
        return []

    transcript_path = Path(transcript_rel)
    if not transcript_path.exists():
        # Try relative to current working directory
        alt = Path.cwd() / transcript_path
        if alt.exists():
            transcript_path = alt
        else:
            # Skip if file truly not found
            print(f"[SKIP] Transcript not found: {transcript_rel}", file=sys.stderr)
            return []

    archival_title = (entry.get("archival_title") or "").strip()
    channel = (entry.get("channel") or "").strip()
    source_type = (entry.get("source_type") or "").strip()
    published = (entry.get("published") or "").strip()

    talk_id = make_talk_id_from_transcript_path(transcript_rel)

    raw_md = read_text_file(transcript_path)
    text = markdown_to_text(raw_md)
    paragraphs = split_paragraphs(text)
    chunk_texts = build_chunks_for_paragraphs(
        paragraphs,
        target=args.target,
        overlap=args.overlap,
        hard_max=int(args.target * 1.5),
    )

    chunks = []
    for idx, chunk_text in enumerate(chunk_texts, start=1):  # 1-based
        ck = f"ck{zero_pad(idx)}"
        hash6 = _sha1_6(chunk_text)
        chunk_id = f"{talk_id}:{ck}:{hash6}"

        obj = {
            "chunk_id": chunk_id,
            "talk_id": talk_id,
            "archival_title": archival_title,
            "published": published,         # YYYY-MM-DD
            "channel": channel,
            "source_type": source_type,
            "transcript": transcript_rel,   # keep relative path for traceability
            "chunk_index": idx,             # 1-based
            "text": chunk_text,
            "char_len": len(chunk_text),
            "token_est": estimate_tokens(chunk_text),
            "hash": hash6,
        }
        chunks.append(obj)

    return chunks

def write_jsonl(rows: list, out_path: Path):
    ensure_parent_dir(out_path)
    with open(out_path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

def write_stats(all_chunks: list, stats_path: Path, args):
    ensure_parent_dir(stats_path)

    # Per-talk stats
    per_talk_counts = defaultdict(int)
    per_talk_chars = defaultdict(list)
    per_talk_tokens = defaultdict(list)

    for c in all_chunks:
        tid = c["talk_id"]
        per_talk_counts[tid] += 1
        per_talk_chars[tid].append(c["char_len"])
        per_talk_tokens[tid].append(c["token_est"])

    per_talk = {}
    for tid, count in per_talk_counts.items():
        chars = per_talk_chars[tid]
        toks = per_talk_tokens[tid]
        per_talk[tid] = {
            "chunks": count,
            "char_len_mean": round(mean(chars), 2),
            "char_len_min": min(chars),
            "char_len_max": max(chars),
            "token_est_mean": round(mean(toks), 2),
            "token_est_min": min(toks),
            "token_est_max": max(toks),
        }

    # Global stats
    all_char_lens = [c["char_len"] for c in all_chunks]
    all_token_ests = [c["token_est"] for c in all_chunks]

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_chunks": len(all_chunks),
        "char_len_mean": round(mean(all_char_lens), 2) if all_char_lens else 0,
        "char_len_min": min(all_char_lens) if all_char_lens else 0,
        "char_len_max": max(all_char_lens) if all_char_lens else 0,
        "token_est_mean": round(mean(all_token_ests), 2) if all_token_ests else 0,
        "token_est_min": min(all_token_ests) if all_token_ests else 0,
        "token_est_max": max(all_token_ests) if all_token_ests else 0,
        "per_talk": per_talk,
        "params": {
            "target_chars": args.target,
            "overlap_chars": args.overlap,
        },
    }

    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

def main():
    ap = argparse.ArgumentParser(description="Chunk Bache transcripts into citation-friendly segments.")
    ap.add_argument("--index", required=True, help="Path to index.json")
    ap.add_argument("--out", default="build/chunks/bache-talks.chunks.jsonl", help="Output JSONL path")
    ap.add_argument("--stats", default="reports/chunk_stats.json", help="Output stats JSON path")
    ap.add_argument("--target", type=int, default=1200, help="Target characters per chunk")
    ap.add_argument("--overlap", type=int, default=100, help="Character overlap between chunks")
    args = ap.parse_args()

    index_path = Path(args.index)
    if not index_path.exists():
        print(f"index.json not found: {index_path}", file=sys.stderr)
        sys.exit(1)

    with open(index_path, "r", encoding="utf-8") as f:
        try:
            entries = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Failed to parse {index_path}: {e}", file=sys.stderr)
            sys.exit(1)

    all_chunks = []
    skipped_no_transcript = 0
    skipped_missing_file = 0

    for entry in entries:
        transcript_rel = entry.get("transcript")
        if not transcript_rel or str(transcript_rel).strip().lower() == "null":
            skipped_no_transcript += 1
            continue

        # If the file doesn't exist, process_entry will print a [SKIP] and return [].
        before = len(all_chunks)
        chunks = process_entry(entry, args)
        all_chunks.extend(chunks)
        if len(all_chunks) == before:
            # No chunks added: likely missing file
            if not (Path(str(transcript_rel)).exists() or (Path.cwd() / str(transcript_rel)).exists()):
                skipped_missing_file += 1

    out_path = Path(args.out)
    write_jsonl(all_chunks, out_path)

    stats_path = Path(args.stats)
    write_stats(all_chunks, stats_path, args)

    print(f"Wrote {len(all_chunks)} chunks → {out_path}")
    print(f"Stats → {stats_path}")
    if skipped_no_transcript:
        print(f"Skipped entries without transcript: {skipped_no_transcript}")
    if skipped_missing_file:
        print(f"Skipped entries with missing transcript file: {skipped_missing_file}", file=sys.stderr)

if __name__ == "__main__":
    main()