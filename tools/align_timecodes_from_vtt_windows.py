#!/usr/bin/env python3
"""
Align missing timecodes in vectors/bache-talks.embeddings.parquet
using local WebVTT captions with adaptive windowing + fuzzy matching.

Behavior:
- Only patches rows whose URL is YouTube.
- By default, aligns ONLY rows missing timecodes.
- Per talk_id, if >20% rows are still missing, enables a 3rd, more forgiving pass.

Environment variables (optional tuning):
  PARQUET_PATH=vectors/bache-talks.embeddings.parquet
  CAPTIONS_DIR=sources/captions

  # thresholds
  ALIGN_THRESH_A=70   # primary
  ALIGN_THRESH_B=62   # fallback
  ALIGN_THRESH_C=68   # conditional WRatio pass for low-coverage talks

  # probe lengths (chars)
  ALIGN_PROBE_MIN=180
  ALIGN_PROBE_MAX=320

  # window scale factors relative to probe length
  ALIGN_PASSA_MIN=0.8
  ALIGN_PASSA_MAX=1.6
  ALIGN_PASSB_MIN=0.6
  ALIGN_PASSB_MAX=2.0
  ALIGN_PASSC_MIN=0.6
  ALIGN_PASSC_MAX=2.2

  # feature flags
  ALIGN_USE_PASS_C=1  # 1 to enable (default), 0 to disable
  FULL_REFRESH=0      # 1 to re-align ALL YouTube rows (overwrite existing), 0 default only-missing
"""

from __future__ import annotations
import os, re, sys
from pathlib import Path
import pandas as pd
from rapidfuzz import fuzz
from ftfy import fix_text

# ---- Config ----
PARQ = os.getenv("PARQUET_PATH", "vectors/bache-talks.embeddings.parquet")
CAPS = Path(os.getenv("CAPTIONS_DIR", "sources/captions"))

THRESH_A = int(os.getenv("ALIGN_THRESH_A", "70"))
THRESH_B = int(os.getenv("ALIGN_THRESH_B", "62"))
THRESH_C = int(os.getenv("ALIGN_THRESH_C", "68"))

PROBE_MIN = int(os.getenv("ALIGN_PROBE_MIN", "180"))
PROBE_MAX = int(os.getenv("ALIGN_PROBE_MAX", "320"))

PASSA_MIN_F = float(os.getenv("ALIGN_PASSA_MIN", "0.8"))
PASSA_MAX_F = float(os.getenv("ALIGN_PASSA_MAX", "1.6"))
PASSB_MIN_F = float(os.getenv("ALIGN_PASSB_MIN", "0.6"))
PASSB_MAX_F = float(os.getenv("ALIGN_PASSB_MAX", "2.0"))
PASSC_MIN_F = float(os.getenv("ALIGN_PASSC_MIN", "0.6"))
PASSC_MAX_F = float(os.getenv("ALIGN_PASSC_MAX", "2.2"))

USE_PASS_C = os.getenv("ALIGN_USE_PASS_C", "1") == "1"
FULL_REFRESH = os.getenv("FULL_REFRESH", "0") == "1"

TS_LINE = re.compile(
    r"(?P<sh>\d{1,2}):(?P<sm>\d{2}):(?P<ss>\d{2})\.\d+\s*-->\s*"
    r"(?P<eh>\d{1,2}):(?P<em>\d{2}):(?P<es>\d{2})\.\d+"
)

# ---- Helpers ----
def norm(t: str) -> str:
    return re.sub(r"\s+", " ", fix_text((t or "").strip()))

def hhmmss(t: int) -> str:
    h = t // 3600
    m = (t % 3600) // 60
    s = t % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def is_youtube(u: str | None) -> bool:
    if not u: return False
    u = u.lower()
    return ("youtu.be" in u) or ("youtube.com" in u)

def pick_vtt(talk_id: str) -> Path | None:
    # Prefer human-edited, then human-dot, then plain
    for suf in ("-human.vtt", ".human.vtt", ".vtt"):
        p = CAPS / f"{talk_id}{suf}"
        if p.exists(): return p
    return None

def parse_vtt(path: Path) -> list[dict]:
    """Return list of {'start': seconds, 'text': normalized text}."""
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    segs, start, buf = [], None, []
    for ln in lines:
        m = TS_LINE.search(ln)
        if m:
            if start is not None and buf:
                segs.append({"start": start, "text": norm(" ".join(buf))})
            start = int(m["sh"]) * 3600 + int(m["sm"]) * 60 + int(m["ss"])
            buf = []
            continue
        if ln.strip() and not ln.startswith("WEBVTT"):
            buf.append(ln.strip())
    if start is not None and buf:
        segs.append({"start": start, "text": norm(" ".join(buf))})
    return segs

def windows(segs: list[dict], min_chars: int, max_chars: int):
    """Yield (start_sec, concatenated_text) sliding windows over caption segments."""
    n = len(segs)
    i = 0
    while i < n:
        j = i
        parts, total = [], 0
        while j < n and total < min_chars:
            tx = segs[j]["text"]; parts.append(tx); total += len(tx); j += 1
        while j < n and total < max_chars:
            tx = segs[j]["text"]; parts.append(tx); total += len(tx); j += 1
        yield (segs[i]["start"], norm(" ".join(parts)))
        step = max(1, (j - i) // 2)   # overlapping hops
        i += step

def probe(text: str, min_n: int = PROBE_MIN, max_n: int = PROBE_MAX) -> str:
    """Take a scaled slice (~40% of chunk) clamped between min_n and max_n."""
    t = norm(text)
    target = max(min_n, min(max_n, int(0.4 * len(t))))
    return t[:target]

def best_start_pass_score(segs: list[dict], q: str, thresh: int, min_chars: int, max_chars: int, scorer) -> int | None:
    ql = q.lower()
    best_score, best_start = 0, None
    for st, blob in windows(segs, min_chars, max_chars):
        sc = scorer(ql, blob.lower())
        if sc > best_score:
            best_score, best_start = sc, st
    return best_start if best_score >= thresh else None

def best_start_adaptive(segs: list[dict], chunk_text: str, allow_pass_c: bool = True) -> tuple[int | None, bool]:
    """
    Try multiple passes with widening windows and different scorers.
    Returns (start_sec or None, used_pass_c: bool)
    """
    p = probe(chunk_text)
    plen = len(p)

    # Pass A (partial_ratio, tighter window)
    a_min = max(150, int(PASSA_MIN_F * plen))
    a_max = max(a_min + 120, int(PASSA_MAX_F * plen))
    st = best_start_pass_score(segs, p, THRESH_A, a_min, a_max, fuzz.partial_ratio)
    if st is not None: return st, False

    # Pass B (partial_ratio, wider & gentler)
    b_min = max(140, int(PASSB_MIN_F * plen))
    b_max = max(b_min + 200, int(PASSB_MAX_F * plen))
    st = best_start_pass_score(segs, p, THRESH_B, b_min, b_max, fuzz.partial_ratio)
    if st is not None: return st, False

    # Pass C (WRatio, only for low-coverage talks)
    if allow_pass_c and USE_PASS_C:
        c_min = max(140, int(PASSC_MIN_F * plen))
        c_max = max(c_min + 240, int(PASSC_MAX_F * plen))
        st = best_start_pass_score(segs, p, THRESH_C, c_min, c_max, fuzz.WRatio)
        if st is not None: return st, True

    return None, False

# Back-compat alias (some older runs call *_with_flag and expect just the start)
def best_start_adaptive_with_flag(segs: list[dict], chunk_text: str, allow_pass_c: bool = True):
    st, _used_c = best_start_adaptive(segs, chunk_text, allow_pass_c=allow_pass_c)
    return st

def ensure_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Add missing columns for timing fields."""
    if "start_sec" not in df.columns: df["start_sec"] = pd.Series([pd.NA]*len(df), dtype="float")
    if "start_hhmmss" not in df.columns: df["start_hhmmss"] = pd.Series([pd.NA]*len(df), dtype="object")
    if "ts_url" not in df.columns: df["ts_url"] = pd.Series([pd.NA]*len(df), dtype="object")
    return df

def with_ts_url(url: str, start: int) -> str:
    sep = "&" if "?" in str(url) else "?"
    return f"{url}{sep}t={int(start)}"

# ---- Main ----
def main():
    if not Path(PARQ).exists():
        print(f"[error] parquet not found: {PARQ}", file=sys.stderr)
        sys.exit(1)

    df = pd.read_parquet(PARQ)
    df = ensure_cols(df)

    # Mask selection
    mask_yt = df["url"].map(is_youtube)
    if FULL_REFRESH:
        print("[mode] full refresh — re-aligning all YouTube rows")
        work = df[mask_yt]
    else:
        print("[mode] patch missing — aligning only rows without timecodes")
        mask_missing = df["start_hhmmss"].isna()
        work = df[mask_missing & mask_yt]

    if work.empty:
        print("[info] No candidate rows to align. Nothing to do.")
        return

    changed = 0
    total_to_try = len(work)

    # Per talk_id processing (read VTT once)
    for tid, g in work.groupby("talk_id"):
        vtt = pick_vtt(tid)
        if not vtt:
            print(f"[skip] no VTT found for {tid}")
            continue
        segs = parse_vtt(vtt)
        if not segs:
            print(f"[skip] empty/invalid VTT for {tid} -> {vtt.name}")
            continue

        # Compute current coverage BEFORE matching to decide if we allow Pass C.
        have_now = df.loc[df["talk_id"] == tid, "start_hhmmss"].notna().sum()
        total_now = (df["talk_id"] == tid).sum()
        miss_pct = 1.0 - (have_now / max(1, total_now))
        allow_pass_c = miss_pct > 0.20  # only enable the forgiving pass for low-coverage talks

        url = g["url"].iloc[0]
        patched_this_talk = 0
        used_c_count = 0

        for idx, row in g.iterrows():
            start, used_c = best_start_adaptive(segs, row["text"], allow_pass_c=allow_pass_c)
            if start is None:
                continue
            df.at[idx, "start_sec"] = int(start)
            df.at[idx, "start_hhmmss"] = hhmmss(int(start))
            df.at[idx, "ts_url"] = with_ts_url(url, int(start))
            changed += 1
            patched_this_talk += 1
            if used_c: used_c_count += 1

        # Coverage AFTER patch attempt
        have = df.loc[df["talk_id"] == tid, "start_hhmmss"].notna().sum()
        total = (df["talk_id"] == tid).sum()
        print(f"[{tid}] patched={patched_this_talk}  coverage={have}/{total}  used_pass_c={used_c_count}  allow_pass_c={'yes' if allow_pass_c else 'no'}")

    if changed:
        df.to_parquet(PARQ, index=False)
        print(f"[ok] patched {changed} rows (of {total_to_try} candidates); wrote {PARQ}")
    else:
        print("[info] No rows updated (consider relaxing thresholds, enabling FULL_REFRESH=1, or checking URL/VTT mismatches).")

if __name__ == "__main__":
    main()