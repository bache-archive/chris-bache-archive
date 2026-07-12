#!/usr/bin/env python3
"""Lightweight Parquet sanity checks for transcript chunk timecodes."""

from __future__ import annotations

import os

import pandas as pd


def stats(group: pd.DataFrame, tail_window: int = 120) -> tuple[int, int, int, int]:
    starts = group["start_sec"].dropna()
    if starts.empty:
        return (0, 0, 0, 0)
    max_start = int(starts.max())
    tail_count = int((starts >= max_start - tail_window).sum())
    max_dupe = int(starts.value_counts().max())
    return (len(group), tail_count, max_start, max_dupe)


def main() -> None:
    parquet_path = os.environ.get("PARQ", "vectors/bache-talks.embeddings.parquet")
    df = pd.read_parquet(parquet_path)
    rows = []
    for talk_id, group in df.groupby("talk_id"):
        count, tail_count, max_start, max_dupe = stats(group)
        if count >= 5 and tail_count / count >= 0.20:
            rows.append((talk_id, count, tail_count, 100 * tail_count / count, max_dupe, max_start))

    rows.sort(key=lambda item: -item[3])
    print("== Tail concentrations (>=20% in last 120s) ==")
    for talk_id, count, tail_count, pct, max_dupe, max_start in rows[:15]:
        hhmmss = f"{max_start // 3600:02d}:{(max_start % 3600) // 60:02d}:{max_start % 60:02d}"
        print(
            f"- {talk_id:64} n={count:4d} tail={tail_count:3d} "
            f"({pct:5.1f}%) max_dupe={max_dupe} max={hhmmss}"
        )


if __name__ == "__main__":
    main()
