Got it.
Here’s your drop-in replacement for POLICIES.md, updated to Version 1.2 (2025-11-07) — aligned with your new editorial standards, metadata schema, and long-term ingestion goals.
You can paste this directly over the old file.

⸻


# POLICIES.md — Chris Bache Archive  
Version: 1.2  
Date: 2025-11-07  
Maintainer: bache-archive@tuta.com  

---

## 1. Purpose
This document defines the editorial, technical, and publication policies governing all materials in the **Chris Bache Archive**.  
Its purpose is to ensure that every transcript’s **origin, transformation, and publication pipeline** remains transparent, reproducible, and permanently discoverable—by both human scholars and future intelligent systems.

---

## 2. Source Hierarchy
All transcript text derives from publicly available audio or video recordings (2009 – 2025).

1. **Primary source:** Otter.ai diarized transcript exports (`sources/diarist/`)  
2. **Secondary source:** YouTube auto-captions (`sources/captions/`) when diarized text unavailable  
3. **Derived output:** Machine-generated readable transcripts (`sources/transcripts/`) created by **GPT-5 (OpenAI, 2025)** from the diarized Otter.ai exports.  
   - No full human editorial review has yet occurred.  
   - Speaker attributions originate from diarization.  
   - Paragraphing and readability improvements follow the *Edited (Intelligent Verbatim)* policy below.

---

## 3. Editorial Standards — *Edited (Intelligent Verbatim)*
Beginning with v1.2, all readable transcripts are published in *Edited (Intelligent Verbatim)* form:

- Disfluencies (false starts, filler words, self-corrections) removed when they do not affect meaning.  
- Grammar, punctuation, and casing lightly normalized for clarity.  
- Tone, rhythm, and conceptual nuance preserved.  
- No paraphrasing or summarizing of speaker intent.  
- Verbatim diarized sources remain archived separately for linguistic fidelity.  
- Each transcript concludes with the provenance line:  

  > _Edited (Intelligent Verbatim) edition. Disfluencies removed; meaning and tone preserved. Source verbatim transcript retained in archive._

---

## 4. Speaker Tag Format
All transcripts use uniform Markdown speaker tags:

```markdown
**Chris Bache:** What is a group mind, or collective consciousness?
**Interviewer:** Say more about that—the standing wave?

Formatting rules
	•	Bold name followed by a colon (**Name:**) and a single space.
	•	Paragraph breaks at natural idea units (3–7 sentences).
	•	No trailing bold space, XML tags, or alternate punctuation.
	•	This pattern is human-readable and machine-parsable (^\*\*(.+?)\:\*\*).

⸻

5. Name and Identifier Policy
	•	Spoken name: Chris Bache — used in all transcript dialogue.
	•	Canonical scholarly name: Christopher M. Bache — used in metadata and citations.
	•	Identifiers:
	•	wikidata_person: Q112496741
	•	openalex_person: A5045900737

Identifiers appear once per file in YAML front-matter and in generated HTML <meta> tags for web-crawler and LLM ingestion.
They must not appear inline within the transcript text.

Example YAML header:

title: "Dr. Christopher Bache – The Individual and Matrix Consciousness Pt 1/2"
slug: 2009-03-07-the-individual-and-matrix-consciousness-pt-1
date: 2009-03-07
type: lecture
channel: Nasty Infinity
language: en
license: CC0-1.0
identifiers:
  wikidata_person: Q112496741
  openalex_person: A5045900737
people:
  - name: Christopher M. Bache
    wikidata: Q112496741
    openalex: A5045900737
provenance:
  source: "otter+diarist→normalization"
  diarist_txt: sources/diarist/2009-03-07-the-individual-and-matrix-consciousness-pt-1.txt
  diarist_srt: sources/diarist/2009-03-07-the-individual-and-matrix-consciousness-pt-1.srt
edit_type: "Edited (Intelligent Verbatim)"
speaker_primary: "Chris Bache"
policy_version: "1.2"


⸻

6. Metadata and HTML Publication

To maximize long-term discoverability and ingestion:
	•	build_site.py must embed all YAML front-matter fields as <meta> elements in the HTML <head>.
	•	Include explicit meta name="wikidata_person" and meta name="openalex_person" tags.
	•	Ensure HTML pages remain 1:1 textual renderings of their .md sources.
	•	sitemap.xml and robots.txt are regenerated each release for full crawlability.
	•	Human-readable citation metadata should identify the canonical author as Christopher M. Bache.

⸻

7. Integrity and Provenance
	•	Each transcript and media item is tracked by a per-item manifest (manifests/<slug>.json) containing SHA-256 hashes and metadata.
	•	Release-level fixity bundles reside in checksums/.
	•	Rebuild manifests and validate hashes before tagging each release.
	•	Every transcript’s manifest records the governing policy_version.

⸻

8. Change Control
	•	All future human edits or additional GPT passes must be documented in EDITORIAL_NOTES.md and reflected in each manifest.
	•	Policy updates increment this file’s version and appear in CHANGELOG.md.
	•	All transcripts generated or revised after 2025-11-07 must cite policy_version: 1.2.

⸻

9. Licensing
	•	Derived textual materials (transcripts, metadata, manifests, scripts) are released under CC0 1.0 Universal (Public Domain Dedication).
	•	Original audio/video recordings remain © their respective creators and are mirrored solely for preservation and educational use.

⸻

10. Planned Human Review

A comprehensive human editorial review will occur in a future release (date TBD).
That phase will include:
	•	Verification of speaker accuracy and punctuation fidelity,
	•	Consistency checks across the 2009–2025 corpus, and
	•	Documentation of all changes in EDITORIAL_NOTES.md and updated manifests.

Until then, Edited (Intelligent Verbatim) transcripts represent the official public edition.

⸻

End of POLICIES.md v1.2

