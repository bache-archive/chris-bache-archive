#!/usr/bin/env python3
import argparse, glob, os, sys
from pathlib import Path
from textwrap import shorten

def find_first_yaml_block(lines):
    """Return (start_idx, end_idx) for the FIRST YAML block if file starts with ---; else (None, None)."""
    if not lines:
        return (None, None)
    if lines[0].strip() != '---':
        return (None, None)
    for i in range(1, len(lines)):
        if lines[i].strip() == '---':
            return (0, i)  # inclusive start/end
    return (None, None)  # unclosed

def collect_strays_after_first_block(lines, start_idx):
    """
    Starting at start_idx (first char after the first YAML block),
    skip & collect any extraneous YAML blocks, empty lines, or one-line HTML comments.
    Stop at the first 'real' content line.
    Returns (body_start_idx, removed_chunks) where removed_chunks is list[list[str]].
    """
    i = start_idx
    removed = []

    def is_empty(l): return l.strip() == ''
    def is_one_line_comment(l): 
        s = l.strip()
        return s.startswith('<!--') and s.endswith('-->')

    n = len(lines)
    while i < n:
        if is_empty(lines[i]) or is_one_line_comment(lines[i]):
            removed.append([lines[i]])
            i += 1
            continue

        if lines[i].strip() == '---':
            # treat as a stray YAML block, skip until closing ---
            j = i + 1
            while j < n and lines[j].strip() != '---':
                j += 1
            if j < n and lines[j].strip() == '---':
                removed.append(lines[i:j+1])  # include closing ---
                i = j + 1
                continue
            else:
                # Unclosed block; bail out and treat current line as content to be safe
                break

        # Otherwise we hit real content
        break

    return i, removed

def preview_removed(path, removed_chunks, show_full=False, max_lines=40):
    if not removed_chunks:
        return
    print(f"[plan] {path}: would strip {sum(len(c) for c in removed_chunks)} lines across {len(removed_chunks)} chunk(s)")
    print("------ stripped preview (prefix '-') ------")
    count = 0
    for chunk in removed_chunks:
        for l in chunk:
            count += 1
            if show_full or count <= max_lines:
                print("- " + l.rstrip("\n"))
    if not show_full and count > max_lines:
        print(f"... ({count - max_lines} more line(s) elided)")
    print("------------------------------------------")

def process_file(path, write=False, show_full=False):
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    start, end = find_first_yaml_block(lines)
    if start is None:
        # No YAML at top; nothing to do
        return False, []

    first_block = lines[start:end+1]
    after_first_idx = end + 1

    body_start, removed_chunks = collect_strays_after_first_block(lines, after_first_idx)
    if not removed_chunks:
        return False, []

    if write:
        new_lines = []
        new_lines.extend(first_block)
        # ensure exactly one blank line after YAML block if body doesn't start with one
        if body_start < len(lines) and lines[body_start].strip() != '':
            new_lines.append("\n")
        new_lines.extend(lines[body_start:])
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        return True, removed_chunks
    else:
        return None, removed_chunks  # None = dry-run change planned

def main():
    ap = argparse.ArgumentParser(description="Remove duplicate/stray YAML blocks & noise between front matter and body.")
    ap.add_argument("--glob", default="sources/transcripts/*.md", help="Glob of files to process")
    ap.add_argument("--limit", type=int, default=None, help="Limit number of files processed")
    ap.add_argument("--write", action="store_true", help="Actually write changes (otherwise preview only)")
    ap.add_argument("--show-full", action="store_true", help="Show full removed text in preview")
    args = ap.parse_args()

    files = sorted(glob.glob(args.glob))
    if args.limit:
        files = files[:args.limit]

    planned = 0
    changed = 0
    for path in files:
        result, removed = process_file(path, write=args.write, show_full=args.show_full)
        if result is None and removed:  # dry-run
            planned += 1
            preview_removed(path, removed, show_full=args.show_full)
        elif result is True:
            changed += 1
            print(f"[fixed] {path} (removed {sum(len(c) for c in removed)} line(s))")

    if not args.write:
        if planned == 0:
            print("Dry-run: no files would change.")
        else:
            print(f"Dry-run: {planned} file(s) would change. Re-run with --write to apply.")

if __name__ == "__main__":
    main()
