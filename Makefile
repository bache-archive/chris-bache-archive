# ------------------------------------------------------------------------------
# Environment & common knobs
# ------------------------------------------------------------------------------
ENV_FILE           := tools/.env
REPORTS_DIR        := reports
QUOTE_PACK_DIR     := $(REPORTS_DIR)/quote_packs
DOCS_EDU_DIR       := docs/educational
ALIGN_SCRIPT       := tools/align_timecodes_from_vtt_windows.py
HARVEST_SCRIPT     := tools/harvest_quote_packs.py
EDU_BUILDER        := tools/build_educational_docs_full.py
PARQUET_PATH       := vectors/bache-talks.embeddings.parquet

# Harvest knobs (override on CLI: make harvest MIN=0.62 MAX=120)
MIN                ?= 0.62
MAX                ?= 120
WITH_TIMECODES     ?= 1

# Alignment knobs (override on CLI if needed)
FULL_REFRESH       ?= 0
ALIGN_USE_PASS_C   ?= 1
ALIGN_THRESH_A     ?= 65
ALIGN_THRESH_B     ?= 55
ALIGN_THRESH_C     ?= 60

# ------------------------------------------------------------------------------
# Init & basics
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
# Checksums & fixity
# ------------------------------------------------------------------------------
# Release metadata
RELEASE            ?= v3.3
CHECKSUMS_DIR      := checksums
ALL_SHA            := checksums.sha256
RELEASE_SHA        := $(CHECKSUMS_DIR)/RELEASE-$(RELEASE).sha256
VERIFY_FIXITY      := tools/verify_fixity.py
FIXITY_LOG         := FIXITY_LOG.md

# What to include in the manifest (files/dirs may be missing; we warn, don’t fail)
FIXITY_TARGETS     := \
	vectors/bache-talks.embeddings.parquet \
	vectors/bache-talks.index.faiss \
	docs/educational \
	reports/quote_packs \
	sources/captions \
	alignments

.PHONY: checksums fixity

# Create a per-release sha256 manifest (portable: shasum on macOS)
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