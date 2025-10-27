tools/ — Working Guide

This folder contains the scripts that power the Chris Bache Archive pipelines:
	•	Ingest new YouTube talks (discover → captions/VTT → diarist)
	•	Build readable transcripts
	•	Publish HTML + sitemaps for GitHub Pages
	•	Preserve manifests & checksums
	•	Research helpers (alignment, chunking, embeddings, quote packs)

If you’re here to add a new YouTube talk, start with the Quickstart below.

⸻

Quickstart: Add a New YouTube Talk

You can do everything with the Makefile targets (recommended) or directly with the scripts. The steps are identical either way.

Option A — With make (preferred)

# 1) Add a new entry to index.json (creates a stub with required fields)
make add SLUG=2025-10-27-mystic-cosmos YT="https://www.youtube.com/watch?v=XXXXXXXXXXX"

# 2) Fetch captions (VTT) for just this item
make captions SLUG=2025-10-27-mystic-cosmos

# 3) Export diarist TXT (and optional SRT) from Otter
#    Save them as:
#      sources/diarist/2025-10-27-mystic-cosmos.txt
#      sources/diarist/2025-10-27-mystic-cosmos.srt  (optional)

# 4) Build the readable transcript (Markdown with front matter)
make transcript SLUG=2025-10-27-mystic-cosmos

# 5) Regenerate the index page (index.md)
make index

# 6) Download MP4/MP3 media for all items in index.json
make media

# 7) Publish the site: build HTML and sitemaps for GitHub Pages
make site
make sitemaps

Option B — Script-by-script

# 1) Add a stub entry (or edit index.json by hand)
#    Ensure fields: youtube_url, diarist, transcript, file, archival_title, published
#    (The Makefile's `add` target uses jq to write a correctly shaped record.)

# 2) Download captions (VTT)
python tools/grab_all_captions.py --index index.json --only 2025-10-27-mystic-cosmos

# 3) Place diarist files
#    sources/diarist/2025-10-27-mystic-cosmos.txt
#    sources/diarist/2025-10-27-mystic-cosmos.srt (optional)

# 4) Build the transcript (writes to sources/transcripts/)
python tools/rebuild_transcripts_v2.py \
  --root . \
  --only 2025-10-27-mystic-cosmos \
  --normalize-labels \
  --sync-speakers-yaml \
  --verbose \
  --out-dir sources/transcripts

# 5) Regenerate index.md
python tools/generate_index_md.py

# 6) Download media
bash tools/download_media.sh

# 7) Build site + sitemaps
python tools/build_site.py
python tools/generate_sitemaps.py https://bache-archive.github.io/chris-bache-archive


⸻

What Each Script Does (and When to Use It)

Ingest & Registration
	•	yt_playlist_sync.py
Pull or refresh YouTube playlist items into index.json. Use when seeding or catching up with a channel/playlist.
	•	grab_all_captions.py
Download captions (.vtt) for entries in index.json. Supports --index, --only <slug|youtube_id>, --force.

Diarist & Transcript Build
	•	rebuild_transcripts_v2.py
Generates polished, speaker-attributed Markdown transcripts from diarist .txt (and optionally .srt), using metadata from index.json. Typical flags:
--root, --only <slug>, --normalize-labels, --sync-speakers-yaml, --verbose, --out-dir sources/transcripts.
	•	timeline_from_captions.py / timeline_from_diarist.py
Produce JSON timelines from VTT or diarist text. Useful for QA, alignment, or downstream analytics.
	•	check_vtt_health.py
Quick validation for broken VTTs (overlaps, malformed cues).
	•	audit_timecodes.py, align_timecodes_from_vtt_windows.py, align_chunks.py, convert_durations_to_alignment.py, debug_alignment_scores.py
Advanced timing/alignment tools. Use these only if you notice sync issues.

Indexing & Site
	•	generate_index_md.py
Builds (or refreshes) the human-readable index.md listing from index.json.
	•	build_site.py
Renders sources/transcripts/*.md into HTML under the site output (typically public/) for GitHub Pages.
	•	generate_sitemaps.py
Produces sitemap-index.xml and sub-sitemaps for search engines.

Media & Preservation
	•	download_media.sh
Downloads MP4/MP3 via yt-dlp for all entries in index.json. Requires that each entry contains youtube_url and a file path; the basename of file is used for file naming. Depends on jq, yt-dlp, and ffmpeg.
	•	build_manifests.py
Creates per-item manifests (metadata + hashes) for provenance.
	•	make_checksums.py / verify_fixity.py
Compute and verify release-level SHA-256 checksums across important directories.

Research, RAG & Educational
	•	chunk_transcripts.py / embed_and_faiss.py
Optional search stack: chunk transcripts and build FAISS indexes for local/RAG search.
	•	align_timecodes_from_vtt_windows.py (also listed above)
The main alignment routine for better diarist/captions sync.
	•	harvest_quote_packs.py, build_educational_docs_full.py
Build educational “quote packs” and synthesize topic pages from curated sources (used by make harvest and make build-edu).
	•	generate_sitemaps.py, generate_index_md.py
Improve discoverability (sitemaps) and keep repo indices tidy.

⸻

Conventions & Required Fields
	•	index.json (minimum useful fields per entry):
	•	youtube_url (and ideally youtube_id)
	•	diarist: sources/diarist/<slug>.txt
	•	transcript: sources/transcripts/<slug>.md
	•	file: sources/transcripts/<slug>.md (used by download_media.sh for naming)
	•	Recommended: archival_title, published (YYYY-MM-DD), channel, type
	•	Filenames:
	•	SLUG format: YYYY-MM-DD-title-words
	•	Diarist: sources/diarist/<slug>.txt (+ optional .srt)
	•	Transcript: sources/transcripts/<slug>.md
	•	Captions: sources/captions/<slug>.vtt
	•	Front matter:
	•	Transcripts include YAML front matter (title, date, channel, themes). Keep IDs stable across rebuilds.

⸻

Dependencies
	•	System: python3, jq, yt-dlp, ffmpeg
	•	Python: markdown (for build_site.py), plus standard libs used across tools
	•	Optional: faiss-cpu, pandas, numpy, internetarchive (for advanced features)

Tip: The Makefile attempts to install markdown if missing.

⸻

Safety & Troubleshooting
	•	Dry runs: Many scripts support -h/--help. Use it before running on the whole corpus.
	•	Side effects: Some scripts write in-place. Keep a clean working tree (commit first).
	•	VTT issues: Run check_vtt_health.py after downloading captions; if timing looks off in the final transcript, explore the align_* tools.
	•	Media failures: Ensure youtube_url exists in index.json and yt-dlp is up to date (yt-dlp -U).

⸻

Typical One-Liners
	•	Add & ingest in one go (then drop the diarist TXT and rebuild transcript):

make quick SLUG=2025-10-27-mystic-cosmos YT="https://www.youtube.com/watch?v=XXXXXXXXXXX"

	•	Rebuild transcript after fixing diarist TXT:

make transcript SLUG=2025-10-27-mystic-cosmos

	•	Full publish step:

make site && make sitemaps

	•	Release checksums & fixity:

make checksums RELEASE=v3.3
make fixity


⸻

FAQ

Q: Do I have to use the Makefile?
A: No—every step can be run with the individual scripts. The Makefile just wires them together with sensible defaults.

Q: Where do I edit titles/channels?
A: In index.json. The add target writes a reasonable stub; you can refine fields there before building the transcript and site.

Q: I have an .srt from Otter—should I include it?
A: Optional but helpful. Place it at sources/diarist/<slug>.srt. The builder can use it to improve timing.
