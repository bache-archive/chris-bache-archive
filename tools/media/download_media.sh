#!/bin/zsh
# tools/media/download_media.sh
# -----------------------------------------------------------------------------
# Context / Why this exists
# -----------------------------------------------------------------------------
# PROBLEM WE HIT:
# - yt-dlp kept returning "Only images are available" and "Requested format is not available"
#   across web/tv clients. When cookies were present, android/ios attempts were skipped
#   ("client does not support cookies"), so we never actually tried the mobile clients.
# - Root cause: SABR + client/cookie mismatch. Web clients often get SABR’d; android/ios
#   can still serve HLS but *only if you do NOT pass cookies*. Passing cookies to them
#   causes yt-dlp to skip those clients.
#
# WORKING SOLUTION:
# - Try **android → ios → tv** *without cookies* first (mobile-first).
# - If those fail, fall back to **tv_embedded → web** *with cookies from browser*.
# - Keep names by slug and read from a simple index `index.for_dl.json`:
#     { "items":[ { "youtube_url":"https://youtu.be/<id>", "slug":"<slug>" }, ... ] }
#
# SUMMARY:
# - Don’t pass cookies to android/ios/tv on first attempts.
# - Only attach cookies for tv_embedded/web as a last resort.
#
# -----------------------------------------------------------------------------
# Usage
# -----------------------------------------------------------------------------
#   PATCH=2025-10-31-bache-youtube-early MODE=both BROWSER="chrome:Default" \
#   ./tools/media/download_media.sh
#
# Vars:
#   PATCH    : patch folder name (used for default paths)
#   INDEX    : path to index.for_dl.json (defaults to build/patch-preview/$PATCH/index.for_dl.json)
#   MODE     : audio | video | both   (default: both)
#   BROWSER  : browser for cookies, e.g. chrome:Default | firefox | safari (used only at fallback)
#
# Pre-step (if you don’t already have index.for_dl.json):
#   jq '{items: [(if type=="array" then . else (.items // .entries // []) end)[]
#       | select(.youtube_id and .slug)
#       | {youtube_url: ("https://youtu.be/" + .youtube_id), slug: .slug}] }' \
#     "patches/$PATCH/work/index.patch.json" > "build/patch-preview/$PATCH/index.for_dl.json"
#
# -----------------------------------------------------------------------------

set -euo pipefail

# ---------- Config ----------
PATCH="${PATCH:-2025-10-31-bache-youtube-early}"
INDEX="${INDEX:-build/patch-preview/$PATCH/index.for_dl.json}"
MODE="${MODE:-both}"                       # audio | video | both
BROWSER="${BROWSER:-chrome:Default}"       # used only for tv_embedded/web fallbacks

OUT_ROOT="build/patch-preview/$PATCH/downloads"
VID_DIR="$OUT_ROOT/video"
AUD_DIR="$OUT_ROOT/audio"

# ---------- Checks ----------
command -v jq >/dev/null 2>&1 || { echo "Install jq (e.g., brew install jq)"; exit 1; }
command -v yt-dlp >/dev/null 2>&1 || { echo "Install yt-dlp (e.g., brew install yt-dlp)"; exit 1; }
mkdir -p "$VID_DIR" "$AUD_DIR"
[[ -f "$INDEX" ]] || { echo "Missing index: $INDEX"; exit 1; }

# ---------- Per-item runner ----------
run_one() {
  local url="$1" slug="$2"
  local vout="$VID_DIR/${slug}.mp4"
  local aout_base="$AUD_DIR/${slug}.%(ext)s"

  echo "=== $slug ==="

  # ---- VIDEO (mobile-first, NO cookies; then fallback WITH cookies) ----
  if [[ "$MODE" == "video" || "$MODE" == "both" ]]; then
    if [[ ! -s "$vout" ]]; then
      yt-dlp --extractor-args "youtube:player_client=android,player_skip=web,web_creator" \
             --hls-prefer-native -o "$vout" "$url" \
      || yt-dlp --extractor-args "youtube:player_client=ios,player_skip=web,web_creator" \
                --hls-prefer-native -o "$vout" "$url" \
      || yt-dlp --extractor-args "youtube:player_client=tv,player_skip=web,web_creator" \
                --hls-prefer-native -o "$vout" "$url" \
      || yt-dlp --cookies-from-browser "$BROWSER" \
                --extractor-args "youtube:player_client=tv_embedded" \
                --hls-prefer-native -o "$vout" "$url" \
      || yt-dlp --cookies-from-browser "$BROWSER" \
                --extractor-args "youtube:player_client=web" \
                -o "$vout" "$url" \
      || echo "[WARN] video failed for $slug"
    else
      echo "  video exists, skip"
    fi
  fi

  # ---- AUDIO (mp3; same client order) ----
  if [[ "$MODE" == "audio" || "$MODE" == "both" ]]; then
    if [[ ! -f "$AUD_DIR/${slug}.mp3" ]]; then
      yt-dlp -x --audio-format mp3 \
             --extractor-args "youtube:player_client=android,player_skip=web,web_creator" \
             -o "$aout_base" "$url" \
      || yt-dlp -x --audio-format mp3 \
                --extractor-args "youtube:player_client=ios,player_skip=web,web_creator" \
                -o "$aout_base" "$url" \
      || yt-dlp -x --audio-format mp3 \
                --extractor-args "youtube:player_client=tv,player_skip=web,web_creator" \
                -o "$aout_base" "$url" \
      || yt-dlp -x --audio-format mp3 \
                --cookies-from-browser "$BROWSER" \
                --extractor-args "youtube:player_client=tv_embedded" \
                -o "$aout_base" "$url" \
      || yt-dlp -x --audio-format mp3 \
                --cookies-from-browser "$BROWSER" \
                --extractor-args "youtube:player_client=web" \
                -o "$aout_base" "$url" \
      || echo "[WARN] audio failed for $slug"
    else
      echo "  audio exists, skip"
    fi
  fi

  echo "------------------------"
}

# ---------- Run ----------
echo "Reading: $INDEX"
echo "Out:     $VID_DIR | $AUD_DIR"
echo "Mode:    $MODE"
echo "Browser: $BROWSER (fallback only)"
echo "----------------------------------------------------"

while IFS=$'\t' read -r url slug; do
  [[ -z "$url" || -z "$slug" ]] && continue
  run_one "$url" "$slug"
done < <(jq -r '.items[] | [.youtube_url, .slug] | @tsv' "$INDEX")

echo "✅ Done. Check $OUT_ROOT"