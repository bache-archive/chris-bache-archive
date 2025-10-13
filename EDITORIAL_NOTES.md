# EDITORIAL_NOTES.md — Chris Bache Archive  
Version: 1.1  
Date: 2025-10-13  

This log records known or intentional deviations from automated output and documents interpretive or procedural decisions that affect textual fidelity or publication format.  
It complements `POLICIES.md` (procedural trust) and `CHANGELOG.md` (temporal trust).

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
- Verified all `.html` pages render 1:1 with their `.md` counterparts (text content identical).  
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

## Planned Editorial Work (v2.6+)
- Correct `model:` field in all transcript front-matter (`gpt-5`).  
- Conduct initial human review for tone and speaker accuracy.  
- Document all resulting edits under this log with `policy_version: 1.2`.

---

**Policy Reference:** Governed by `POLICIES.md` v1.1.  
**Integrity Reference:** See `manifests/<id>.json` for per-item provenance and fixity.  

---

*End of EDITORIAL_NOTES.md v1.1*