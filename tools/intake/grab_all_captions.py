#!/usr/bin/env python3
# tools/intake/grab_all_captions.py
# Downloads YouTube captions for all entries in index.json.
# - Auto captions -> sources/captions/<talk_id>.vtt
# - Human captions -> sources/captions/<talk_id>-human.vtt
# Additions:
#   • --only-from-patch, --out-dir
#   • Robust repo-relative path printing
#   • Authentication passthrough for age-restricted videos:
#       --yt-cookies-from-browser <browser>  (safari|chrome|brave|firefox|chromium)
#       --yt-cookies <cookies.txt>           (Netscape cookies file)

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

# --- Paths ---
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent  # repo root (absolute)

CAP_DIR_DEFAULT = ROOT / "sources" / "captions"
CAP_DIR = CAP_DIR_DEFAULT  # may be overridden by --out-dir

# --- Small utilities ---------------------------------------------------------
def to_repo_rel(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(ROOT))
    except Exception:
        return str(p.resolve())

def run(cmd: str) -> tuple[int, str, str]:
    try:
        res = subprocess.run(
            cmd, shell=True, check=False,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        return res.returncode, res.stdout, res.stderr
    except Exception as e:
        return 1, "", str(e)

# --- Core helpers ------------------------------------------------------------
def derive_talk_id(item: dict) -> str | None:
    tr = item.get("transcript") or ""
    m = re.search(r"([^/]+)\.md$", tr)
    if m:
        return m.group(1)
    for key in ("id", "slug", "youtube_id"):
        val = (item.get(key) or "").strip()
        if val:
            return val
    return None

def target_paths(talk_id: str) -> tuple[Path, Path]:
    auto_default = CAP_DIR / f"{talk_id}.vtt"
    human_side = CAP_DIR / f"{talk_id}-human.vtt"
    return auto_default, human_side

def newest_vtt(path: Path) -> Path | None:
    vtts = list(path.glob("*.vtt"))
    if not vtts:
        return None
    return max(vtts, key=lambda p: p.stat().st_mtime)

def clean_tmp(tmpdir: Path) -> None:
    tmpdir.mkdir(parents=True, exist_ok=True)
    for p in tmpdir.glob("*"):
        if p.is_file():
            p.unlink()

def build_yt_auth_args(args: argparse.Namespace) -> str:
    extra = []
    if args.yt_cookies_from_browser:
        extra += [f'--cookies-from-browser {args.yt_cookies_from_browser}']
    if args.yt_cookies:
        # If both provided, yt-dlp prefers explicit cookies file; keep both just in case
        extra += [f'--cookies "{args.yt_cookies}"']
    # Mildly helpful on some region locks:
    extra += ['--geo-bypass']
    return " ".join(extra)

def fetch_auto(url: str, tmpdir: Path, yt_extra: str) -> tuple[int, str, str]:
    cmd = (
        f'yt-dlp "{url}" {yt_extra} '
        f'--write-auto-subs --sub-format vtt '
        f'--skip-download -o "{tmpdir}/%(id)s.%(ext)s"'
    )
    return run(cmd)

def fetch_human(url: str, tmpdir: Path, yt_extra: str) -> tuple[int, str, str]:
    cmd = (
        f'yt-dlp "{url}" {yt_extra} '
        f'--write-subs --sub-langs "en.*,en" --sub-format vtt '
        f'--skip-download -o "{tmpdir}/%(id)s.%(ext)s"'
    )
    return run(cmd)

def extract_only_from_patch(patch_path: Path) -> set[str]:
    ids: set[str] = set()
    if not patch_path or not patch_path.exists():
        return ids
    try:
        data = json.loads(patch_path.read_text(encoding="utf-8"))
    except Exception:
        return ids

    def add(s):
        if isinstance(s, str) and s.strip():
            ids.add(s.strip())

    items = data if isinstance(data, list) else (data.get("items") or data.get("entries") or [])
    for it in (items or []):
        add(it.get("id"))
        add(it.get("slug"))
        add(it.get("youtube_id"))
        tr = (it.get("transcript") or "")
        m = re.search(r"([^/]+)\.md$", tr)
        if m:
            add(m.group(1))
    return ids

# --- Main --------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Download timestamped captions (VTT) for items in index.json")
    ap.add_argument("--index", default=str(ROOT / "index.json"), help="Path to index.json (default: repo root index.json)")
    ap.add_argument("--force", action="store_true", help="Overwrite existing .vtt if present")
    ap.add_argument("--only", nargs="*", help="Restrict to these talk_ids or youtube_ids")
    ap.add_argument("--only-from-patch", help="JSON file listing items to restrict to (reads id/slug/youtube_id/transcript)")
    ap.add_argument("--out-dir", help="Directory to write VTT files into (default: sources/captions/)")
    # NEW: auth passthrough
    ap.add_argument("--yt-cookies-from-browser", help="Browser for yt-dlp cookies (safari|chrome|brave|firefox|chromium)")
    ap.add_argument("--yt-cookies", help="Path to a cookies.txt file (Netscape format)")
    args = ap.parse_args()

    # Resolve index
    index_path = Path(args.index)
    if not index_path.exists():
        print(f"ERROR: index.json not found at {index_path}", file=sys.stderr)
        sys.exit(1)

    # Output captions directory
    global CAP_DIR
    CAP_DIR = Path(args.out_dir).resolve() if args.out_dir else CAP_DIR_DEFAULT
    CAP_DIR.mkdir(parents=True, exist_ok=True)

    # Load items (supports {"items":[...]} or bare list)
    try:
        obj = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"ERROR: failed to read {index_path}: {e}", file=sys.stderr)
        sys.exit(1)

    items = obj.get("items") if isinstance(obj, dict) else obj
    if not isinstance(items, list):
        print("ERROR: index format not recognized (expected list or {'items': [...]})", file=sys.stderr)
        sys.exit(1)

    # Temp staging for yt-dlp outputs
    tmp = CAP_DIR / "_tmp"
    tmp.mkdir(parents=True, exist_ok=True)

    # Filters
    only_set = set(args.only or [])
    if args.only_from_patch:
        only_set |= extract_only_from_patch(Path(args.only_from_patch))

    yt_extra = build_yt_auth_args(args)

    manifest_rows: list[dict] = []

    for it in items:
        talk_id = derive_talk_id(it)
        yid = (it.get("youtube_id") or "").strip()
        url = (it.get("youtube_url") or "").strip() or (f"https://youtu.be/{yid}" if yid else "")

        if not talk_id:
            manifest_rows.append({"talk_id": "", "youtube_id": yid, "status": "skipped:no_talk_id", "auto_path": "", "human_path": ""})
            continue

        if not url:
            manifest_rows.append({"talk_id": talk_id, "youtube_id": yid, "status": "skipped:no_youtube", "auto_path": "", "human_path": ""})
            continue

        if only_set and (talk_id not in only_set and yid not in only_set):
            manifest_rows.append({"talk_id": talk_id, "youtube_id": yid, "status": "skipped:filtered", "auto_path": "", "human_path": ""})
            continue

        auto_path, human_path = target_paths(talk_id)
        have_auto = auto_path.exists()
        have_human = human_path.exists()

        if (have_auto or have_human) and not args.force:
            status = "exists:auto_human" if (have_auto and have_human) else ("exists:auto" if have_auto else "exists:human")
            manifest_rows.append({
                "talk_id": talk_id,
                "youtube_id": yid,
                "status": status,
                "auto_path": to_repo_rel(auto_path) if have_auto else "",
                "human_path": to_repo_rel(human_path) if have_human else "",
            })
            continue

        # Clean temp staging
        clean_tmp(tmp)

        # 1) AUTO captions
        auto_rc, auto_out, auto_err = fetch_auto(url, tmp, yt_extra)
        auto_vtt = newest_vtt(tmp)

        wrote_auto = False
        if auto_rc == 0 and auto_vtt:
            if auto_path.exists():
                auto_path.unlink()
            shutil.move(str(auto_vtt), str(auto_path))
            wrote_auto = True

        # 2) HUMAN captions
        clean_tmp(tmp)
        human_rc, human_out, human_err = fetch_human(url, tmp, yt_extra)
        human_vtt = newest_vtt(tmp)
        wrote_human = False
        if human_rc == 0 and human_vtt:
            if human_path.exists():
                human_path.unlink()
            shutil.move(str(human_vtt), str(human_path))
            wrote_human = True

        # Record result
        if wrote_auto and wrote_human:
            status = "downloaded:auto+human"
        elif wrote_auto:
            status = "downloaded:auto"
        elif wrote_human:
            status = "downloaded:human_only"
        else:
            status = f"failed:{auto_rc}/{human_rc}"

        manifest_rows.append({
            "talk_id": talk_id,
            "youtube_id": yid,
            "status": status,
            "auto_path": to_repo_rel(auto_path) if (wrote_auto or auto_path.exists()) else "",
            "human_path": to_repo_rel(human_path) if (wrote_human or human_path.exists()) else "",
        })

    # Write manifest CSV
    man_path = CAP_DIR / "_captions_manifest.csv"
    with man_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["talk_id", "youtube_id", "status", "auto_path", "human_path"])
        w.writeheader()
        w.writerows(manifest_rows)

    # STDOUT summary
    counts = Counter(r["status"] for r in manifest_rows)
    print("\n=== Captions Download Summary ===")
    for k in sorted(counts):
        print(f"{k:26s} {counts[k]:4d}")
    print(f"Manifest: {to_repo_rel(man_path)}\n")

    # Quick review table
    print("talk_id                                       youtube_id        status                     auto_vtt                                 human_vtt")
    print("-" * 130)
    for r in manifest_rows:
        print(
            f"{(r['talk_id'] or ''):44s}  "
            f"{(r['youtube_id'] or ''):12s}  "
            f"{r['status']:24s}  "
            f"{(r['auto_path'] or '-'):38s}  "
            f"{(r['human_path'] or '-'):38s}"
        )

if __name__ == "__main__":
    main()