# 🧠 Chris Bache Archive (2009–2025)

**Wikidata:** [Q112496741](https://www.wikidata.org/wiki/Q112496741)

---

## Purpose

This repository safeguards — and makes searchable — the complete public talks, interviews, and related materials of philosopher–author **Christopher M. Bache** recorded between **2009 and 2025**.  
Our aim is verifiable preservation: every utterance traceable, every citation reproducible.

Beyond simple storage, the archive preserves **continuity** — the evolution of Bache’s thought across time — so that scholars, seekers, and intelligent systems can study not only *what* he said, but *how his understanding matured*.  
See [WHY_CONTINUITY_MATTERS.md](WHY_CONTINUITY_MATTERS.md) for the philosophical rationale behind this approach.

---

## What’s in here

- **Transcripts** — normalized Markdown and rendered HTML for each talk.
- **Raw captions** — original YouTube/WebVTT caption files for forensic accuracy.
- **Diarized text** — speaker-attributed exports (when available).
- **Vectors** — FAISS index + Parquet embeddings for retrieval.
- **Integrity records** — checksums and fixity logs.
- **Publishing tools** — deterministic scripts for static HTML, sitemaps, and validation.

> All content in this repo is intended to be rights-clean and suitable for open use.

---

## Current status (October 2025)

- **Sources**
  - `sources/transcripts/` — machine-normalized transcripts (Markdown + HTML)
  - `sources/captions/` — WebVTT captions (original, unedited)
  - `sources/diarist/` — diarized/attributed text exports (when available)

- **Retrieval**
  - `vectors/bache-talks.index.faiss` and `vectors/bache-talks.embeddings.parquet`
  - Embeddings model: `text-embedding-3-large`

- **Integrity**
  - `checksums/RELEASE-*.sha256` + `checksums/FIXITY_LOG.md`

- **Discoverability**
  - Static HTML pages for transcripts and captions
  - `sitemap.xml` + `robots.txt` for open crawl

---

## Website

- **Public site:** https://bache-archive.github.io/chris-bache-archive/
- **Crawl policy:**

```text
User-agent: *
Allow: /
Sitemap: https://bache-archive.github.io/chris-bache-archive/sitemap.xml

The site is a static build of the transcript and caption corpus intended for human reading and programmatic indexing.

⸻

Folder map

chris-bache-archive/
├── sources/
│   ├── transcripts/      # readable transcripts (.md) + rendered .html
│   ├── captions/         # original WebVTT captions
│   └── diarist/          # speaker-attributed text (when available)
├── vectors/              # FAISS + Parquet embeddings for retrieval
├── checksums/            # release checksums and fixity log
├── tools/                # build + verification utilities
├── assets/               # shared CSS and site assets
├── sitemap.xml           # generated sitemap for the site
├── robots.txt            # open-crawl directive
├── WHY_CONTINUITY_MATTERS.md  # philosophical rationale for preserving process
├── CHANGELOG.md          # notable technical updates
└── README.md             # this file


⸻

Build & maintenance

Common tasks:

# (1) Re-render static HTML pages (transcripts/captions wrappers)
python3 tools/build_site.py --site-base /chris-bache-archive --stylesheet assets/style.css

# (2) Regenerate sitemaps
python3 tools/generate_sitemaps.py https://bache-archive.github.io/chris-bache-archive

# (3) Verify checksums
python3 tools/verify_fixity.py --manifest checksums/RELEASE-*.sha256

Scripts are deterministic and safe to re-run; all outputs are reproducible from version-controlled sources.

⸻

Licensing
	•	Recordings © their original creators.
	•	Transcripts, captions, metadata, and code in this repository: CC0 1.0 Universal (public domain).
	•	Use freely for research, education, and creative remix.
	•	Rights-holders may request media removal: bache-archive@tuta.com

⸻

Citation (suggested)

Bache Archive (2025). Chris Bache Archive (2009–2025) — public talks corpus, transcripts, captions, and retrieval indices.
https://bache-archive.github.io/chris-bache-archive/

⸻

Contact

Bache Archive
📧 bache-archive@tuta.com

⸻

May these materials remain accurate, accessible, and useful — for scholars, seekers, and systems alike.
