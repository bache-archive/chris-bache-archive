# POLICIES.md — Chris Bache Archive
Version: 1.0  
Date: 2025-10-12  
Maintainer: bache-archive@tuta.com  

---

## 1. Purpose
This document defines the editorial and processing policies governing all textual materials in the Chris Bache Archive.  
Its goal is to make every transcript’s origin and treatment transparent and reproducible.

---

## 2. Source Hierarchy
All transcript text derives from publicly available audio or video recordings (2014 – 2025).

1. **Primary source:** Otter.ai diarized transcript exports (`sources/diarist/`)  
2. **Secondary source:** YouTube auto-captions (`sources/captions/`) when diarized text unavailable  
3. **Derived output:** Machine-generated readable transcripts (`sources/transcripts/`) created by **GPT-5 (OpenAI, 2025)** using the diarized Otter.ai exports as input.  
   - No full human editorial review has yet occurred.  
   - Speaker attributions and paragraph boundaries come from Otter.ai diarization.

---

## 3. Normalization Policy
Machine processing used the following normalization rules (prompt-level instructions applied to GPT-5):

- Preserve the speaker order and attributions from Otter.ai.  
- Remove non-semantic filler words (“um,” “uh,” “you know”).  
- Correct obvious punctuation and capitalization errors.  
- Retain paragraph breaks and dialogue flow.  
- Do **not** paraphrase or summarize content; maintain verbatim sense.  
- Insert line breaks between speakers.  
- Keep minimal contextual markers `[applause]`, `[music]`, `[pause]` where detected.

---

## 4. Metadata and Front-Matter
Each transcript includes a short YAML-like header specifying:
- `archival_title`  
- `recorded_date`  
- `channel` (host/platform)  
- `source_type` (lecture, interview, etc.)  
- `themes` (initial auto-tags)  
- `model` used for generation  

⚠️ **Note:**  
Earlier front-matter lines incorrectly listed `gpt-o3` as the model.  
As of v2.4, all readable transcripts were produced by **GPT-5**, not GPT-o3.

---

## 5. Model and Tool Versions
| Tool | Version / Date | Notes |
|------|----------------|-------|
| Otter.ai | 2025-04 diarization model | Primary diarist source |
| GPT-5 | 2025-05 | Used for paragraph cleanup and normalization |
| Python build scripts | 2025-10 | See `tools/tool_versions.json` |

---

## 6. Change Control
- Any future human edits or model passes must be logged in `EDITORIAL_NOTES.md`.  
- Policy revisions increment this file’s version and are recorded in `CHANGELOG.md`.  
- Each transcript’s governing policy version appears in its corresponding `manifests/<id>.json` under `"policy_version"`.

---

## 7. Licensing
- Derived textual materials: **CC0 1.0 Universal (Public Domain Dedication)**.  
- Original audio/video remain © their respective creators and are mirrored for preservation and educational use only.

---

## 8. Planned Human Review
A later release (v2.5 +) will include line-by-line human verification and style harmonization.  
Those changes will be documented through updated manifests and `EDITORIAL_NOTES.md`.

---

*End of POLICIES.md v1.0*
