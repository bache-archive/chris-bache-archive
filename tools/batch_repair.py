#!/usr/bin/env python3
"""
tools/batch_repair.py

Harvest → Merge → Build → Style for a list of QIDs, with per-topic isolation.
Intended to avoid shell subtleties (zsh subshells, set -e, etc.).

Usage:
  python3 tools/batch_repair.py
  python3 tools/batch_repair.py --date 2025-10-22
  python3 tools/batch_repair.py --top-k 16 --date $(date +%F)
  python3 tools/batch_repair.py --qids diamond-luminosity grof-coex
"""

from __future__ import annotations
import argparse, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
DOCS  = ROOT / "docs" / "educational"

DEFAULT_QIDS = [
    "diamond-luminosity",
    "grof-coex",
    "dose-retrospective",
    "evolution-of-the-species-mind",
    "future-human",
    "great-death-and-rebirth",
]

LEAK_KEYS = (
    "archivaltitle", "criptiondate", "channel", "recorded", "published",
    "youtubeid", "speakers", "transcrib", "transcriptiondate", "Abstract"
)

def run(cmd: list[str], env: dict | None = None) -> int:
    print(f"+ {' '.join(cmd)}")
    proc = subprocess.run(cmd, env=env)
    return proc.returncode

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="Harvest date folder (YYYY-MM-DD). Default: today.")
    ap.add_argument("--top-k", type=int, default=int(os.getenv("TOP_K", "16")))
    ap.add_argument("--qids", nargs="*", default=DEFAULT_QIDS)
    ap.add_argument("--site-base", default="/chris-bache-archive")
    ap.add_argument("--stylesheet", default="assets/style.css")
    args = ap.parse_args()

    # Ensure python exists (simple sanity)
    if not sys.executable:
        print("[error] No Python interpreter found.")
        sys.exit(127)

    # Stable env for all child processes
    env = os.environ.copy()
    if args.date:
        env["RUN_DATE"] = args.date
    env["WITH_TIMECODES"] = "1"

    failures = []

    print("=== Starting batch repair ===")
    print(f"QIDs: {', '.join(args.qids)}")
    print(f"RUN_DATE={env.get('RUN_DATE','(today)')} TOP_K={args.top_k} WITH_TIMECODES=1\n")

    for q in args.qids:
        print(f"==== Harvesting {q} ====")
        rc = run(
            [sys.executable, str(TOOLS / "harvest_quote_packs.py"),
             "--date", env.get("RUN_DATE", ""),
             "--qid", q,
             "--top-k", str(args.top_k)],
            env=env
        )
        if rc != 0:
            print(f"[fail] harvest {q} (rc={rc}) — continuing")
            failures.append(("harvest", q, rc))

        print(f"==== Merging {q} ====")
        rc = run(
            [sys.executable, str(TOOLS / "merge_harvest_into_sources.py"),
             "--date", env.get("RUN_DATE", ""),
             "--qid", q],
            env=env
        )
        if rc != 0:
            print(f"[warn] merge {q} (rc={rc}) — continuing")
            failures.append(("merge", q, rc))

        print(f"==== Building docs {q} ====")
        rc = run(
            [sys.executable, str(TOOLS / "build_educational_docs_full.py"),
             "--qid", q],
            env=env
        )
        if rc != 0:
            print(f"[warn] build docs {q} (rc={rc}) — continuing")
            failures.append(("build_docs", q, rc))

    print("==== Building site (HTML wrappers with unified styling) ====")
    rc = run(
        [sys.executable, str(TOOLS / "build_site.py"),
         "--site-base", args.site_base,
         "--stylesheet", args.stylesheet],
        env=env
    )
    if rc != 0:
        print(f"[warn] build_site failed (rc={rc})")
        failures.append(("build_site", "(all)", rc))

    print("\n==== Quick validation: leak check (should print nothing) ====")
    issues_found = 0
    for q in args.qids:
        f = DOCS / q / "index.html"
        if not f.exists():
            print(f"[warn] missing {f}")
            issues_found += 1
            continue
        txt = f.read_text(encoding="utf-8", errors="ignore")
        hits = [k for k in LEAK_KEYS if k in txt]
        if hits:
            issues_found += 1
            print(f"[leak] {f} → found: {', '.join(hits)}")

    print("\n==== Summary ====")
    if failures:
        for stage, q, rc in failures:
            print(f"  - {stage:12} {q:36} rc={rc}")
    else:
        print("  - stages: OK")

    if issues_found:
        print(f"  - leak-check: {issues_found} file(s) with leaks")
    else:
        print("  - leak-check: OK")

    # Non-zero exit if anything failed or leaked
    sys.exit(1 if failures or issues_found else 0)

if __name__ == "__main__":
    main()
