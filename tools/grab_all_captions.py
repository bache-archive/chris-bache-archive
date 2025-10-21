#!/usr/bin/env python3
# tools/grab_all_captions.py
# Downloads YouTube captions for all entries in index.json.
# - Auto captions -> sources/captions/<talk_id>.vtt  (DEFAULT FILENAME)
# - Human captions -> sources/captions/<talk_id>-human.vtt
# Won't overwrite existing files unless --force is provided.
# Emits: sources/captions/_captions_manifest.csv and a concise stdout summary.

import argparse, json, subprocess, sys, shutil, os, csv, re
from pathlib import Path
from collections import Counter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent  # repo root
CAP_DIR = ROOT / "sources" / "captions"
CAP_DIR.mkdir(parents=True, exist_ok=True)

def derive_talk_id(item):
    tr = item.get("transcript") or ""
    m = re.search(r"([^/]+)\.md$", tr)
    if m:
        return m.group(1)
    yid = (item.get("youtube_id") or "").strip()
    return yid or None

def target_paths(talk_id):
    auto_default = CAP_DIR / f"{talk_id}.vtt"          # AUTO uses default filename
    human_side   = CAP_DIR / f"{talk_id}-human.vtt"    # HUMAN gets -human suffix
    return auto_default, human_side

def run(cmd):
    try:
        res = subprocess.run(cmd, shell=True, check=False,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return res.returncode, res.stdout, res.stderr
    except Exception as e:
        return 1, "", str(e)

def newest_vtt(path: Path):
    vtts = list(path.glob("*.vtt"))
    if not vtts: return None
    return max(vtts, key=lambda p: p.stat().st_mtime)

def fetch_auto(url, tmpdir):
    cmd = (
        f'yt-dlp "{url}" '
        f'--write-auto-subs --sub-format vtt '
        f'--skip-download -o "{tmpdir}/%(id)s.%(ext)s"'
    )
    return run(cmd)

def fetch_human(url, tmpdir):
    # grab any English human track
    cmd = (
        f'yt-dlp "{url}" '
        f'--write-subs --sub-langs "en.*,en" --sub-format vtt '
        f'--skip-download -o "{tmpdir}/%(id)s.%(ext)s"'
    )
    return run(cmd)

def clean_tmp(tmpdir: Path):
    tmpdir.mkdir(parents=True, exist_ok=True)
    for p in tmpdir.glob("*"):
        if p.is_file():
            p.unlink()

def main():
    ap = argparse.ArgumentParser(description="Download timestamped captions (VTT) for items in index.json")
    ap.add_argument("--index", default=str(ROOT / "index.json"))
    ap.add_argument("--force", action="store_true", help="Overwrite existing .vtt if present")
    ap.add_argument("--only", nargs="*", help="Restrict to these talk_ids or youtube_ids")
    args = ap.parse_args()

    index_path = Path(args.index)
    if not index_path.exists():
        print(f"ERROR: index.json not found at {index_path}", file=sys.stderr)
        sys.exit(1)

    items = json.loads(index_path.read_text(encoding="utf-8"))
    tmp = CAP_DIR / "_tmp"
    tmp.mkdir(parents=True, exist_ok=True)

    manifest_rows = []
    for it in items:
        talk_id = derive_talk_id(it)
        yid = (it.get("youtube_id") or "").strip()
        url = (it.get("youtube_url") or "").strip() or (f"https://youtu.be/{yid}" if yid else "")

        if not talk_id:
            manifest_rows.append({"talk_id":"", "youtube_id":yid, "status":"skipped:no_talk_id", "auto_path":"", "human_path":""})
            continue
        if not url:
            manifest_rows.append({"talk_id":talk_id, "youtube_id":yid, "status":"skipped:no_youtube", "auto_path":"", "human_path":""})
            continue
        if args.only and (talk_id not in args.only and yid not in args.only):
            manifest_rows.append({"talk_id":talk_id, "youtube_id":yid, "status":"skipped:filtered", "auto_path":"", "human_path":""})
            continue

        auto_path, human_path = target_paths(talk_id)
        have_auto  = auto_path.exists()
        have_human = human_path.exists()

        if (have_auto or have_human) and not args.force:
            status = "exists:auto_human" if (have_auto and have_human) else ("exists:auto" if have_auto else "exists:human")
            manifest_rows.append({
                "talk_id":talk_id, "youtube_id":yid, "status":status,
                "auto_path":str(auto_path.relative_to(ROOT)) if have_auto else "",
                "human_path":str(human_path.relative_to(ROOT)) if have_human else ""
            })
            continue

        # Clean temp staging
        clean_tmp(tmp)

        # 1) AUTO captions (default filename)
        auto_rc, _, _ = fetch_auto(url, tmp)
        auto_vtt = newest_vtt(tmp)

        wrote_auto = False
        if auto_rc == 0 and auto_vtt:
            if auto_path.exists(): auto_path.unlink()
            shutil.move(str(auto_vtt), str(auto_path))
            wrote_auto = True

        # 2) HUMAN captions (sidecar -human.vtt)
        clean_tmp(tmp)
        human_rc, _, _ = fetch_human(url, tmp)
        human_vtt = newest_vtt(tmp)
        wrote_human = False
        if human_rc == 0 and human_vtt:
            if human_path.exists(): human_path.unlink()
            shutil.move(str(human_vtt), str(human_path))
            wrote_human = True

        # Record result
        if wrote_auto and wrote_human:
            status = "downloaded:auto+human"
        elif wrote_auto:
            status = "downloaded:auto"
        elif wrote_human:
            # No auto available; we still save human sidecar only
            status = "downloaded:human_only"
        else:
            status = f"failed:{auto_rc}/{human_rc}"

        manifest_rows.append({
            "talk_id":talk_id,
            "youtube_id":yid,
            "status":status,
            "auto_path":str(auto_path.relative_to(ROOT)) if (wrote_auto or auto_path.exists()) else "",
            "human_path":str(human_path.relative_to(ROOT)) if (wrote_human or human_path.exists()) else ""
        })

    # Write manifest CSV
    man_path = CAP_DIR / "_captions_manifest.csv"
    with man_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["talk_id","youtube_id","status","auto_path","human_path"])
        w.writeheader()
        w.writerows(manifest_rows)

    # STDOUT summary
    counts = Counter(r["status"] for r in manifest_rows)
    print("\n=== Captions Download Summary ===")
    for k in sorted(counts):
        print(f"{k:26s} {counts[k]:4d}")
    print(f"Manifest: {man_path.relative_to(ROOT)}\n")

    # Quick review table for human vs auto
    print("talk_id                                       youtube_id        status                     auto_vtt                                 human_vtt")
    print("-"*130)
    for r in manifest_rows:
        print(f"{(r['talk_id'] or ''):44s}  {(r['youtube_id'] or ''):12s}  {r['status']:24s}  {(r['auto_path'] or '-'):38s}  {(r['human_path'] or '-'):38s}")

if __name__ == "__main__":
    main()
