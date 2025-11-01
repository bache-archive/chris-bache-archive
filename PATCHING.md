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
6) **Ingest & build** → captions → diarist → transcript → media → site → checksums/manifests  
7) **Commit** everything with a clear message

---

## Where Things Live

tools/
intake/ → discovery & caption fetch  
curation/ → dedupe & merge  
media/ → download audio/video (yt-dlp)  
preservation/ → fixity & manifests  
site/ → build HTML site  

Typical patch workspace:

patches/
20251031/
inputs/
candidates.bache.youtube.csv
candidates.bache.youtube.json
urls.txt
work/
index.patch.json
outputs/
index.merged.json
logs/

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

patches/20251031/work/index.patch.json

Example (2025 schema with media paths):

[
  {
    "youtube_id": "NtcLJ3_Ceyc",
    "title": "2013-11-16, Dr. Chris Bache, Guest Speaker, 'No Fear of Death' (Part 3/3)",
    "channel": "Unity Myrtle Beach",
    "source_type": "talk",
    "published": "2013-11-17",
    "slug": "2013-11-17-no-fear-of-death-part-3-unity-myrtle-beach",
    "media": {
      "audio": "downloads/audio/2013-11-17-no-fear-of-death-part-3-unity-myrtle-beach.mp3",
      "video": "downloads/video/2013-11-17-no-fear-of-death-part-3-unity-myrtle-beach.mp4"
    }
  }
]

✅ New in 2025:
Including media.audio and media.video fields is now recommended.
These ensure that the download_media.sh / download_media.py tools name outputs consistently.

Keep patches small and focused; omit fields unchanged from index.json.

⸻

Step 3 — Merge the Patch

Generate a reviewable merged index (does not overwrite index.json yet):

mkdir -p patches/20251031
python tools/curation/merge_candidates_to_index.py \
  --index index.json \
  --patch patches/20251031/work/index.patch.json \
  --out patches/20251031/outputs/index.merged.json \
  --prefer-newer

Flags:
	•	--prefer-newer keeps newer metadata where conflicts exist.
	•	Use --dry-run to preview actions (if supported).

⸻

Step 4 — Review the Merge

Spot-check the diff:

git diff --no-index index.json patches/20251031/outputs/index.merged.json | less

Look for:
	•	Accidental removals
	•	Duplicate youtube_id
	•	Wrong media paths or missing slugs

⸻

Step 5 — Adopt the Merge

Once verified:

cp patches/20251031/outputs/index.merged.json index.json
git add index.json patches/20251031/work/index.patch.json patches/20251031/outputs/index.merged.json
git commit -m "Patch index.json: add/update items (2025-10-31 batch)"


⸻

Step 6 — Run the Ingest & Build Pipelines

6.1 Captions (VTT)

python tools/intake/grab_all_captions.py --index index.json --only <slug>

6.2 Diarist

Export from Otter or equivalent to:

sources/diarist/<slug>.txt
sources/diarist/<slug>.srt  # optional

6.3 Transcript (Markdown)

python tools/transcripts/rebuild_transcripts_v2.py \
  --root . \
  --only <slug> \
  --normalize-labels \
  --sync-speakers-yaml \
  --verbose \
  --out-dir sources/transcripts

6.4 Media (updated 2025 method)

# Recommended new version (Android-first fallback system)
bash tools/media/download_media.sh
# or
python tools/media/download_media.py

Both use mobile-first extraction order to avoid YouTube’s SABR restrictions
(android → ios → tv → tv_embedded → web) and save slug-named MP4/MP3 files under build/patch-preview/.

6.5 Site & Sitemaps

python tools/site/build_site.py
python tools/site/generate_index_md.py
python tools/site/generate_sitemaps.py https://bache-archive.github.io/chris-bache-archive

6.6 Preservation (checksums & manifests)

python tools/preservation/make_checksums.py
python tools/preservation/build_manifests.py


⸻

Updating Existing Records

For corrections (titles, channels, or dates), include only the changed fields (plus youtube_id or slug) in a fresh patch.
Then repeat Steps 3–5.
This keeps the history atomic and reviewable.

⸻

QA & Gotchas
	•	Duplicates: dedupes by youtube_id.
	•	Slugs drift: update paths everywhere if slug changes.
	•	Status field: optional "pending" → "ready".
	•	SABR issues: if a video fails, re-run media download with the mobile-first script (Oct 2025 fix).
	•	Check fixity: run preservation tools after each batch merge.

⸻

Rollback Strategy

git checkout -- index.json
# or
git revert <commit-sha>


⸻

Commit Message Templates
	•	Patch index.json: add N items, update M items (YYYY-MM-DD batch)
	•	Ingest & publish: <slug> (captions→diarist→transcript→site→checksums)
	•	Fix metadata: <slug> (channel/title/published)

⸻

Appendix — Minimal Fields Cheat Sheet

Required
	•	youtube_id / youtube_url
	•	title
	•	channel
	•	source_type
	•	published
	•	slug
	•	media.audio, media.video

Nice to have
	•	status
	•	duration_hms
	•	notes

Keep patches small, dated, and reproducible.
The patch → merge → review → adopt cycle ensures long-term provenance and clarity.

⸻

