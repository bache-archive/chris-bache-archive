# tools/ — Working Guide

This folder contains the modular pipelines that power the **Chris Bache Archive**.  
Each subfolder corresponds to one stage in the archival process — from intake to preservation.

---

## 📂 Folder Overview

| Subfolder | Purpose |
|------------|----------|
| **intake/** | Discovery and ingestion — find new videos, pull playlists, and download captions (VTT). |
| **curation/** | Curate, deduplicate, and merge new candidates into `index.json`. See [PATCHING.md](../PATCHING.md) for the full patch workflow. |
| **transcripts/** | Build readable, speaker-attributed Markdown transcripts from diarist `.txt` and optional `.srt` files. |
| **alignment/** | Fine-tune timing between captions and diarist text, audit overlaps, and verify cue integrity. |
| **site/** | Build the public HTML site, generate `index.md`, and create sitemaps for search engines. |
| **media/** | Download and sync MP4/MP3 assets via `yt-dlp` and upload or verify Internet Archive mirrors. |
| **preservation/** | Generate per-item manifests, release-level checksums, and verify digital fixity. |
| **rag/** | Research and search layers — chunk transcripts, embed vectors, and build FAISS indexes. |
| **utils/** | Shared helpers (currently empty). |
| **secrets/** | Local OAuth tokens or API keys (ignored by git). |

---

## ⚡ Quickstart — Add a New YouTube Talk

You can do everything with the **Makefile targets** (recommended) or run the scripts directly.
The following steps are identical either way.

### Option A — With `make` (preferred)

```bash
# 1) Add a stub entry to index.json
make add SLUG=2025-10-27-mystic-cosmos \
         YT="https://www.youtube.com/watch?v=XXXXXXXXXXX"

# 2) Fetch captions (VTT)
make captions SLUG=2025-10-27-mystic-cosmos

# 3) Diarize audio with WhisperX + pyannote
make diarize SLUG=2025-10-27-mystic-cosmos \
             AUDIO=downloads/audio/2025-10-27-mystic-cosmos.mp3

# 4) Build the transcript (Markdown with YAML front matter)
make transcript SLUG=2025-10-27-mystic-cosmos

# 5) Regenerate the index page
make index

# 6) Download MP4/MP3 media
make media

# 7) Build and publish the HTML site
make site
make sitemaps
```

Option B — Script-by-script

```bash
# 1) Fetch captions
python3 tools/intake/grab_all_captions.py --index index.json --only 2025-10-27-mystic-cosmos

# 2) Build transcript
printf '%s\n' 2025-10-27-mystic-cosmos > /tmp/bache-worklist.txt
python3 tools/transcripts/rebuild_transcripts.py \
  --root . \
  --missing-file /tmp/bache-worklist.txt \
  --normalize-labels \
  --sync-speakers-yaml \
  --verbose

# 3) Build HTML + sitemaps
python3 tools/site/build_site.py
python3 tools/site/generate_sitemaps.py https://bache-archive.github.io/chris-bache-archive
```


⸻

🔧 What Each Subsystem Does

🧭 intake/
	•	find_bache_videos.py — Discover new videos on YouTube.
	•	yt_playlist_sync.py — Sync or refresh known playlists.
	•	grab_all_captions.py — Download captions (.vtt) for each item.

🗂️ curation/
	•	curate_candidates.py — Clean, dedupe, and normalize candidate lists.
	•	merge_candidates_to_index.py — Merge a patch into index.json.
→ See PATCHING.md￼ for the full process.
	•	migrate_index.py — Upgrade index.json schema if fields change.
	•	dedupe_prefer_timed.py — Choose the most complete timed transcripts.

📝 transcripts/
	•	rebuild_transcripts.py — Build final readable Markdown transcripts from a worklist of diarist basenames.
	•	timeline_from_captions.py / timeline_from_diarist.py — Generate timing JSON for QA or analytics.
	•	normalize_filenames.sh — Normalize diarist/transcript filenames.

⏱ alignment/
	•	align_timecodes_from_vtt_windows.py — Align diarist text to captions.
	•	align_chunks.py, audit_timecodes.py, debug_alignment_scores.py, convert_durations_to_alignment.py — Deep timing/debug utilities.

🌐 site/
	•	build_site.py — Render .md → .html for GitHub Pages.
	•	generate_index_md.py — Build the master index.md listing.
	•	generate_sitemaps.py — Produce sitemap-index.xml and sub-maps.

🎧 media/
	•	download_media.sh — Primary media fetcher.
2025-10 update: rewritten to avoid YouTube SABR restrictions.
→ Order of attempts: android → ios → tv (no cookies), then tv_embedded → web (with cookies).
→ Produces slug-named MP4/MP3 and writes _media_manifest.csv for auditing.
	•	download_media.py — Python equivalent for batch use or cross-platform environments.
	•	ia_sync_media.py — Sync verified files to the Internet Archive.

🗄 preservation/
	•	build_manifests.py — Create per-item provenance manifests.
	•	make_checksums.py / verify_fixity.py — Compute and verify SHA-256 fixity.
	•	tool_versions.json — Logged environment versions for reproducibility.

🔍 rag/
	•	chunk_transcripts.py, embed_and_faiss.py — Build searchable embeddings for research and RAG use.

⸻

🧩 Conventions & Required Fields

Each entry in index.json must include:

Field	Description
youtube_url / youtube_id	Primary identifier
archival_title	Canonical title
channel	Source channel
diarist	Path to diarist TXT
transcript	Path to Markdown transcript
published	ISO date YYYY-MM-DD
source_type	"lecture", "interview", "excerpt", etc.

File naming convention:
YYYY-MM-DD-title-words (slug used across captions, diarist, transcript, and media)

⸻

🔒 Secrets

API credentials (e.g., YouTube API keys or OAuth tokens) live under:

tools/secrets/
  client_secret.json
  token.json

This directory is git-ignored and safe for local use only.

⸻

🧱 Dependencies

Type	Required	Notes
System	python3, jq, yt-dlp, ffmpeg	Required for all media and transcript operations
Python	markdown	Auto-installed via make
Optional	faiss-cpu, pandas, numpy, internetarchive	For RAG and fixity automation


⸻

🧠 Safety & Best Practices
	•	Commit before running batch scripts that modify files (index.json, manifests, etc.).
	•	Use --dry-run whenever available.
	•	Check .vtt health with tools/alignment/check_vtt_health.py.
	•	Keep index.json canonical; treat index.merged.json as staging.
	•	Every edit to index.json or a transcript should have a dated patch under /patches/.

⸻

🪞 Recent Fixes
	•	YouTube SABR workaround (Oct 2025) —
Legacy web clients began returning only thumbnails (“Only images are available”).
The new download_media.sh and download_media.py fix this by using mobile-first clients without cookies.
Verified working on all 2009–2013 Unity Myrtle Beach and SkyBlue talks.

⸻

🧩 Related Documents
	•	PATCHING.md￼ — How to add or update records safely.
	•	PROVENANCE.md — Phase summaries and preservation logs.
	•	Root README.md — Project overview and purpose.
	•	Makefile — All primary automation targets.

⸻

When in doubt: commit your state, run a dry-run, and document every patch.
The goal is not just preservation — but reproducibility across decades.

---

✅ **Why this update matters**

- Keeps your README evergreen (documents the SABR-era fix).  
- Future maintainers will immediately know *why* the Android-first order exists.  
- Adds a clear description of the new Python variant (`download_media.py`).  
- Otherwise leaves your structure and tone untouched.
