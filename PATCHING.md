# PATCHING.md — Adding/Updating Items via Patch Files

This document explains the **safe, repeatable** way to bring new videos into the archive (or fix existing records) without hand-editing `index.json`.  
You’ll create a small **patch file**, merge it into a **proposed merged index**, review, and then run the standard pipelines (captions → diarist → transcript → site → preservation).

---

## TL;DR — Happy Path

1) **Discover candidates** → write CSV/JSON  
2) **Author a patch** (`index.patch.json`) with only the new/changed records  
3) **Merge** → produce `index.merged.json`  
4) **Review** → diff merged vs current; spot-check a few items  
5) **Adopt** → replace `index.json` with the merged file  
6) **Ingest & build** → captions → diarist → transcript → site → checksums/manifests  
7) **Commit** everything with a clear message

---

## Where Things Live

tools/
intake/
find_bache_videos.py         # discovery helpers (YouTube, playlists, etc.)
grab_all_captions.py         # VTT fetcher
yt_playlist_sync.py          # bulk import/refresh from playlists

curation/
curate_candidates.py         # normalize/dedupe candidate lists
merge_candidates_to_index.py # merges patch JSON → merged index
migrate_index.py             # structural migrations if schema changes
candidates/
YYYYMMDD/
candidates.bache.youtube.csv
candidates.bache.youtube.json
patches/
YYYYMMDD/
index.patch.json         # minimal records to add/update
index.merged.json        # result of merge (for review, not source of truth)

site/ (build output lives under build/site/)
sources/
captions/                      # VTT
diarist/                       # .txt (.srt optional)
transcripts/                   # .md (final source of truth for HTML)

> If you currently have `candidates.*` or `index.*.json` at repo root, feel free to move them under `tools/curation/...` with `git mv` for neatness.

---

## Step 1 — Discover Candidates

Use the discovery script(s) to pull candidate videos into a dated folder:

```bash
# create a dated workspace
mkdir -p tools/curation/candidates/20251031
python tools/intake/find_bache_videos.py \
  --query "Christopher Bache" \
  --out-csv tools/curation/candidates/20251031/candidates.bache.youtube.csv \
  --out-json tools/curation/candidates/20251031/candidates.bache.youtube.json

Optionally normalize or dedupe:

python tools/curation/curate_candidates.py \
  --in tools/curation/candidates/20251031/candidates.bache.youtube.json \
  --out tools/curation/candidates/20251031/candidates.bache.youtube.json


⸻

Step 2 — Author a Patch

Create a minimal index.patch.json that contains only the entries you are adding or updating.

Place it at:

tools/curation/patches/20251031/index.patch.json

Patch Entry Schema (minimal & recommended)

[
  {
    "youtube_id": "IBCN4z5P-8s",
    "youtube_url": "https://youtu.be/IBCN4z5P-8s",
    "archival_title": "PSA Fireside Chat Featuring Dr. Raymond Turpin & Dr. Chris Bache",
    "channel": "Psychedelic Society of Asheville (PSA)",
    "source_type": "interview",
    "published": "2025-10-21",

    "transcript": "sources/transcripts/2025-10-21-psa-fireside-chat.md",
    "diarist": "sources/diarist/2025-10-21-psa-fireside-chat.txt",

    "status": "pending",
    "notes": "Auto-imported candidate; not yet diarized or verified."
  }
]

Naming convention (slug): YYYY-MM-DD-title-words ⇒ keep transcript & diarist paths aligned to the slug you’ll actually create.

You do not need to copy every field that exists in index.json. Keep the patch small and focused.

⸻

Step 3 — Merge the Patch

Generate a reviewable merged index (does not overwrite index.json yet):

mkdir -p tools/curation/patches/20251031
python tools/curation/merge_candidates_to_index.py \
  --index index.json \
  --patch tools/curation/patches/20251031/index.patch.json \
  --out tools/curation/patches/20251031/index.merged.json \
  --prefer-newer

Flags:
	•	--prefer-newer keeps newer published or imported_at metadata where conflicts exist.
	•	Use --dry-run (if available) to preview actions.

⸻

Step 4 — Review the Merge

Spot-check the diff:

git diff --no-index index.json tools/curation/patches/20251031/index.merged.json | less

Look for:
	•	Accidental removals
	•	Duplicates of the same youtube_id
	•	Path mistakes (sources/transcripts/... slugs, extensions)

⸻

Step 5 — Adopt the Merge

Once you’re satisfied:

cp tools/curation/patches/20251031/index.merged.json index.json
git add index.json tools/curation/patches/20251031/index.patch.json tools/curation/patches/20251031/index.merged.json
git commit -m "Patch index.json: add/update items (2025-10-31 batch)"


⸻

Step 6 — Run the Ingest & Build Pipelines

6.1 Captions (VTT)

python tools/intake/grab_all_captions.py --index index.json --only IBCN4z5P-8s
# or by slug:
# python tools/intake/grab_all_captions.py --index index.json --only 2025-10-21-psa-fireside-chat

6.2 Diarist

Export from Otter (or your diarist) and save as:

sources/diarist/2025-10-21-psa-fireside-chat.txt
# optional SRT:
sources/diarist/2025-10-21-psa-fireside-chat.srt

6.3 Transcripts (Markdown)

python tools/transcripts/rebuild_transcripts_v2.py \
  --root . \
  --only 2025-10-21-psa-fireside-chat \
  --normalize-labels \
  --sync-speakers-yaml \
  --verbose \
  --out-dir sources/transcripts

6.4 Media (optional)

bash tools/media/download_media.sh

6.5 Site & Sitemaps

python tools/site/build_site.py
python tools/site/generate_index_md.py
python tools/site/generate_sitemaps.py https://bache-archive.github.io/chris-bache-archive

6.6 Preservation (checksums/manifests)

python tools/preservation/make_checksums.py
python tools/preservation/build_manifests.py

Commit the outputs you track in git:

git add sources/captions sources/diarist sources/transcripts build/site/ checksums/ manifests/ index.md
git commit -m "Ingest & publish: 2025-10-21 PSA fireside chat (captions→diarist→transcript→site→checksums)"
git push


⸻

Updating Existing Records

For corrections (titles, channels, paths, dates, etc.), put only the changed fields (plus the key: youtube_id or transcript path) into a new index.patch.json, then repeat Steps 3–5.
This ensures a clean audit trail of what changed and when.

⸻

QA & Gotchas
	•	Duplicates: The merge script dedupes by youtube_id when present. If missing, it may attempt URL or slug matching—prefer adding youtube_id.
	•	Slugs drift: If you change a slug after creating diarist/transcript files, update the patch to keep paths consistent.
	•	Status field: Use "pending" until diarist and transcript exist; switch to "ready" (or omit) after publish.
	•	Shorts/Excerpts: Set "source_type": "excerpt" and keep durations accurate; short clips don’t need diarist if captions are clean.
	•	Timing issues: Run tools/alignment/check_vtt_health.py and alignment helpers if the final HTML looks out of sync.

⸻

Rollback Strategy

Did the merge introduce a problem?

# Restore the previous index.json from git:
git checkout -- index.json

# Or revert the commit:
git log --oneline
git revert <commit-sha>


⸻

Make Targets (Optional)

If you prefer make, wire these shortcuts into your Makefile:

PATCH_DATE ?= $(shell date +%Y%m%d)

patch-merge:
	python tools/curation/merge_candidates_to_index.py \
	  --index index.json \
	  --patch tools/curation/patches/$(PATCH_DATE)/index.patch.json \
	  --out tools/curation/patches/$(PATCH_DATE)/index.merged.json \
	  --prefer-newer

captions:
	python tools/intake/grab_all_captions.py --index index.json --only $(SLUG)

transcript:
	python tools/transcripts/rebuild_transcripts_v2.py \
	  --root . \
	  --only $(SLUG) \
	  --normalize-labels --sync-speakers-yaml --verbose \
	  --out-dir sources/transcripts

site:
	python tools/site/build_site.py
	python tools/site/generate_index_md.py

sitemaps:
	python tools/site/generate_sitemaps.py https://bache-archive.github.io/chris-bache-archive


⸻

Commit Message Templates
	•	Patch applied (index only)
Patch index.json: add N items, update M items (YYYY-MM-DD batch)
	•	Full ingest
Ingest & publish: <slug> (captions→diarist→transcript→site→checksums)
	•	Fixes
Fix metadata: <slug> (channel/title/published)

⸻

Appendix — Minimal Fields Cheat Sheet

Required for new items
	•	youtube_id and/or youtube_url
	•	archival_title
	•	channel
	•	source_type (lecture | interview | excerpt)
	•	published (YYYY-MM-DD)
	•	diarist (future path)
	•	transcript (future path)

Nice to have
	•	duration_hms
	•	status (pending → remove or set ready after publish)
	•	notes

Keep patches small, dated, and reviewable. The patch → merge → review → adopt loop protects index.json and makes provenance obvious to future maintainers.


