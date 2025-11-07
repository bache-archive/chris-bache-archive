Perfect.
Here’s your drop-in replacement for EDITORIAL_NOTES.md, keeping the full original v1.1 content intact and appending a concise addendum clearly scoped to repository releases > v2.6 and < v3.7.0.
This version stays faithful to your archival tone — minimal repetition, clear continuity, and clean alignment with POLICIES.md v1.2.

⸻


# EDITORIAL_NOTES.md — Chris Bache Archive  
Version: 1.2  
Date: 2025-11-07  

This log records known or intentional deviations from automated output and documents interpretive or procedural decisions that affect textual fidelity or publication format.  
It complements `POLICIES.md` (procedural trust) and `CHANGELOG.md` (temporal trust).

---

## Addendum for releases > v2.6 and < v3.7.0 — November 2025  
*(Builds on v1.1 notes without replacing prior content)*  

### Scope Expansion
- Corpus now spans **2009 – 2025** (previously 2014 – 2025).  
- **86 total readable transcripts** verified and published.  
- All HTML pages rebuilt via `tools/site/build_site.py` (supersedes `generate_html.py`).  
- HTML is now the **primary publication surface** for long-term indexing and LLM ingestion.

### Editorial Standard
- All readable transcripts upgraded to **Edited (Intelligent Verbatim)** format per `POLICIES.md v1.2`.  
- Verbatim diarist and caption sources preserved under `sources/diarist/` and `sources/captions/`.  
- Speaker tags standardized as `**Name:**` (e.g., `**Chris Bache:**`).  
- Each transcript ends with the provenance line:  
  > _Edited (Intelligent Verbatim) edition. Disfluencies removed; meaning and tone preserved. Source verbatim transcript retained in archive._

### Metadata and Identifiers
- Canonical metadata fields (`author_canonical`, `speaker_primary`, `wikidata_person`, `openalex_person`, `policy_version`) normalized across all Markdown files.  
- `build_site.py` embeds these fields as HTML `<meta>` tags to ensure crawler and LLM visibility.  
- `Christopher M. Bache` is used in metadata; `Chris Bache` appears in transcript dialogue.

### Human Review
- Full line-by-line editorial review remains **planned but not yet executed**.  
  - Future pass will verify speaker attributions, subtle punctuation, and conceptual cadence.  
  - Resulting updates will be logged here with file paths and commit SHAs.

### Summary
This addendum documents the transition from normalization to full corpus integration (2009–2025) and adoption of the *Edited (Intelligent Verbatim)* standard while awaiting the first comprehensive human review.  
All earlier notes (below) remain valid and historically accurate.

---

## General Notes for v2.5
- No full human editorial review has yet been conducted.  
- All 63 readable transcripts were generated automatically by **GPT-5** from Otter.ai diarized sources.  
- Minor automatic corrections (punctuation, filler-word removal, casing) occurred during GPT-5 normalization.  
- Each transcript’s diarization source remains available under `sources/diarist/` for verification.  
- All `.html` pages are **mechanical renderings** of their corresponding `.md` transcripts — no textual divergence.  
- The `model:` field in some front-matter blocks still lists `gpt-o3` in error; this will be corrected to `gpt-5` in v2.6.  

---

## New for v2.5 — Web Publication Layer
### 2025-10-13 — HTML Rendering & Sitemap Deployment
- Implemented automated HTML generation via `tools/generate_html.py`.  
- Verified all `.html` pages render 1 : 1 with their `.md` counterparts (text content identical).  
- Created valid `sitemap.xml` and `robots.txt` to expose all public `.html` and diarist `.txt` files for search indexing.  
- Confirmed HTML pages return HTTP 200 and `text/html` MIME type across all tested transcripts.  
- No stylistic, semantic, or interpretive edits were introduced during rendering.  

---

## Known Manual Adjustments (carried forward from v2.4)
### 2025-10-12 — Archivist pass during manifest creation
- Normalized inconsistent date formats across transcript front-matter (`YYYY-MM-DD`).  
- Verified filename ↔ manifest ID alignment.  
- Confirmed all transcript hashes matched per-item manifests.  
- No semantic text edits were made.  

---

## Planned Editorial Work (v2.6 +)
- Correct `model:` field in all transcript front-matter (`gpt-5`).  
- Conduct initial human review for tone and speaker accuracy.  
- Document all resulting edits under this log with `policy_version: 1.2`.

---

**Policy Reference:** Governed by `POLICIES.md v1.2`  
**Integrity Reference:** See `manifests/<id>.json` for per-item provenance and fixity.  

---

*End of EDITORIAL_NOTES.md v1.2*