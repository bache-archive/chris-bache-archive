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
CAPTION_SCRIPT     := tools/grab_all_captions.py
REBUILD_SCRIPT     := tools/rebuild_transcripts_v2.py
INDEX_MD_SCRIPT    := tools/generate_index_md.py
DOWNLOAD_MEDIA_SH  := tools/download_media.sh
BUILD_SITE_PY      := tools/build_site.py
SITEMAPS_PY        := tools/generate_sitemaps.py

# Deps we expect on PATH
SHELL := /bin/bash

# ------------------------------------------------------------------------------
# Init & basics (existing)
# ------------------------------------------------------------------------------
.PHONY: init harvest build-edu audit-parquet rebuild-parquet
init:
	@[ -f $(ENV_FILE) ] || cp tools/.env.example $(ENV_FILE)
	@echo ">> Edit $(ENV_FILE) with real hosts/keys."

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
	@python3 - <<'PY'
import pandas as pd, os
PARQ=os.environ.get("PARQ","$(PARQUET_PATH)")
df=pd.read_parquet(PARQ)
def stats(g, T=120):
    s=g["start_sec"].dropna()
    if s.empty: return (0,0,0,0)
    mx=int(s.max()); return (len(g), int((s>=mx-T).sum()), mx, int(s.value_counts().max()))
rows=[]
for tid,g in df.groupby("talk_id"):
    n,t,mx,md = stats(g)
    if n>=5 and t/n>=0.20:
        rows.append((tid,n,t,100*t/n,md,mx))
rows.sort(key=lambda x:-x[3])
print("== Tail concentrations (>=20% in last 120s) ==")
for tid,n,t,p,md,mx in rows[:15]:
    hh=f"{mx//3600:02d}:{(mx%3600)//60:02d}:{mx%60:02d}"
    print(f"- {tid:64} n={n:4d} tail={t:3d} ({p:5.1f}%) max_dupe={md} max={hh}")
PY

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
.PHONY: help add captions diarist transcript index media site sitemaps publish quick

help:
	@echo "Usage:"
	@echo "  make add SLUG=<yyyy-mm-dd-title> YT=<youtube_url>"
	@echo "  make captions SLUG=<slug>"
	@echo "  make diarist SLUG=<slug>"
	@echo "  make transcript SLUG=<slug>"
	@echo "  make index"
	@echo "  make media"
	@echo "  make site"
	@echo "  make sitemaps ROOT_URL=$(ROOT_URL)"
	@echo "  make publish"
	@echo "  make quick SLUG=<slug> YT=<youtube_url>"

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
	     "type": "interview",
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

# Reminder to drop Otter exports
diarist:
	@echo "↳ Place diarist exports at:"
	@echo "   - $(DIAR_TXT)"
	@echo "   - (optional) $(DIAR_SRT)"

# Build transcript markdown from diarist + index metadata
transcript:
	@test -f "$(REBUILD_SCRIPT)" || { echo "ERROR: $(REBUILD_SCRIPT) not found"; exit 1; }
	@echo ">> Building transcript for $(SLUG)"
	@python3 "$(REBUILD_SCRIPT)" \
	  --root . \
	  --only "$(SLUG)" \
	  --normalize-labels \
	  --sync-speakers-yaml \
	  --verbose \
	  --out-dir sources/transcripts

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
	@python3 - <<'PY' || true
import importlib, sys
try:
    importlib.import_module("markdown")
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "markdown"])
PY
	@test -f "$(BUILD_SITE_PY)" || { echo "ERROR: $(BUILD_SITE_PY) not found"; exit 1; }
	@python3 "$(BUILD_SITE_PY)"

# Generate sitemaps for GitHub Pages
sitemaps:
	@test -f "$(SITEMAPS_PY)" || { echo "ERROR: $(SITEMAPS_PY) not found"; exit 1; }
	@echo ">> Generating sitemaps for $(ROOT_URL)"
	@python3 "$(SITEMAPS_PY)" "$(ROOT_URL)"

# One-shot: add → captions → diarist reminder → transcript → index
quick: add captions diarist transcript index
	@echo ">> Quick flow completed for $(SLUG)"