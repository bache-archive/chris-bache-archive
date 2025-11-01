#!/bin/zsh
set -euo pipefail

# ---------- Config ----------
PATCH="${PATCH:-2025-10-31-bache-youtube}"
INDEX_FILE="${INDEX_FILE:-patches/$PATCH/outputs/index.merged.json}"
PATCH_JSON="${PATCH_JSON:-patches/$PATCH/work/index.patch.json}"   # optional filter
DOWNLOADS_ROOT="${DOWNLOADS_ROOT:-build/patch-preview/$PATCH/downloads}"
VIDEO_DIR="$DOWNLOADS_ROOT/video"
AUDIO_DIR="$DOWNLOADS_ROOT/audio"
MODE="${MODE:-audio}"   # audio | video | both
BROWSER="${BROWSER:-chrome:Default}"  # chrome|firefox|safari or profile (e.g., chrome:Default)

# ---------- Checks ----------
echo "Checking for required tools (jq, yt-dlp)..."
command -v jq >/dev/null 2>&1 || { echo "Install jq: brew install jq"; exit 1; }
command -v yt-dlp >/dev/null 2>&1 || { echo "Install yt-dlp: brew install yt-dlp"; exit 1; }

[[ -f "$INDEX_FILE" ]] || { echo "Error: index not found: $INDEX_FILE"; exit 1; }

mkdir -p "$VIDEO_DIR" "$AUDIO_DIR"
echo "Output dirs: $VIDEO_DIR  $AUDIO_DIR"
echo "----------------------------------------------------"

# ---------- Build selection ----------
# Read index (array or {items:[]}) and optionally restrict to patch items.
if [[ -f "$PATCH_JSON" ]]; then
  echo "Using patch filter: $PATCH_JSON"
  # Collect allowed ids from patch (id/slug/youtube_id/transcript stem)
  ALLOW_IDS=$(jq -r '
    ( . as $root
      | if type=="array" then . else (.items // .entries // []) end
    ) as $items
    | $items[]
    | [
        (.id // ""),
        (.slug // ""),
        (.youtube_id // ""),
        ((.transcript // "") | capture("([^/]+)\\.md$").captures[0].string? // "")
      ] | .[]
    ' "$PATCH_JSON" | awk 'NF' | sort -u)

  # Build list from index, filtered by ALLOW_IDS
  MAP_CMD='
    def items(x):
      if (x|type)=="array" then x else (x.items // []) end;
    def base_of(i):
      if (i.youtube_id // "") != "" then i.youtube_id
      elif (i.transcript // "") | test("([^/]+)\\.md$") then (i.transcript | capture("([^/]+)\\.md$").captures[0].string)
      elif (i.slug // "") != "" then i.slug
      elif (i.id // "") != "" then i.id
      else null end;
    items(.)[]
    | {url: (.youtube_url // ("https://youtu.be/" + (.youtube_id // ""))), base: base_of(.)}
    | select(.url != null and .base != null)
  '
  # shell → jq array of allowed ids
  ALLOW_JSON=$(printf '%s\n' $ALLOW_IDS | jq -R . | jq -s .)
  SELECTION=$(jq -cr --argjson allow "$ALLOW_JSON" '
    '"$MAP_CMD"' | select( [ .base ] | inside($allow) or (.[] as $x | ($allow|index($x))) )
  ' "$INDEX_FILE")
else
  echo "No patch filter provided (PATCH_JSON missing); using full index."
  MAP_CMD='
    def items(x):
      if (x|type)=="array" then x else (x.items // []) end;
    def base_of(i):
      if (i.youtube_id // "") != "" then i.youtube_id
      elif (i.transcript // "") | test("([^/]+)\\.md$") then (i.transcript | capture("([^/]+)\\.md$").captures[0].string)
      elif (i.slug // "") != "" then i.slug
      elif (i.id // "") != "" then i.id
      else null end;
    items(.)[]
    | {url: (.youtube_url // ("https://youtu.be/" + (.youtube_id // ""))), base: base_of(.)}
    | select(.url != null and .base != null)
  '
  SELECTION=$(jq -cr "$MAP_CMD" "$INDEX_FILE")
fi

TOTAL_ITEMS=$(printf '%s\n' "$SELECTION" | wc -l | tr -d ' ')
CURRENT_ITEM=0

# ---------- Helpers ----------
dl_audio() {
  local url="$1" out="$2"
  # Try sequence of client modes to dodge SABR; cookies on web clients
  local clients=("web" "web_creator" "mweb" "tv" "tv_embedded")
  for client in "${clients[@]}"; do
    echo "      [audio] client=$client"
    yt-dlp -x --audio-format mp3 \
      --no-overwrites --continue \
      --geo-bypass-country US \
      --sleep-requests 1 --min-sleep-interval 1 --max-sleep-interval 3 \
      --concurrent-fragments 1 --force-ipv4 \
      --cookies-from-browser "$BROWSER" \
      --extractor-args "youtube:player_client=$client" \
      -o "$out" "$url" && return 0
  done
  return 1
}

dl_video() {
  local url="$1" out="$2"
  local clients=("web" "web_creator" "mweb" "tv" "tv_embedded")
  for client in "${clients[@]}"; do
    echo "      [video] client=$client"
    yt-dlp \
      -f 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best' \
      --no-overwrites --continue \
      --geo-bypass-country US \
      --sleep-requests 1 --min-sleep-interval 1 --max-sleep-interval 3 \
      --concurrent-fragments 1 --force-ipv4 \
      --cookies-from-browser "$BROWSER" \
      --extractor-args "youtube:player_client=$client" \
      -o "$out" "$url" && return 0
  done
  return 1
}

# ---------- Loop ----------
echo "Starting downloads (MODE=$MODE, BROWSER=$BROWSER)"
echo "----------------------------------------------------"

printf '%s\n' "$SELECTION" | while IFS= read -r row; do
  [[ -z "$row" ]] && continue
  CURRENT_ITEM=$((CURRENT_ITEM + 1))
  url=$(jq -r '.url' <<<"$row")
  base=$(jq -r '.base' <<<"$row")

  echo "[$CURRENT_ITEM/$TOTAL_ITEMS] $base"
  [[ -z "$url" || -z "$base" ]] && { echo "  - skip: missing url/base"; echo "----------------------------------------------------"; continue; }

  # Video
  if [[ "$MODE" == "video" || "$MODE" == "both" ]]; then
    vout="$VIDEO_DIR/$base.mp4"
    if [[ -f "$vout" ]]; then
      echo "  - video exists, skip"
    else
      echo "  - downloading video → $vout"
      if ! dl_video "$url" "$vout"; then
        echo "    [WARN] video failed for $base"
      fi
    fi
  fi

  # Audio
  if [[ "$MODE" == "audio" || "$MODE" == "both" ]]; then
    aout="$AUDIO_DIR/$base.mp3"
    if [[ -f "$aout" ]]; then
      echo "  - audio exists, skip"
    else
      echo "  - downloading audio → $aout"
      if ! dl_audio "$url" "$aout"; then
        echo "    [WARN] audio failed for $base"
      fi
    fi
  fi

  echo "----------------------------------------------------"
done

echo "✅ Done. Check: $DOWNLOADS_ROOT"