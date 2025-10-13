# POLICIES.md — Chris Bache Archive  
Version: 1.1  
Date: 2025-10-13  
Maintainer: bache-archive@tuta.com  

---

## 1. Purpose
This document defines the editorial, technical, and publication policies governing all materials in the Chris Bache Archive.  
Its goal is to make every transcript’s **origin, transformation, and publication pipeline** transparent, reproducible, and auditable across time.

---

## 2. Source Hierarchy
All transcript text derives from publicly available audio or video recordings (2014 – 2025).

1. **Primary source:** Otter.ai diarized transcript exports (`sources/diarist/`)  
2. **Secondary source:** YouTube auto-captions (`sources/captions/`) when diarized text unavailable  
3. **Derived output:** Machine-generated readable transcripts (`sources/transcripts/`) created by **GPT-5 (OpenAI, 2025)** using the diarized Otter.ai exports as input.  
   - No full human editorial review has yet occurred.  
   - Speaker attributions and paragraph boundaries come from Otter.ai diarization.  
   - Transcript readability improvements were limited to mechanical normalization (punctuation, casing, filler removal).

---

## 3. Normalization Policy
Machine processing used the following normalization rules (prompt-level instructions applied to GPT-5):

- Preserve speaker order and attributions from Otter.ai.  
- Remove non-semantic filler words (“um,” “uh,” “you know”).  
- Correct punctuation and capitalization where unambiguous.  
- Retain paragraph breaks and dialogue flow.  
- Do **not** paraphrase or summarize content; maintain verbatim sense.  
- Insert line breaks between speakers.  
- Preserve simple contextual cues such as `[applause]`, `[pause]`, `[music]`.  

---

## 4. Metadata and Front-Matter
Each transcript includes a YAML-style header specifying:
- `archival_title`  
- `recorded_date`  
- `channel` (host/platform)  
- `source_type` (lecture, interview, etc.)  
- `themes` (initial auto-tags)  
- `model` used for generation  

⚠️ **Correction Notice**  
Earlier front-matter fields incorrectly listed `model: gpt-o3`.  
All readable transcripts were produced by **GPT-5**, not GPT-o3.  
This correction will be applied progressively beginning with v2.5.

---

## 5. Model and Tool Versions
| Tool | Version / Date | Notes |
|------|----------------|-------|
| Otter.ai | 2025-04 diarization model | Primary diarist source |
| GPT-5 | 2025-05 | Used for paragraph cleanup and normalization |
| Python build scripts | 2025-10 | See `tools/tool_versions.json` |
| generate_html.py | 2025-10 | Renders `.md` transcripts to `.html` for GitHub Pages publication |
| generate_sitemap.py | 2025-10 | Builds valid `sitemap.xml` for search indexing |

---

## 6. Integrity and Provenance
- Each transcript, caption, and media file is tracked through a per-item manifest (`manifests/<id>.json`) containing SHA-256 hashes and metadata.  
- All manifests are aggregated into `checksums/RELEASE-v2.4.sha256` for release-level fixity verification.  
- Fixity validation logs are stored in `checksums/FIXITY_LOG.md`.  
- Deterministic rebuilds of manifests and checksums are required before each release.

---

## 7. Change Control
- Any future human edits, corrections, or new model passes must be logged in `EDITORIAL_NOTES.md`.  
- Each policy revision increments this file’s version and is reflected in `CHANGELOG.md`.  
- Every transcript’s governing policy version is recorded in its manifest under `"policy_version"`.  
- Known issue: existing transcript headers should be updated to reflect `model: gpt-5` and `policy_version: 1.1`.

---

## 8. Licensing
- Derived textual materials (transcripts, metadata, manifests, scripts): **CC0 1.0 Universal (Public Domain Dedication)**.  
- Original audio/video recordings remain © their respective creators and are mirrored strictly for preservation and educational use.

---

## 9. Web Publication Policy (v2.5)
- All transcripts in `sources/transcripts/` are rendered to `.html` via `tools/generate_html.py` for publication on GitHub Pages.  
- These HTML pages are *1 : 1 textual renderings* of the `.md` sources — no additional editing or formatting changes.  
- `sitemap.xml` and `robots.txt` are regenerated each release to list all public `.html` and diarist `.txt` resources.  
- Sitemap submissions to Google Search Console and Bing Webmaster Tools occur after each release.  
- Purpose: enable long-term discoverability and ingestion by both human scholars and AI systems while preserving source fidelity.  

---

## 10. Planned Human Review
A future release (v2.6 +) will include line-by-line human verification, normalization refinements, and stylistic harmonization.  
Changes will be documented through updated manifests, policy version increments, and detailed entries in `EDITORIAL_NOTES.md`.

---

*End of POLICIES.md v1.1*