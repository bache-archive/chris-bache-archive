#!/usr/bin/env python3
# tools/media/download_media.py
# -----------------------------------------------------------------------------
# CONTEXT / THE FAILURE WE HIT
# -----------------------------------------------------------------------------
# Symptom:
#   yt-dlp repeatedly returned:
#     - "Only images are available" and
#     - "Requested format is not available"
#   across web/tv clients. When cookies were present, android/ios attempts were
#   *skipped* ("client does not support cookies"), so we never actually tried
#   the mobile clients that could still serve HLS.
#
# Root cause:
#   SABR + client/cookie mismatch. Web clients often get SABR’d. Android/iOS
#   can still serve HLS but *only if you do NOT pass cookies*. If you pass
#   cookies, yt-dlp refuses those clients and you loop on web/tv “images only”.
#
# Working solution (that you verified manually):
#   1) Try **android → ios → tv** WITHOUT cookies (and prefer native HLS).
#   2) If those fail, try **tv_embedded → web** WITH cookies-from-browser.
#   3) Keep names by slug; read from a prebuilt `index.for_dl.json` like:
#        { "items":[ { "youtube_url":"https://youtu.be/<id>", "slug":"<slug>" }, ... ] }
#
# TL;DR:
#   - Don’t pass cookies to android/ios/tv on first attempts.
#   - Only attach cookies for tv_embedded/web as a last resort.
#
# -----------------------------------------------------------------------------
# Usage examples
# -----------------------------------------------------------------------------
# export PATCH=2025-10-31-bache-youtube-early
#
# # Both video+audio, using chrome cookies for the final fallbacks:
# python tools/media/download_media.py \
#   --index "build/patch-preview/$PATCH/index.for_dl.json" \
#   --video-dir "build/patch-preview/$PATCH/downloads/video" \
#   --audio-dir "build/patch-preview/$PATCH/downloads/audio" \
#   --browser "chrome:Default" \
#   --mode both \
#   --verbose
#
# Audio only:
# python tools/media/download_media.py --index build/patch-preview/$PATCH/index.for_dl.json \
#   --audio-dir build/patch-preview/$PATCH/downloads/audio --mode audio
#
# Notes:
# - This script does NOT synthesize the slug index. Build it beforehand with jq.
# - It writes a CSV manifest next to the downloads dir: _media_manifest.csv
# -----------------------------------------------------------------------------

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
from collections import Counter
from pathlib import Path
from typing import List, Optional, Tuple

# ------------------------- small utils -------------------------

def info(enabled: bool, msg: str) -> None:
    if enabled:
        print(f"[INFO] {msg}", flush=True)

def warn(msg: str) -> None:
    print(f"[WARN] {msg}", flush=True)

def run(cmd: List[str], verbose: bool=False) -> Tuple[int, str, str]:
    if verbose:
        print("  $", " ".join(cmd), flush=True)
    p = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.returncode, p.stdout, p.stderr

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def repo_rel(p: Optional[Path]) -> str:
    if not p:
        return ""
    try:
        root = Path(__file__).resolve().parents[2]  # repo/
        return str(p.resolve().relative_to(root))
    except Exception:
        return str(p)

# ------------------------- core logic -------------------------

MOBILE_NO_COOKIE_CLIENTS = [
    # Do NOT pass cookies to these:
    "android",
    "ios",
    "tv",           # try tv without cookies before we fall back with cookies
]
COOKIE_FALLBACK_CLIENTS = [
    # These we *do* try with cookies-from-browser, if provided:
    "tv_embedded",
    "web",
]

def load_index(index_path: Path, verbose: bool=False) -> list[dict]:
    if not index_path.exists():
        raise FileNotFoundError(f"index not found: {index_path}")
    data = json.loads(index_path.read_text(encoding="utf-8"))
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError("index must be a list or {items:[...]} at the top level")
    # minimal shape validation
    for it in items:
        if not it.get("youtube_url") or not it.get("slug"):
            raise ValueError("each item must contain youtube_url and slug")
    info(verbose, f"Loaded {len(items)} items from {repo_rel(index_path)}")
    return items

def video_attempts(url: str,
                   out_mp4: Path,
                   browser_cookies: Optional[str],
                   verbose: bool) -> Tuple[bool, str]:
    """
    Try android → ios → tv (no cookies, prefer native HLS),
    then tv_embedded → web (with cookies) if a browser is provided.
    """
    last_tail = ""

    # 1) Mobile-first (no cookies)
    for client in MOBILE_NO_COOKIE_CLIENTS:
        cmd = [
            "yt-dlp",
            "--extractor-args", f"youtube:player_client={client},player_skip=web,web_creator",
            "--hls-prefer-native",
            "-o", str(out_mp4),
            url,
        ]
        rc, so, se = run(cmd, verbose)
        err = (so + "\n" + se)
        last_tail = err[-1200:]
        if out_mp4.exists() and out_mp4.stat().st_size > 0:
            return True, ""
    # 2) Cookie fallbacks (only if browser is provided)
    if browser_cookies:
        for client in COOKIE_FALLBACK_CLIENTS:
            cmd = [
                "yt-dlp",
                "--cookies-from-browser", browser_cookies,
                "--extractor-args", f"youtube:player_client={client}",
                # don't force HLS for web fallback; let yt-dlp decide
                "-o", str(out_mp4),
                url,
            ]
            rc, so, se = run(cmd, verbose)
            err = (so + "\n" + se)
            last_tail = err[-1200:]
            if out_mp4.exists() and out_mp4.stat().st_size > 0:
                return True, ""
    return False, last_tail

def audio_attempts(url: str,
                   out_glob_base: Path,
                   browser_cookies: Optional[str],
                   verbose: bool) -> Tuple[bool, str, Optional[Path]]:
    """
    Same order as video. For audio we -x to mp3 and check the .mp3 exists.
    """
    last_tail = ""

    def mp3_path(base: Path) -> Path:
        return base.parent / (base.name.replace(".%(ext)s", "") + ".mp3")

    # 1) Mobile-first (no cookies)
    for client in MOBILE_NO_COOKIE_CLIENTS:
        cmd = [
            "yt-dlp",
            "-x", "--audio-format", "mp3",
            "--extractor-args", f"youtube:player_client={client},player_skip=web,web_creator",
            "-o", str(out_glob_base),
            url,
        ]
        rc, so, se = run(cmd, verbose)
        err = (so + "\n" + se)
        last_tail = err[-1200:]
        mp3 = mp3_path(out_glob_base)
        if mp3.exists() and mp3.stat().st_size > 0:
            return True, "", mp3

    # 2) Cookie fallbacks
    if browser_cookies:
        for client in COOKIE_FALLBACK_CLIENTS:
            cmd = [
                "yt-dlp",
                "-x", "--audio-format", "mp3",
                "--cookies-from-browser", browser_cookies,
                "--extractor-args", f"youtube:player_client={client}",
                "-o", str(out_glob_base),
                url,
            ]
            rc, so, se = run(cmd, verbose)
            err = (so + "\n" + se)
            last_tail = err[-1200:]
            mp3 = mp3_path(out_glob_base)
            if mp3.exists() and mp3.stat().st_size > 0:
                return True, "", mp3

    return False, last_tail, None

# ------------------------- main -------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download YouTube media by slug using a SABR-resilient client order."
    )
    parser.add_argument("--index", required=True, help="Path to index.for_dl.json (items: [{youtube_url, slug}]).")
    parser.add_argument("--video-dir", help="Directory for MP4 outputs.")
    parser.add_argument("--audio-dir", help="Directory for MP3 outputs.")
    parser.add_argument("--browser", default=None, help="cookies-from-browser value, e.g. chrome:Default (used only for fallbacks).")
    parser.add_argument("--mode", choices=["audio", "video", "both"], default="both")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    index_path = Path(args.index).resolve()
    items = load_index(index_path, verbose=args.verbose)

    # Defaults for out dirs (mirror your patch preview structure if index is inside it)
    if args.video_dir:
        vdir = Path(args.video_dir).resolve()
    else:
        vdir = index_path.parent / "downloads" / "video"
    if args.audio_dir:
        adir = Path(args.audio_dir).resolve()
    else:
        adir = index_path.parent / "downloads" / "audio"

    ensure_dir(vdir)
    ensure_dir(adir)
    info(args.verbose, f"Video dir: {repo_rel(vdir)} | Audio dir: {repo_rel(adir)}")

    manifest_path = (vdir.parent / "_media_manifest.csv").resolve()

    rows: List[dict] = []
    for i, it in enumerate(items, 1):
        url = it["youtube_url"].strip()
        slug = it["slug"].strip()
        print(f"[{i}/{len(items)}] {slug}", flush=True)

        status_parts = []
        v_ok = a_ok = False
        v_err = a_err = ""
        v_path: Optional[Path] = None
        a_path: Optional[Path] = None

        # Video
        if args.mode in ("video", "both"):
            v_path = vdir / f"{slug}.mp4"
            if v_path.exists() and v_path.stat().st_size > 0:
                info(args.verbose, "  video exists, skip")
                v_ok = True
            else:
                ok, tail = video_attempts(url, v_path, args.browser, args.verbose)
                v_ok, v_err = ok, tail
            status_parts.append("video_ok" if v_ok else "video_fail")

        # Audio
        if args.mode in ("audio", "both"):
            # use %(ext)s; we will check the .mp3 afterwards
            a_glob = adir / f"{slug}.%(ext)s"
            expected_mp3 = adir / f"{slug}.mp3"
            if expected_mp3.exists() and expected_mp3.stat().st_size > 0:
                info(args.verbose, "  audio exists, skip")
                a_ok = True
                a_path = expected_mp3
            else:
                ok, tail, found = audio_attempts(url, a_glob, args.browser, args.verbose)
                a_ok, a_err, a_path = ok, tail, found
            status_parts.append("audio_ok" if a_ok else "audio_fail")

        # status
        if args.mode == "video":
            status = "ok:video" if v_ok else "failed:video"
        elif args.mode == "audio":
            status = "ok:audio" if a_ok else "failed:audio"
        else:
            status = "ok:video+audio" if (v_ok and a_ok) else ("ok:video_only" if v_ok else ("ok:audio_only" if a_ok else "failed"))

        rows.append({
            "slug": slug,
            "youtube_url": url,
            "status": status,
            "video_path": repo_rel(v_path) if (v_path and v_path.exists()) else "",
            "audio_path": repo_rel(a_path) if (a_path and a_path.exists()) else "",
            "stderr_tail": (v_err or "")[-600:] + ("\n" if v_err and a_err else "") + (a_err or "")[-600:],
        })

    # write manifest
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["slug", "youtube_url", "status", "video_path", "audio_path", "stderr_tail"])
        w.writeheader()
        w.writerows(rows)

    # summary
    c = Counter(r["status"] for r in rows)
    print("\n=== Media Download Summary ===")
    for k in sorted(c):
        print(f"{k:20s} {c[k]:4d}")
    print(f"Manifest: {repo_rel(manifest_path)}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())