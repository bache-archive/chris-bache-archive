# ------------------------------------------------------------------------------
# Environment & common knobs (existing)
# ------------------------------------------------------------------------------
ENV_FILE           := tools/.env
REPORTS_DIR        := reports
QUOTE_PACK_DIR     := $(REPORTS_DIR)/quote_packs
DOCS_EDU_DIR       := docs/educational
ALIGN_SCRIPT       := tools/align_timecodes_from_vtt_windows.py
HARVEST_SCRIPT     := tools/harvest_quote_packs.py
EDU_BUILDER        := tools/build_educational_docs_full.py
PARQUET_PATH       := vectors/bache-talks.embeddings.parquet

# Harvest knobs
MIN                ?= 0.62
MAX                ?= 120
WITH_TIMECODES     ?= 1

# Alignment knobs
FULL_REFRESH       ?= 0
ALIGN_USE_PASS_C   ?= 1
ALIGN_THRESH_A     ?= 65
ALIGN_THRESH_B     ?= 55
ALIGN_THRESH_C     ?= 60

# ------------------------------------------------------------------------------
# New: ingest/publish knobs & paths
# ------------------------------------------------------------------------------
# Inputs when adding a new talk
SLUG ?= 2025-01-01-sample-talk
YT   ?= https://www.youtube.com/watch?v=XXXXXXXXXXX

# Core files/paths
INDEX_JSON         := index.json
DIAR_TXT           := sources/diarist/$(SLUG).txt
DIAR_SRT           := sources/diarist/$(SLUG).srt
TRANSCRIPT_MD      := sources/transcripts/$(SLUG).md
ROOT_URL           ?= https://bache-archive.github.io/chris-bache-archive

# Script paths
CAPTION_SCRIPT     := tools/intake/grab_all_captions.py
DIARIZE_SCRIPT     := tools/diarist/diarize_talk.py
REBUILD_SCRIPT     := tools/transcripts/rebuild_transcripts.py
INDEX_MD_SCRIPT    := tools/site/generate_index_md.py
DOWNLOAD_MEDIA_SH  := tools/media/download_media.sh
BUILD_SITE_PY      := tools/site/build_site.py
SITEMAPS_PY        := tools/site/generate_sitemaps.py
PREPARE_YT_BATCH   := tools/intake/prepare_youtube_batch.py
FETCH_YT_METADATA  := tools/intake/fetch_youtube_metadata.py
PROMOTE_YT_BATCH   := tools/intake/promote_youtube_batch.py
FIND_YT_VIDEOS     := tools/intake/find_bache_videos.py
YT_PLAYLIST_SYNC   := tools/intake/yt_playlist_sync.py
SUMMARIZE_YT_BATCH := tools/intake/summarize_youtube_batch.py
SPEAKER_REF_SCRIPT := tools/speakers/build_reference_manifest.py
SPEAKER_CLIPS_SCRIPT := tools/speakers/extract_reference_clips.py
SPEAKER_IDENTIFY_SCRIPT := tools/speakers/identify_speakers.py
BATCH_OUT          ?= patches/2026-07-12-youtube-public-batch
BATCH_URLS         ?= $(BATCH_OUT)/inputs/urls.txt
DISCOVERY_OUT      ?= reports/youtube-discovery/$(shell date +%F)
DISCOVERY_AFTER    ?=
DISCOVERY_BEFORE   ?=
DISCOVERY_MAX_PER_QUERY ?= 20
DISCOVERY_MIN_SCORE ?= 2
PLAYLIST_ID        ?=
PLAYLIST_EXTRA     ?= --dry-run
FETCH_ONLY_NEW     ?= 1
PROMOTE_POLICY     ?= operator-supplied
AUDIO_ONLY         ?=
AUDIO              ?= downloads/audio/$(SLUG).mp3
DIAR_OUT           ?= sources/diarist
DIAR_PYTHON        ?= python3
DIAR_LANGUAGE      ?= en
DIAR_MODEL         ?= large-v3
DIAR_NUM_SPEAKERS  ?=
DIAR_LEXICON       ?= data/diarist/lexicon.yml
DIAR_PROMPT        ?= data/diarist/initial_prompt.txt
DIAR_EXTRA         ?=
SPEAKER_REF_MANIFEST ?= data/speakers/chris_bache.reference_manifest.json
SPEAKER_REF_CLIPS ?= build/speaker-reference-clips/chris_bache
SPEAKER_REPORT ?= reports/diarization/$(SLUG).speaker_identity.json
SPEAKER_PYTHON ?= python3
TRANSCRIPT_PYTHON ?= python3

# Deps we expect on PATH
SHELL := /bin/bash
VENV ?= .venv
PYTHON ?= $(VENV)/bin/python
ENSURE_VENV := test -x "$(PYTHON)" || python3 -m venv "$(VENV)"
ENSURE_MARKDOWN := $(ENSURE_VENV); "$(PYTHON)" -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('markdown') else 1)" || "$(PYTHON)" -m pip install markdown

# ------------------------------------------------------------------------------
# Init & basics (existing)
# ------------------------------------------------------------------------------
.PHONY: init harvest build-edu audit-parquet rebuild-parquet identity-audit
init:
	@[ -f $(ENV_FILE) ] || cp tools/.env.example $(ENV_FILE)
	@echo ">> Edit $(ENV_FILE) with real hosts/keys."

identity-audit:
	@python3 tools/identity_audit.py

# Safe harvest: removes only machine-generated quote packs; preserves curated docs.
harvest:
	@echo ">> Clearing machine-generated quote packs at $(QUOTE_PACK_DIR)"
	@rm -rf "$(QUOTE_PACK_DIR)"
	@echo ">> Running harvest (min=$(MIN), max=$(MAX), with_timecodes=$(WITH_TIMECODES))"
	@python3 "$(HARVEST_SCRIPT)" \
	  --out "$(QUOTE_PACK_DIR)" \
	  --min-score "$(MIN)" \
	  --max-items "$(MAX)" \
	  $(if $(filter 1,$(WITH_TIMECODES)),--with-timecodes,)

# Build only the markdown pages from per-topic sources.json
build-edu:
	@echo ">> Building educational docs from per-topic sources.json"
	@python3 "$(EDU_BUILDER)"

# Full realign to rebuild the Parquet timecodes (then quick audit)
rebuild-parquet:
	@echo ">> FULL realign to rebuild $(PARQUET_PATH)"
	@FULL_REFRESH=1 ALIGN_USE_PASS_C=$(ALIGN_USE_PASS_C) \
	 ALIGN_THRESH_A=$(ALIGN_THRESH_A) ALIGN_THRESH_B=$(ALIGN_THRESH_B) ALIGN_THRESH_C=$(ALIGN_THRESH_C) \
	 python3 "$(ALIGN_SCRIPT)"
	@$(MAKE) audit-parquet

# Lightweight parquet sanity (tail clustering / max-second dupes)
audit-parquet:
	@PARQ="$(PARQUET_PATH)" python3 tools/rag/audit_parquet.py

# ------------------------------------------------------------------------------
# Checksums & fixity (existing)
# ------------------------------------------------------------------------------
RELEASE            ?= v3.3
CHECKSUMS_DIR      := checksums
ALL_SHA            := checksums.sha256
RELEASE_SHA        := $(CHECKSUMS_DIR)/RELEASE-$(RELEASE).sha256
VERIFY_FIXITY      := tools/verify_fixity.py
FIXITY_LOG         := FIXITY_LOG.md

# Include in release manifest (warn if missing, don't fail)
FIXITY_TARGETS     := \
	vectors/bache-talks.embeddings.parquet \
	vectors/bache-talks.index.faiss \
	docs/educational \
	reports/quote_packs \
	sources/captions \
	alignments

.PHONY: checksums fixity
checksums:
	@mkdir -p "$(CHECKSUMS_DIR)"
	@echo ">> Writing $(RELEASE_SHA)"
	@rm -f "$(RELEASE_SHA)"
	@set -e; \
	for p in $(FIXITY_TARGETS); do \
		if [ -e "$$p" ]; then \
			if [ -d "$$p" ]; then \
				find "$$p" -type f -print0 | xargs -0 shasum -a 256 >> "$(RELEASE_SHA)"; \
			else \
				shasum -a 256 "$$p" >> "$(RELEASE_SHA)"; \
			fi; \
		else \
			echo "WARN: missing $$p" >&2; \
		fi; \
	done
	@echo ">> Updating $(ALL_SHA)"
	@shasum -a 256 "$(RELEASE_SHA)" >> "$(ALL_SHA)"
	@echo "OK: wrote $(RELEASE_SHA) and appended to $(ALL_SHA)"

fixity: $(RELEASE_SHA)
	@test -f "$(VERIFY_FIXITY)" || { echo "ERROR: $(VERIFY_FIXITY) not found."; exit 1; }
	@echo ">> Running fixity verification against $(RELEASE_SHA)"
	@python3 "$(VERIFY_FIXITY)" --manifest "$(RELEASE_SHA)" --log "$(FIXITY_LOG)"
	@echo ">> Appended results to $(FIXITY_LOG)"

# ------------------------------------------------------------------------------
# New: YouTube → captions → diarist → transcript → index → media → site
# ------------------------------------------------------------------------------
.PHONY: help install-ingest-deps find-youtube-candidates prepare-youtube-batch fetch-youtube-metadata promote-youtube-batch merge-youtube-batch-preview captions-from-batch audio-from-batch youtube-batch-status playlist-sync speaker-reference speaker-reference-clips speaker-identify add captions diarize diarist transcript index media site sitemaps publish quick

help:
	@echo "Usage:"
	@echo "  make install-ingest-deps"
	@echo "  make find-youtube-candidates DISCOVERY_AFTER=YYYY-MM-DD DISCOVERY_BEFORE=YYYY-MM-DD"
	@echo "  make prepare-youtube-batch BATCH_URLS=<urls.txt> BATCH_OUT=<patch-dir>"
	@echo "  make fetch-youtube-metadata BATCH_URLS=<urls.txt> BATCH_OUT=<patch-dir>  # defaults to new IDs only"
	@echo "  make promote-youtube-batch BATCH_OUT=<patch-dir> PROMOTE_POLICY=operator-supplied|heuristic"
	@echo "  make merge-youtube-batch-preview BATCH_OUT=<patch-dir>"
	@echo "  make captions-from-batch BATCH_OUT=<patch-dir>"
	@echo "  make audio-from-batch BATCH_OUT=<patch-dir> AUDIO_ONLY=<slug-or-youtube-id>"
	@echo "  make youtube-batch-status BATCH_OUT=<patch-dir>"
	@echo "  make playlist-sync PLAYLIST_ID=<playlist-id> PLAYLIST_EXTRA='--dry-run'"
	@echo "  make speaker-reference"
	@echo "  make speaker-reference-clips"
	@echo "  make speaker-identify SLUG=<slug> AUDIO=<path-to-audio.mp3>"
	@echo "  make add SLUG=<yyyy-mm-dd-title> YT=<youtube_url>  # legacy stub; prefer patch workflow"
	@echo "  make captions SLUG=<slug>"
	@echo "  make diarize SLUG=<slug> AUDIO=<path-to-audio.mp3>"
	@echo "  make diarize SLUG=<slug> AUDIO=<path-to-audio.mp3> DIAR_MODEL=tiny DIAR_EXTRA='--asr-only'"
	@echo "  make diarist SLUG=<slug>  # legacy placement reminder"
	@echo "  make transcript SLUG=<slug>"
	@echo "  make index"
	@echo "  make media"
	@echo "  make site"
	@echo "  make sitemaps ROOT_URL=$(ROOT_URL)"
	@echo "  make publish"
	@echo "  make quick SLUG=<slug> YT=<youtube_url>"

install-ingest-deps:
	@$(ENSURE_VENV)
	@"$(PYTHON)" -m pip install -r requirements.txt

# Discover likely new public Chris Bache YouTube videos. Outputs stay ignored
# under reports/ until a human or agent promotes reviewed URLs into patches/.
find-youtube-candidates:
	@test -f "$(FIND_YT_VIDEOS)" || { echo "ERROR: $(FIND_YT_VIDEOS) not found"; exit 1; }
	@mkdir -p "$(DISCOVERY_OUT)"
	@set -e; \
	after_arg=""; before_arg=""; \
	if [ -n "$(DISCOVERY_AFTER)" ]; then after_arg="--published-after $(DISCOVERY_AFTER)"; fi; \
	if [ -n "$(DISCOVERY_BEFORE)" ]; then before_arg="--published-before $(DISCOVERY_BEFORE)"; fi; \
	set -a; [ ! -f .env ] || source .env; set +a; \
	"$(PYTHON)" "$(FIND_YT_VIDEOS)" \
	  --index "$(INDEX_JSON)" \
	  --max-per-query "$(DISCOVERY_MAX_PER_QUERY)" \
	  --min-score "$(DISCOVERY_MIN_SCORE)" \
	  $$after_arg $$before_arg \
	  --out-json "$(DISCOVERY_OUT)/candidates.bache.youtube.json" \
	  --out-csv "$(DISCOVERY_OUT)/candidates.bache.youtube.csv"

# Offline-safe URL normalization and duplicate check for a public YouTube batch.
prepare-youtube-batch:
	@test -f "$(PREPARE_YT_BATCH)" || { echo "ERROR: $(PREPARE_YT_BATCH) not found"; exit 1; }
	@test -f "$(BATCH_URLS)" || { echo "ERROR: $(BATCH_URLS) not found"; exit 1; }
	@python3 "$(PREPARE_YT_BATCH)" \
	  --urls "$(BATCH_URLS)" \
	  --index "$(INDEX_JSON)" \
	  --out-dir "$(BATCH_OUT)"

# Fetch public metadata and create a review-only draft patch. Does not mutate index.json.
fetch-youtube-metadata: prepare-youtube-batch
	@test -f "$(FETCH_YT_METADATA)" || { echo "ERROR: $(FETCH_YT_METADATA) not found"; exit 1; }
	@set -e; \
	urls_file="$(BATCH_OUT)/inputs/urls.normalized.txt"; \
	if [ "$(FETCH_ONLY_NEW)" = "1" ] && [ -s "$(BATCH_OUT)/work/new_video_ids.txt" ]; then \
	  urls_file="$(BATCH_OUT)/work/new_video_ids.txt"; \
	fi; \
	python3 "$(FETCH_YT_METADATA)" \
	  --urls "$$urls_file" \
	  --out-dir "$(BATCH_OUT)"

promote-youtube-batch:
	@test -f "$(PROMOTE_YT_BATCH)" || { echo "ERROR: $(PROMOTE_YT_BATCH) not found"; exit 1; }
	@test -f "$(BATCH_OUT)/work/index.patch.metadata.json" || { echo "ERROR: $(BATCH_OUT)/work/index.patch.metadata.json not found"; exit 1; }
	@python3 "$(PROMOTE_YT_BATCH)" \
	  --batch-out "$(BATCH_OUT)" \
	  --index "$(INDEX_JSON)" \
	  --policy "$(PROMOTE_POLICY)"

merge-youtube-batch-preview:
	@test -f "$(BATCH_OUT)/work/index.patch.json" || { echo "ERROR: $(BATCH_OUT)/work/index.patch.json not found; run make promote-youtube-batch first"; exit 1; }
	@python3 tools/curation/merge_index.py \
	  --base "$(INDEX_JSON)" \
	  --patch "$(BATCH_OUT)/work/index.patch.json" \
	  --out "$(BATCH_OUT)/outputs/index.merged.json"

captions-from-batch:
	@test -f "$(BATCH_OUT)/work/index.patch.json" || { echo "ERROR: $(BATCH_OUT)/work/index.patch.json not found; run make promote-youtube-batch first"; exit 1; }
	@python3 "$(CAPTION_SCRIPT)" \
	  --index "$(BATCH_OUT)/work/index.patch.json" \
	  --only-from-patch "$(BATCH_OUT)/work/index.patch.json"
	@mkdir -p "$(BATCH_OUT)/outputs"
	@if [ -f sources/captions/_captions_manifest.csv ]; then cp sources/captions/_captions_manifest.csv "$(BATCH_OUT)/outputs/captions_manifest.csv"; fi

audio-from-batch:
	@test -f "$(BATCH_OUT)/work/download.index.json" || { echo "ERROR: $(BATCH_OUT)/work/download.index.json not found; run make promote-youtube-batch first"; exit 1; }
	@set -e; \
	only_arg=""; \
	if [ -n "$(AUDIO_ONLY)" ]; then only_arg="--only $(AUDIO_ONLY)"; fi; \
	python3 tools/media/download_media.py \
	  --index "$(BATCH_OUT)/work/download.index.json" \
	  --mode audio \
	  --audio-dir downloads/audio \
	  $$only_arg
	@mkdir -p "$(BATCH_OUT)/outputs"
	@if [ -f "$(BATCH_OUT)/work/downloads/_media_manifest.csv" ]; then cp "$(BATCH_OUT)/work/downloads/_media_manifest.csv" "$(BATCH_OUT)/outputs/media_manifest.csv"; fi

youtube-batch-status:
	@test -f "$(SUMMARIZE_YT_BATCH)" || { echo "ERROR: $(SUMMARIZE_YT_BATCH) not found"; exit 1; }
	@"$(PYTHON)" "$(SUMMARIZE_YT_BATCH)" "$(BATCH_OUT)"

# Idempotently preview or sync the archive YouTube playlist from index.json.
# Default is dry-run; pass PLAYLIST_EXTRA= to apply additions, or
# PLAYLIST_EXTRA='--reorder' to enforce ordering.
playlist-sync:
	@test -f "$(YT_PLAYLIST_SYNC)" || { echo "ERROR: $(YT_PLAYLIST_SYNC) not found"; exit 1; }
	@set -e; \
	id_arg=""; \
	if [ -n "$(PLAYLIST_ID)" ]; then id_arg="--playlist-id $(PLAYLIST_ID)"; fi; \
	"$(PYTHON)" "$(YT_PLAYLIST_SYNC)" $$id_arg $(PLAYLIST_EXTRA)

# Build non-audio speaker reference metadata from reviewed timecoded diarist files.
speaker-reference:
	@test -f "$(SPEAKER_REF_SCRIPT)" || { echo "ERROR: $(SPEAKER_REF_SCRIPT) not found"; exit 1; }
	@python3 "$(SPEAKER_REF_SCRIPT)" --out "$(SPEAKER_REF_MANIFEST)"

# Extract local reference clips when source audio is present. Outputs are ignored.
speaker-reference-clips: speaker-reference
	@test -f "$(SPEAKER_CLIPS_SCRIPT)" || { echo "ERROR: $(SPEAKER_CLIPS_SCRIPT) not found"; exit 1; }
	@python3 "$(SPEAKER_CLIPS_SCRIPT)" \
	  --manifest "$(SPEAKER_REF_MANIFEST)" \
	  --out-dir "$(SPEAKER_REF_CLIPS)"

# Compare diarized speaker clusters against the reviewed Chris reference clips.
speaker-identify:
	@test -f "$(SPEAKER_IDENTIFY_SCRIPT)" || { echo "ERROR: $(SPEAKER_IDENTIFY_SCRIPT) not found"; exit 1; }
	@test -f "sources/diarist/$(SLUG).json" || { echo "ERROR: sources/diarist/$(SLUG).json not found"; exit 1; }
	@"$(SPEAKER_PYTHON)" "$(SPEAKER_IDENTIFY_SCRIPT)" \
	  --audio "$(AUDIO)" \
	  --diarization-json "sources/diarist/$(SLUG).json" \
	  --reference-clips "$(SPEAKER_REF_CLIPS)/clips_manifest.json" \
	  --out "$(SPEAKER_REPORT)"

# Append a stub record into index.json
add:
	@test -f "$(INDEX_JSON)" || { echo "ERROR: $(INDEX_JSON) not found"; exit 1; }
	@command -v jq >/dev/null || { echo "ERROR: jq is required"; exit 1; }
	@echo ">> Adding stub for $(SLUG)"
	@tmp=$$(mktemp); \
	jq --arg slug "$(SLUG)" \
	   --arg yt   "$(YT)" \
	   '. += [{
	     "archival_title": ($$slug | gsub("-"; " ") ),
	     "published": (($$slug | capture("^(?<d>\\d{4}-\\d{2}-\\d{2})")).d // ""),
	     "channel": "",
	     "source_type": "interview",
	     "youtube_url": $$yt,
	     "youtube_id": ($$yt | capture("(?:v=|/shorts/|/embed/|youtu\\.be/)(?<id>[A-Za-z0-9_-]{11})").id // ""),
	     "diarist": "sources/diarist/\($$slug).txt",
	     "transcript": "sources/transcripts/\($$slug).md",
	     "file": "sources/transcripts/\($$slug).md"
	   }]' "$(INDEX_JSON)" > $$tmp && mv $$tmp "$(INDEX_JSON)"
	@echo "OK: added to $(INDEX_JSON). Edit title/channel as needed."

# Fetch VTT (scoped to SLUG)
captions:
	@test -f "$(CAPTION_SCRIPT)" || { echo "ERROR: $(CAPTION_SCRIPT) not found"; exit 1; }
	@echo ">> Downloading captions for $(SLUG)"
	@python3 "$(CAPTION_SCRIPT)" --index "$(INDEX_JSON)" --only "$(SLUG)"

# Run the current local diarization path: WhisperX ASR + pyannote speaker turns.
diarize:
	@test -f "$(DIARIZE_SCRIPT)" || { echo "ERROR: $(DIARIZE_SCRIPT) not found"; exit 1; }
	@test -f "$(AUDIO)" || { echo "ERROR: audio not found: $(AUDIO)"; exit 1; }
	@mkdir -p "$(DIAR_OUT)"
	@echo ">> Diarizing $(AUDIO) -> $(DIAR_OUT)/$(SLUG).{txt,srt,json}"
	@extra=""; \
	if [ -n "$(DIAR_NUM_SPEAKERS)" ]; then extra="$$extra --num-speakers $(DIAR_NUM_SPEAKERS)"; fi; \
	if [ -f "$(DIAR_LEXICON)" ]; then extra="$$extra --lexicon $(DIAR_LEXICON)"; fi; \
	if [ -f "$(DIAR_PROMPT)" ]; then extra="$$extra --initial-prompt-file $(DIAR_PROMPT)"; fi; \
	"$(DIAR_PYTHON)" "$(DIARIZE_SCRIPT)" \
	  --input "$(AUDIO)" \
	  --out "$(DIAR_OUT)" \
	  --basename "$(SLUG)" \
	  --language "$(DIAR_LANGUAGE)" \
	  --whisper-model "$(DIAR_MODEL)" \
	  $$extra $(DIAR_EXTRA)

# Legacy reminder for external diarist exports.
diarist:
	@echo "↳ Legacy external-diarist placement:"
	@echo "   - $(DIAR_TXT)"
	@echo "   - (optional) $(DIAR_SRT)"
	@echo "↳ Preferred current path: make diarize SLUG=$(SLUG) AUDIO=<path-to-audio.mp3>"

# Build transcript markdown from diarist + index metadata
transcript:
	@test -f "$(REBUILD_SCRIPT)" || { echo "ERROR: $(REBUILD_SCRIPT) not found"; exit 1; }
	@echo ">> Building transcript for $(SLUG)"
	@set -e; \
	tmp=$$(mktemp); \
	printf '%s\n' "$(SLUG)" > "$$tmp"; \
	"$(TRANSCRIPT_PYTHON)" "$(REBUILD_SCRIPT)" \
	  --root . \
	  --missing-file "$$tmp" \
	  --normalize-labels \
	  --sync-speakers-yaml \
	  --verbose; \
	rm -f "$$tmp"

# Regenerate index.md from index.json
index:
	@test -f "$(INDEX_MD_SCRIPT)" || { echo "ERROR: $(INDEX_MD_SCRIPT) not found"; exit 1; }
	@echo ">> Generating index.md"
	@python3 "$(INDEX_MD_SCRIPT)"

# Download MP4/MP3 for all index entries
media:
	@test -f "$(DOWNLOAD_MEDIA_SH)" || { echo "ERROR: $(DOWNLOAD_MEDIA_SH) not found"; exit 1; }
	@command -v yt-dlp >/dev/null || { echo "ERROR: yt-dlp is required"; exit 1; }
	@command -v jq >/dev/null || { echo "ERROR: jq is required"; exit 1; }
	@echo ">> Downloading media for entries in $(INDEX_JSON)"
	@bash "$(DOWNLOAD_MEDIA_SH)"

# Build HTML site (uses Python-Markdown)
site:
	@echo ">> Building site"
	@$(ENSURE_MARKDOWN)
	@test -f "$(BUILD_SITE_PY)" || { echo "ERROR: $(BUILD_SITE_PY) not found"; exit 1; }
	@"$(PYTHON)" "$(BUILD_SITE_PY)"

# Generate sitemaps for GitHub Pages
sitemaps:
	@test -f "$(SITEMAPS_PY)" || { echo "ERROR: $(SITEMAPS_PY) not found"; exit 1; }
	@echo ">> Generating sitemaps for $(ROOT_URL)"
	@python3 "$(SITEMAPS_PY)" "$(ROOT_URL)"

# Legacy one-shot: only for already staged diarist text. Prefer the patch workflow.
quick: add captions diarist transcript index
	@echo ">> Legacy quick flow completed for $(SLUG). Prefer docs/END_TO_END_PUBLIC_VIDEO_INGESTION.md for production."

# ------------------------------------------------------------------------------
# Finalization (simple one-command build + verify)
# ------------------------------------------------------------------------------
RELEASE_VERSION ?= v3.5.4

.PHONY: finalize
finalize:
	@echo ">> Rebuilding site..."
	@$(ENSURE_MARKDOWN)
	@"$(PYTHON)" tools/site/build_site.py
	@echo ">> Regenerating sitemaps..."
	@python3 tools/site/generate_sitemaps.py
	@echo ">> Rebuilding checksums for $(RELEASE_VERSION)..."
	@python3 tools/preservation/make_checksums.py --version $(RELEASE_VERSION) --verify --no-downloads
	@echo ">> Rebuilding JSON release manifest..."
	@python3 tools/preservation/build_manifests_from_checksums.py \
	  --checksums checksums/RELEASE-$(RELEASE_VERSION).sha256 \
	  --version $(RELEASE_VERSION)
	@echo ">> Verifying fixity..."
	@python3 tools/preservation/verify_fixity.py --manifest manifests/release-$(RELEASE_VERSION).json
	@echo ""
	@echo "✅ Finalization complete — site + sitemaps + checksums + fixity verified."
	@echo "Results logged in checksums/FIXITY_LOG.md"
