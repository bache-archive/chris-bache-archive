#!/usr/bin/env python3
"""
Build a word-level timeline TSV from a diarist transcript (.txt).

Assumed diarist format (Otter-like):
  Speaker  <space><space> mm:ss
  <text lines...>
  Speaker2 <space><space> hh:mm:ss
  <text lines...>
  ...

We:
- Detect lines containing a timestamp token at end (mm:ss or hh:mm:ss).
- Treat each timed block's text as running until the next timestamp.
- Distribute the block duration evenly across tokens.
- Last block's end is heuristically estimated: max(2s, 0.35s * tokens).

STDOUT TSV (no header):
  word <TAB> start_sec <TAB> end_sec
"""
import sys, re

TS_RE = re.compile(r'(?P<h>\d{1,2}:)?(?P<m>\d{1,2}):(?P<s>\d{2})\s*$')
WORD_RE = re.compile(r"[A-Za-z0-9]+'?[A-Za-z0-9]+")

def parse_ts(tok):
    parts = tok.strip().split(":")
    if len(parts) == 2:
        m, s = parts
        return int(m)*60 + int(s)
    elif len(parts) == 3:
        h, m, s = parts
        return int(h)*3600 + int(m)*60 + int(s)
    return None

def main():
    if len(sys.argv) < 2:
        print("usage: timeline_from_diarist.py <file.txt>", file=sys.stderr)
        sys.exit(2)
    path = sys.argv[1]
    with open(path, "r", encoding="utf-8") as f:
        lines = [ln.rstrip("\n") for ln in f]

    # Identify block starts: line with a timestamp token at end
    idx_ts = []
    for i, ln in enumerate(lines):
        m = TS_RE.search(ln)
        if m:
            ts = m.group(0).strip()
            t = parse_ts(ts)
            if t is not None:
                idx_ts.append((i, t))

    # Build blocks (start_line, start_sec, end_line_exclusive, end_sec_est)
    blocks = []
    for j, (i, t) in enumerate(idx_ts):
        end_line = idx_ts[j+1][0] if j+1 < len(idx_ts) else len(lines)
        end_time = idx_ts[j+1][1] if j+1 < len(idx_ts) else None
        # Collect text body
        body = []
        k = i + 1
        while k < end_line:
            ln = lines[k].strip()
            if ln:
                body.append(ln)
            k += 1
        blocks.append((t, end_time, " ".join(body)))

    out = []
    for start, end, text in blocks:
        tokens = WORD_RE.findall(text)
        if not tokens:
            continue
        if end is None:
            # Heuristic for last block
            est = max(2.0, 0.35 * len(tokens))
            end = start + est
        dur = max(0.001, end - start)
        step = dur / len(tokens)
        t = start
        for w in tokens:
            w_ = w.lower()
            a = t
            b = min(end, t + step)
            out.append((w_, a, b))
            t += step

    w = sys.stdout.write
    for w_, a, b in out:
        w(f"{w_}\t{a:.3f}\t{b:.3f}\n")

if __name__ == "__main__":
    main()
