# CHANGELOG.md — Chris Bache Archive

All notable updates to the **Chris Bache Archive (2014 – 2025)** are documented here.  
This file complements `POLICIES.md` (rules of practice) and `EDITORIAL_NOTES.md` (specific decisions).  
Each entry summarizes what changed, when, and why.

---

## [v2.4] — 2025-10-12  
**Fixity & Provenance Layer — “Trust the Object”**

### Added
- Implemented permanent **cryptographic provenance layer (MANIFEST + Checksums)**  
  - 511 files hashed and verified (100 % match).  
  - 70 per-item manifests created in `/manifests/` describing file paths, SHA-256 hashes, capture date, source URLs, tools, and license.  
  - Global ledger `checksums/RELEASE-v2.4.sha256` and fixity log `checksums/FIXITY_LOG.md` added.  
  - Verified determinism by rebuilding manifests; no diffs on same-day re-run.  
- Introduced new directory structure:  

checksums/   → release-level hashes + verification log
manifests/   → per-item provenance records
tools/       → automation scripts

### Documentation
- Added documentation set:  
- `POLICIES.md` — rules of practice (v1.0)  
- `EDITORIAL_NOTES.md` — interpretive log (v1.0)  
- `CHANGELOG.md` — this file (v1.0)  
- `ETHOS.md` — intent & guiding principles (v1.0)  
- Updated `README.md` to reflect the new integrity layer and documentation map.

### Known issues
- All transcripts still list `model: gpt-o3` in front-matter (incorrect).  
Actual model: **GPT-5 (OpenAI, 2025)**.  
To be corrected in v2.5.

### Outcome
Every object in the archive now has a verifiable digital fingerprint and a clear provenance trail.  
Future curators and AIs can recompute hashes to confirm authenticity.

---

## [v2.3] — 2025-09-01  
**Three New Recordings · Diarist Updates · Archive Re-org**

### Added
- Three new recordings:  
- `2020-01-10 · Prof. Dr. Christopher Bache about his work and consciousness (ECR)`  
- `2020-05-13 · EP.6 – LSD and the Mind of the Universe (Ryan & Mo)`  
- `2023-06-30 · Learning to be Gods (Inbodied Life w/ Lauren Taus)`  

### Changed
- Added diarized Otter.ai transcripts for all new items (`sources/diarist/`).  
- Created matching readable transcript placeholders (`sources/transcripts/`).  
- Reorganized repository: all transcript files now live under `sources/transcripts/`.  
- Updated `index.json` + `index.md` with full metadata tables.  
- README revised to show 62 transcripts, 61 captions, and new diarist layer.

### Integrity
- Naming convention standardized: `YYYY-MM-DD-title-slug`.  
- CC0 1.0 Universal dedication reaffirmed.  
- Media files excluded from Git; preserved via Zenodo + Internet Archive bundles.

---

## [v2.2.1] — 2025-07-xx  
**Complete Otter.ai Diarized Transcripts**

- Added remaining diarized `.txt` transcripts with automated speaker attribution.  
- Normalized filenames across captions / transcripts / media / diarist layers.  
- Updated README to reflect full diarist coverage.  
- Audio/video media unchanged since v2.1.1.

---

## [v2.2] — 2025-06-xx  
**Initial Otter.ai Diarized Transcripts**

- Introduced `sources/diarist/` directory with first 10 diarized transcripts.  
- Updated README to describe new three-layer structure:  
*edited / captions / diarist* + media mirrors.  
- Media bundle unchanged (see v2.1.1).  
- All curated materials dedicated to CC0 1.0 Universal.

---

## [v2.1.1] — 2025-05-xx  
**First Release with Media Bundle**

- Added complete `downloads/video/` (MP4) + `downloads/audio/` (MP3).  
- Published companion bundle `chris-bache-archive-v2.1.1-media.zip`.  
- Included `checksums.sha256` for file verification.  
- Established full audio/video preservation layer alongside transcripts.  

---

## [v2.1] — 2025-05-xx  
**Media Automation & Archive Hygiene**

- Added `download_media.sh` (using yt-dlp) to automate MP4/MP3 fetch.  
- Created `downloads/` substructure and updated `.gitignore`.  
- Normalized slugs (fixed punctuation, removed “prof.” period).  
- Media now managed externally via Zenodo & Internet Archive.  

---

## [v2.0] — 2025-04-xx  
**CC0 Public Domain Dedication**

- All curated text + metadata released under CC0 1.0 Universal.  
- Source recordings remain © their original creators.  
- README + LICENSE updated accordingly.  
- No transcript text altered; purely licensing and metadata change.

---

## [v1.x → v1.9] — 2024 – Early 2025  
**Foundation & Metadata Hygiene**

- Initial releases included 59 cleaned transcripts + raw captions.  
- Fixed duration formats in `index.json`.  
- Standardized HH:MM:SS fields and metadata consistency.  
- Laid groundwork for modernized archive structure.

---

## [v1.0] — 2024-Early  
**Initial Release**

- First public version of the Chris Bache Archive.  
- 59 cleaned transcripts of public talks + raw YouTube captions.  
- Licensed CC BY 4.0 (precursor to later CC0 dedication).

---

*End of CHANGELOG — maintained by bache-archive (2025-10-12).*
