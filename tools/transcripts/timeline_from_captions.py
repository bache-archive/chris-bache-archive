#!/usr/bin/env python3
"""
Build a word-level timeline TSV from a WebVTT captions file.

STDOUT TSV columns (no header):
  word <TAB> start_sec <TAB> end_sec

Rules:
- Parse VTT cues (start --> end, then 1+ lines of text).
- Remove bracketed stage directions like [Applause].
- Strip simple HTML tags.
- Tokenize words as [A-Za-z0-9]+'?[A-Za-z0-9]+ (keeps intra-word apostrophes).
- Distribute each cue's duration evenly over its tokens.
- If a cue has no tokens, it's skipped.

Usage:
  python3 tools/timeline_from_captions.py sources/captions/<talk_id>.vtt > tmp/words/<talk_id>.captions.tsv
"""
import sys, re

TIME_RE = re.compile(r'(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2}\.\d{3})')
WORD_RE = re.compile(r"[A-Za-z0-9]+'?[A-Za-z0-9]+")
STAGE_RE = re.compile(r'^\s*\[[^\]]+\]\s*$')  # [Applause], [Music], etc.
TAG_RE = re.compile(r"</?[^>]+>")             # simple HTML tag stripper

def parse_time(s):
    m = TIME_RE.search(s)
    if not m: return None
    h = int(m.group("h")); m_ = int(m.group("m")); s_ = float(m.group("s"))
    return h*3600 + m_*60 + s_

def iter_cues(lines):
    # Skip WEBVTT header
    i, n = 0, len(lines)
    if i < n and lines[i].strip().upper().startswith("WEBVTT"):
        i += 1
        while i < n and lines[i].strip() != "":
            i += 1
        while i < n and lines[i].strip() == "":
            i += 1

    while i < n:
        # optional cue id
        if i < n and "-->" not in lines[i]:
            i += 1
            if i >= n: break
        if "-->" not in lines[i]:
            i += 1
            continue
        timing = lines[i].strip(); i += 1
        parts = [p.strip() for p in timing.split("-->")]
        if len(parts) != 2:
            continue
        start = parse_time(parts[0]); end = parse_time(parts[1])
        if start is None or end is None or end <= start:
            # skip until blank
            while i < n and lines[i].strip() != "": i += 1
            while i < n and lines[i].strip() == "": i += 1
            continue

        # collect text until blank
        txt = []
        while i < n and lines[i].strip() != "":
            line = TAG_RE.sub("", lines[i].rstrip("\n"))
            if not STAGE_RE.match(line):
                txt.append(line)
            i += 1
        # skip blank sep
        while i < n and lines[i].strip() == "":
            i += 1
        yield start, end, "\n".join(txt)

def main():
    if len(sys.argv) < 2:
        print("usage: timeline_from_captions.py <file.vtt>", file=sys.stderr)
        sys.exit(2)
    path = sys.argv[1]
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    out = []
    for s, e, text in iter_cues(lines):
        tokens = WORD_RE.findall(text)
        if not tokens:
            continue
        dur = max(0.001, e - s)
        step = dur / len(tokens)
        t = s
        for w in tokens:
            w_ = w.lower()
            start = t
            end = min(e, t + step)
            out.append((w_, start, end))
            t += step

    # emit
    w = sys.stdout.write
    for w_, a, b in out:
        w(f"{w_}\t{a:.3f}\t{b:.3f}\n")

if __name__ == "__main__":
    main()
