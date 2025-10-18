# CHANGELOG.md — Chris Bache Archive

All notable updates to the **Chris Bache Archive (2014–2025)** are documented here.
This file complements `POLICIES.md` (rules of practice) and `EDITORIAL_NOTES.md` (specific decisions).
Each entry summarizes what changed, when, and why.

---

## c

---

## v2.5.2 — 2025-10-13

**Metadata Consistency (Markdown)**

- Corrected transcriber/model attribution in **Markdown** transcripts to:
  `Otter.ai (diarized, speaker-attributed) + GPT-5 normalization`.
- Rebuilt per-item manifests and release checksums.
- Verified all 511 files: hashes match (`verify_fixity.py --update`).
- No content changes — metadata/provenance consistency only.

---

## v2.5.1 — 2025-10-13

**Metadata Consistency (HTML) & Indexing polish**

- Fixed transcriber attribution wording across **HTML** transcript pages.
- Minor sitemap/robots polish for search engine submission (no URL changes).
- No transcript content changes.

---

## v2.5 — 2025-10-12

**Fixity & Provenance Layer + Web Publication & Indexing**

### Provenance & Integrity

- Implemented permanent **cryptographic provenance**:
  - 70 per-item manifests in `/manifests/` with SHA-256, sources, tools, license.
  - Global ledger `checksums/RELEASE-v2.4.sha256` (covers 511 files) and `checksums/FIXITY_LOG.md`.
  - Deterministic rebuild + verification scripts: `build_manifests.py`, `verify_fixity.py`.

### Web Publication

- Generated `.html` renderings for all transcripts (`tools/generate_html.py`).
- Published GitHub Pages site with valid `sitemap.xml` and `robots.txt`.
- Submitted sitemap to Google Search Console and Bing Webmaster Tools.
- Verified HTTP 200 and correct MIME types for transcript `.html` and diarist `.txt`.

### Docs

- Updated `README.md` with “Web Publication & Indexing”.
- Added/updated policy notes in `POLICIES.md`.

---

## v2.4 — 2025-10-01

**Transcript Rebuilds from Diarists · Repo Unification · Clean Index**

This release provides version 2.4 of the Chris Bache Archive, a curated collection of transcripts, diarist files, captions, and metadata covering Chris Bache’s talks, interviews, and lectures (2014–2025).

**Key updates in v2.4**

- **Transcripts rebuilt from diarists:** All 68 transcripts regenerated from diarized sources, significantly improving speaker attribution. Earlier versions relied on captions + GPT inference, which sometimes mis-labeled speakers. (Minor residual errors may remain.)
- **Unified transcript paths:** All transcripts now live under `sources/transcripts/` (deprecates older `sources/` locations).
- **`index.json` cleaned:** Normalized filenames; corrected diarist/transcript/media references.
- **New transcript added:** *DMT Entity Encounters — Chapter 9 (Tyringham Hall)*.
- **Captions included:** Where available, original YouTube captions remain in `sources/captions/` for comparison.
- **Diarists preserved:** Raw diarized text files are included for transparency and future reprocessing.

**Notes**

- This bundle **excludes media** (audio/video). Media are preserved via dedicated Internet Archive collections and Zenodo deposit.
- License: **CC0 1.0 Universal** (public domain dedication).

---

## v2.3 — 2025-09-30

**Three New Recordings · Diarist Updates · Archive Re-org**

- Added three recordings (2020-01-10 ECR; 2020-05-13 Ryan & Mo; 2023-06-30 Inbodied Life).
- Added matching Otter.ai diarized transcripts and readable transcript shells.
- Reorganized repository under `sources/transcripts/`.
- Updated `index.json` and `index.md`.
- Standardized naming (`YYYY-MM-DD-slug`); reaffirmed CC0 1.0 Universal.

---

## v2.2.1 — 2025-09-30

**Complete Otter.ai Diarized Transcripts**

- Added remaining diarized `.txt` transcripts with speaker attribution.
- Normalized filenames across layers; updated `README`.
- Audio/video media unchanged since v2.1.1.

---

## v2.2 — 2025-09-29

**Initial Otter.ai Diarized Transcripts**

- Introduced `sources/diarist/` directory with first 10 transcripts.
- Updated `README` to describe three-layer structure (*edited / captions / diarist*).
- Media bundle unchanged (same as v2.1.1).
- Dedicated to CC0 1.0 Universal.

---

## v2.1.1 — 2025-09-29

**First Release with Media Bundle**

- Added complete `downloads/video/` (MP4) + `downloads/audio/` (MP3).
- Published `chris-bache-archive-v2.1.1-media.zip`.
- Added `checksums.sha256`.
- Established full audio/video preservation layer.

---

## v2.1 — 2025-09-29

**Media Automation & Archive Hygiene**

- Added `download_media.sh` (yt-dlp) to automate MP4/MP3 fetch.
- Created `downloads/` substructure and updated `.gitignore`.
- Normalized slugs (fixed punctuation, removed “prof.” period).
- Media managed via Zenodo & Internet Archive.

---

## v2.0 — 2025-09-11

**CC0 Public Domain Dedication**

- All curated text + metadata released under **CC0 1.0 Universal**.
- Source recordings remain © original creators.
- Updated README + LICENSE.
- No text changes — licensing/metadata only.

---

## v1.0.1 — 2025-09-09

**Minor Documentation & Metadata Patch**

- Fixed README links and metadata typos from initial release.
- No content changes.

---

## v1.0 — 2025-09-09

**Initial Public Release**

- First public version of the Chris Bache Archive.
- 59 cleaned transcripts of public talks + raw YouTube captions.
- Licensed **CC BY 4.0** (predecessor to later CC0 dedication).

---

*End of CHANGELOG — maintained by bache-archive (2025-10-13).*
