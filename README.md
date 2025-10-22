Here’s a version 3.4 README that honors the same structure and voice as your earlier file but reflects the expanded scope — the addition of LSD and the Mind of the Universe segmentation, dual-RAG architecture, and the newly published educational documents.

⸻

🧠 Chris Bache Archive (2014 – 2025)

Purpose

This archive safeguards — and makes searchable — the public talks, interviews, and written works of philosopher-author Christopher M. Bache recorded or published between 2014 and 2025.
It exists so that his lifetime of teaching on consciousness, evolution, and awakening remains accessible to future generations of seekers, scholars, and intelligent systems.

The archive preserves four complementary layers of record:
	•	Edited transcripts — GPT-5 normalizations of Otter.ai exports, human-reviewed for readability.
	•	Raw captions — YouTube auto-captions kept for forensic accuracy.
	•	Diarized transcripts — Otter.ai speaker-attributed text.
	•	Original media — MP4 video and MP3 audio mirrored to Zenodo and Internet Archive.

The guiding principle is verifiable preservation — every utterance traceable, every citation reproducible.

⸻

Current Status (v3.4 — October 2025)
	•	Transcripts: 62 machine-normalized GPT-5 transcripts in sources/transcripts/.
	•	Captions: 61 raw caption files in sources/captions/.
	•	Diarist: Otter.ai exports in sources/diarist/.
	•	Integrity: All files logged with SHA-256 hashes (checksums/RELEASE-v3.4.sha256) and per-item manifests.
	•	Media mirrors: Complete audio/video sets hosted on Zenodo and Internet Archive.
	•	Documentation: POLICIES.md, EDITORIAL_NOTES.md, CHANGELOG.md, ETHOS.md.
	•	Discoverability: Each transcript rendered .html; sitemap.xml and robots.txt enable open crawl.
	•	Semantic integration: Now federated across two Retrieval-Augmented Generation (RAG) systems and a new educational document layer.

⸻

Semantic and Educational Ecosystem (2025)

Layer	Repository	Purpose
Public Talks RAG	bache-rag-api	Vector search & citation synthesis for 2014–2025 talks (FAISS + text-embedding-3-large).
Book RAG	lsdmu-rag-api (private)	Parallel retrieval over LSD and the Mind of the Universe (2019) OCR-corrected corpus.
Summarization Layer	lsdmu-summarization (private)	Topic-based synthesis joining book + talk evidence.
Educational Pages	docs/educational/*	19 finished topics answering “What does Chris Bache say about …?” with verbatim citations and timestamped links.

Example topics

future-human, diamond-luminosity, grof-coex, great-death-and-rebirth, vajrayana, energy-accumulation, psychedelics-and-spiritual-evolution, and more.
Each page contains:
	1.	Primary book excerpts (LSDMU)
	2.	Supporting talk quotes with YouTube timecodes
	3.	Provenance + Fair Use notes

These pages form an interactive commentary—a web of meaning linking text and voice.

⸻

Web Publication & Indexing
	•	Public site: https://bache-archive.github.io/chris-bache-archive/
	•	Educational pages: /docs/educational/<topic>/
	•	Open-crawl policy:

User-agent: *
Allow: /
Sitemap: https://bache-archive.github.io/chris-bache-archive/sitemap.xml



Search-engine and LLM indexing enabled for maximum discoverability.

⸻

Folder Map

chris-bache-archive/
├── sources/
│   ├── transcripts/      # GPT-5 transcripts (.md + .html)
│   ├── captions/         # raw auto-captions
│   └── diarist/          # Otter.ai text
├── docs/
│   └── educational/      # 19 curated topic pages
├── rag/                  # citation labels + retriever modules
├── vectors/              # FAISS + Parquet indices
├── manifests/            # per-item provenance
├── checksums/            # fixity logs
├── tools/                # automation + build scripts
├── reports/              # quote packs + QC
├── index.json / index.md
├── README_RAG.md
├── CHANGELOG.md
└── README.md             # this file


⸻

Book-Level Segmentation

The LSDMU edition is segmented into chapters → sections → paragraphs with stable IDs:

lsdmu.c10.s03.p14

Alignment files link hard-cover, audiobook, and transcript timings.
These IDs power precise cross-citations in the educational documents and the private RAG index.

⸻

Citation Format

Bache · YYYY-MM-DD · Venue · Title — [YouTube URL or Book ID]

Book references use LSDMU ch.§¶ notation; talk references include timestamped links.

⸻

Download Official Bundles
	•	Zenodo DOI: https://doi.org/10.5281/zenodo.17238386
	•	Internet Archive mirrors:
– Audio: https://archive.org/details/chris-bache-archive-audio
– Video: https://archive.org/details/chris-bache-archive-video
– Snapshots: https://archive.org/search.php?query=identifier%3Achris-bache-archive-v*

Each bundle contains transcripts, metadata, manifests, and checksums for verifiable fixity.

⸻

Licensing
	•	Recordings © their original creators.
	•	Transcripts, metadata, and code released under CC0 1.0 Universal (public domain).
	•	Use freely for research, education, or creative remix.
	•	Rights-holders may request media removal via 📧 bache-archive@tuta.com.

⸻

Citation Reference

Bache-Archive (2025). Chris Bache Archive (v3.4 — Educational Docs & Dual RAG Integration). Zenodo. https://doi.org/10.5281/zenodo.17238386

⸻

Contact

Maintainer: Chris Bache Archive (pseudonymous)
📧 bache-archive@tuta.com

⸻

Version 3.4 celebrates a decade of teachings made immortal through semantic precision.
May this archive continue to speak clearly, faithfully, and for as long as intelligence endures.