#!/usr/bin/env python3
"""
tools/media/download_media.py

Download YouTube media (MP3 audio and/or MP4 video) for items in an index,
optionally restricted to a patch JSON. Produces a CSV manifest with per-item
results and stderr tails for debugging.

Key improvements
- Robust client fallbacks (android, ios, tv, tv_embedded, web_creator, mweb, web)
- Detects success by scanning for actual files (no false positives)
- Avoids SABR pitfalls by preferring non-web clients first
- Cleaner cookies handling: only attaches browser cookies for web-like clients
- Works with list or {"items": [...]} index shapes
- Compatible with prior CLI flags from earlier script

Usage (audio only, patch-scoped)
--------------------------------
export PATCH=2025-10-31-bache-youtube
python tools/media/download_media.py \
  --index "patches/$PATCH/outputs/index.merged.json" \
  --only-from-patch "patches/$PATCH/work/index.patch.json" \
  --audio-dir "build/patch-preview/$PATCH/downloads/audio" \
  --yt-cookies-from-browser "chrome:Default" \
  --verbose

(Optionally add --video-dir to pull MP4s too.)
"""

from __future__ import annotations
import argparse
import csv
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------- Constants & Client Order ----------

AUDIO_FORMAT_EXPR = "bestaudio[ext=m4a]/140/251/bestaudio/best/ba"
VIDEO_FORMAT_EXPR = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"

CLIENT_ORDER = ["android", "ios", "tv", "tv_embedded", "web_creator", "mweb", "web"]

SABR_MSG = "Only images are available for download"
AGE_MSG = "confirm your age"
PO_WARN = "android client https formats require a GVS PO Token"

# ---------- Paths ----------

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent  # repo root

# ---------- Small utils ----------

def info(v: bool, msg: str) -> None:
    if v:
        print(f"[INFO] {msg}", flush=True)

def warn(msg: str) -> None:
    print(f"[WARN] {msg}", flush=True)

def to_repo_rel(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(ROOT))
    except Exception:
        return str(p.resolve())

def run(cmd: List[str]) -> Tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return p.returncode, p.stdout, p.stderr
    except Exception as e:
        return 1, "", str(e)

# ---------- Index & Patch helpers ----------

def load_index(index_path: Path, verbose: bool=False) -> List[Dict]:
    if not index_path.exists():
        raise FileNotFoundError(f"index not found: {index_path}")
    data = json.loads(index_path.read_text(encoding="utf-8"))
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError("index must be a list or {'items':[...]} at the top level")
    info(verbose, f"Loaded index items: {len(items)} from {to_repo_rel(index_path)}")
    return items

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
        for k in ("id", "slug", "youtube_id"):
            v = (it.get(k) or "").strip()
            if v:
                ids.add(v)
        tr = (it.get("transcript") or "").strip()
        m = re.search(r"([^/]+)\.md$", tr)
        if m:
            ids.add(m.group(1))
    info(verbose, f"Filtered IDs from patch: {len(ids)}")
    return ids

def basename_for_item(it: Dict) -> Optional[str]:
    # Prefer YouTube ID (stable, unique), else transcript stem, else id/slug
    yid = (it.get("youtube_id") or "").strip()
    if yid:
        return yid
    tr = (it.get("transcript") or "").strip()
    if tr:
        m = re.search(r"([^/]+)\.md$", tr)
        if m:
            return m.group(1)
    for k in ("id", "slug"):
        v = (it.get(k) or "").strip()
        if v:
            return v
    return None

def youtube_url_for(it: Dict) -> str:
    url = (it.get("youtube_url") or "").strip()
    yid = (it.get("youtube_id") or "").strip()
    return url or (f"https://youtu.be/{yid}" if yid else "")

# ---------- yt-dlp command builders ----------

def build_base_args() -> List[str]:
    return [
        "yt-dlp",
        "--progress",
        "--continue",                 # resume partial
        "--no-overwrites",            # don't clobber finished files
        "--restrict-filenames",
        "--force-ipv4",
        "--geo-bypass-country", "US",
        "--sleep-requests", "1",
        "--min-sleep-interval", "1", "--max-sleep-interval", "3",
        "--concurrent-fragments", "1",
        "--format-sort", "proto:https",
    ]

def client_allows_cookies(client: str) -> bool:
    return client in ("web", "mweb", "web_creator", "web_embedded")

# ---------- Single-attempt download helpers (detect by scanning files) ----------

def try_download_audio(url: str,
                       out_glob_base: Path,
                       client: str,
                       cookies_from_browser: Optional[str],
                       cookies_file: Optional[str],
                       verbose: bool) -> Tuple[bool, str, Optional[Path]]:
    cmd = build_base_args()
    cmd += ["--extractor-args", f"youtube:player_client={client}"]
    if client_allows_cookies(client) and cookies_from_browser:
        cmd += ["--cookies-from-browser", cookies_from_browser]
    if cookies_file:
        cmd += ["--cookies", cookies_file]
    cmd += ["-f", AUDIO_FORMAT_EXPR, "-o", str(out_glob_base), url]

    rc, so, se = run(cmd)
    err = (so + "\n" + se)
    audio_dir = out_glob_base.parent
    base = out_glob_base.name.replace(".%(ext)s", "")
    found = None
    for ext in (".m4a", ".webm", ".opus", ".mp3"):
        p = audio_dir / f"{base}{ext}"
        if p.exists() and p.stat().st_size > 0:
            found = p
            break
    ok = found is not None
    if verbose:
        info(True, f"client={client} cookies={'on' if (client_allows_cookies(client) and cookies_from_browser) else 'off'} rc={rc} ok={'Y' if ok else 'N'}")
    return ok, err, found

def try_download_video(url: str,
                       out_path: Path,
                       client: str,
                       cookies_from_browser: Optional[str],
                       cookies_file: Optional[str],
                       verbose: bool) -> Tuple[bool, str]:
    cmd = build_base_args()
    cmd += ["--extractor-args", f"youtube:player_client={client}"]
    if client_allows_cookies(client) and cookies_from_browser:
        cmd += ["--cookies-from-browser", cookies_from_browser]
    if cookies_file:
        cmd += ["--cookies", cookies_file]
    cmd += ["-f", VIDEO_FORMAT_EXPR, "-o", str(out_path), url]
    rc, so, se = run(cmd)
    err = (so + "\n" + se)
    ok = out_path.exists() and out_path.stat().st_size > 0
    if verbose:
        info(True, f"video client={client} cookies={'on' if (client_allows_cookies(client) and cookies_from_browser) else 'off'} rc={rc} ok={'Y' if ok else 'N'}")
    return ok, err

# ---------- Multi-client fallback wrappers ----------

def download_audio_with_fallbacks(url: str,
                                  out_glob_base: Path,
                                  cookies_from_browser: Optional[str],
                                  cookies_file: Optional[str],
                                  verbose: bool) -> Tuple[bool, str, Optional[Path]]:
    last_err = ""
    for client in CLIENT_ORDER:
        ok, err, found = try_download_audio(url, out_glob_base, client, cookies_from_browser, cookies_file, verbose)
        if ok and found:
            return True, "", found

        last_err = err[-2000:]
        lerr = last_err.lower()
        if SABR_MSG.lower() in lerr:
            if verbose: warn("SABR detected (audio); trying next client")
            continue
        if PO_WARN.lower() in lerr and client == "android":
            if verbose: warn("Android PO-token warning (audio); trying next client")
            continue
        if AGE_MSG in lerr and not client_allows_cookies(client):
            if verbose: warn("Age gate hint (audio); will try a web client with cookies")
            continue
    return False, last_err, None

def download_video_with_fallbacks(url: str,
                                  out_path: Path,
                                  cookies_from_browser: Optional[str],
                                  cookies_file: Optional[str],
                                  verbose: bool) -> Tuple[bool, str]:
    last_err = ""
    for client in CLIENT_ORDER:
        ok, err = try_download_video(url, out_path, client, cookies_from_browser, cookies_file, verbose)
        if ok:
            return True, ""
        last_err = err[-2000:]
        lerr = last_err.lower()
        if SABR_MSG.lower() in lerr:
            if verbose: warn("SABR detected (video); trying next client")
            continue
        if PO_WARN.lower() in lerr and client == "android":
            if verbose: warn("Android PO-token warning (video); trying next client")
            continue
        if AGE_MSG in lerr and not client_allows_cookies(client):
            if verbose: warn("Age gate hint (video); will try a web client with cookies")
            continue
    return False, last_err

# ---------- Main ----------

def main() -> int:
    ap = argparse.ArgumentParser(description="Download YouTube media for an index (optionally restricted by patch).")
    ap.add_argument("--index", default=str(ROOT / "index.json"))
    ap.add_argument("--only-from-patch")
    ap.add_argument("--only", action="append", default=[], help="Additional allowlist IDs (id/slug/youtube_id/basename). Can be passed multiple times.")
    ap.add_argument("--video-dir", default=None, help="Directory for MP4 files; omit to skip video.")
    ap.add_argument("--audio-dir", default=str(ROOT / "downloads" / "audio"))
    ap.add_argument("--yt-cookies-from-browser", help="e.g., chrome | chrome:Default | brave | firefox | safari")
    ap.add_argument("--yt-cookies", help="Path to cookies.txt (Netscape format)")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    index_path = Path(args.index).resolve()
    items = load_index(index_path, verbose=args.verbose)

    allow_ids: Optional[set[str]] = None
    if args.only_from_patch:
        allow_ids = extract_ids_from_patch(Path(args.only_from_patch).resolve(), verbose=args.verbose)
    if args.only:
        allow_ids = (allow_ids or set()) | {s.strip() for chunk in args.only for s in chunk.split(",") if s.strip()}

    # Build selection
    work: List[Dict] = []
    for it in items:
        base = basename_for_item(it)
        if not base:
            continue
        if allow_ids:
            ok = False
            for k in ("id", "slug", "youtube_id"):
                v = (it.get(k) or "").strip()
                if v and v in allow_ids:
                    ok = True
                    break
            if base in allow_ids:
                ok = True
            if not ok:
                continue
        work.append(it)

    # Dirs
    audio_dir = Path(args.audio_dir).resolve()
    audio_dir.mkdir(parents=True, exist_ok=True)
    video_dir: Optional[Path] = None
    if args.video_dir:
        video_dir = Path(args.video_dir).resolve()
        video_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = (audio_dir.parent / "_media_manifest.csv").resolve()

    rows: List[Dict] = []
    for i, it in enumerate(work, 1):
        base = basename_for_item(it)
        url  = youtube_url_for(it)
        if not base or not url:
            rows.append({
                "basename": base or "",
                "youtube_url": url or "",
                "status": "skipped:missing_base_or_url",
                "video_path": "",
                "audio_path": "",
                "stderr_tail": "",
            })
            continue

        info(args.verbose, f"[{i}/{len(work)}] {base}")

        # Targets
        a_out_glob = audio_dir / f"{base}.%(ext)s"
        v_out = (video_dir / f"{base}.mp4") if video_dir else None

        # Download
        a_ok, a_err, a_found = download_audio_with_fallbacks(
            url, a_out_glob, args.yt_cookies_from_browser, args.yt_cookies, args.verbose
        )
        if video_dir:
            v_ok, v_err = download_video_with_fallbacks(
                url, v_out, args.yt_cookies_from_browser, args.yt_cookies, args.verbose
            )
        else:
            v_ok, v_err = (False, "")

        status = (
            "ok:video+audio" if (v_ok and a_ok) else
            ("ok:audio_only" if a_ok else ("ok:video_only" if v_ok else "failed"))
        )
        err_tail = ""
        if status == "failed":
            combined = (a_err or "") + "\n" + (v_err or "")
            err_tail = combined[-1000:]
            lerr = err_tail.lower()
            if "age" in lerr and "confirm" in lerr:
                status = "failed:age_restricted"
            elif "403" in lerr or "forbidden" in lerr:
                status = "failed:403"
            elif SABR_MSG.lower() in lerr:
                status = "failed:sabr"
            elif PO_WARN.lower() in lerr:
                status = "failed:po_token"

        rows.append({
            "basename": base,
            "youtube_url": url,
            "status": status,
            "video_path": to_repo_rel(v_out) if (v_out and v_out.exists()) else "",
            "audio_path": to_repo_rel(a_found) if a_found else "",
            "stderr_tail": (err_tail.replace("\x00", " ") if err_tail else ""),
        })

    # Manifest
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["basename", "youtube_url", "status", "video_path", "audio_path", "stderr_tail"]
        )
        w.writeheader()
        w.writerows(rows)

    # Summary
    from collections import Counter
    c = Counter(r["status"] for r in rows)
    print("\n=== Media Download Summary ===")
    for k in sorted(c):
        print(f"{k:24s} {c[k]:4d}")
    print(f"Manifest: {to_repo_rel(manifest_path)}")

    return 0

if __name__ == "__main__":
    sys.exit(main())