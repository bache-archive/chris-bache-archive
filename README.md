# 🧠 Chris Bache Archive (2014–2025)

**Purpose**

This repository safeguards — and makes searchable — the public talks, interviews, and related materials of philosopher–author **Christopher M. Bache** recorded between **2014–2025**.  
Our aim is verifiable preservation: every utterance traceable, every citation reproducible.

---

## What’s in here

- **Transcripts** — readable, normalized Markdown; each also rendered to HTML for the website.
- **Raw captions** — original YouTube/WebVTT caption files kept for forensic accuracy.
- **Diarized text** — speaker-attributed exports (when available).
- **Vectors** — FAISS index + Parquet embeddings for retrieval.
- **Integrity records** — checksums and fixity logs.
- **Publishing tools** — simple scripts for static HTML, sitemaps, and verification.

> All content in this repo is intended to be rights-clean and suitable for open use.

---

## Current status (October 2025)

- **Sources**
  - `sources/transcripts/` — machine-normalized transcripts (Markdown + rendered HTML)
  - `sources/captions/` — WebVTT captions (original, unedited)
  - `sources/diarist/` — diarized/attributed text exports (when available)
- **Retrieval**
  - `vectors/bache-talks.index.faiss` and `vectors/bache-talks.embeddings.parquet`
  - Embeddings: `text-embedding-3-large`
- **Integrity**
  - `checksums/RELEASE-*.sha256` + `checksums/FIXITY_LOG.md`
- **Discoverability**
  - Static HTML pages for transcripts/captions
  - `sitemap.xml` + `robots.txt` for open crawl

---

## Website

- **Public site:** https://bache-archive.github.io/chris-bache-archive/
- **Crawl policy:**

User-agent: *
Allow: /
Sitemap: https://bache-archive.github.io/chris-bache-archive/sitemap.xml

The site is a static build of the transcript/caption corpus intended for human reading and programmatic indexing.

---

## Folder map

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
├── CHANGELOG.md          # notable technical updates
└── README.md             # this file

---

## Build & maintenance

Common tasks:

```bash
# (1) Re-render static HTML pages (transcripts/captions wrappers)
python3 tools/build_site.py --site-base /chris-bache-archive --stylesheet assets/style.css

# (2) Regenerate sitemaps
python3 tools/generate_sitemaps.py https://bache-archive.github.io/chris-bache-archive

# (3) Verify checksums (example)
python3 tools/verify_fixity.py --manifest checksums/RELEASE-*.sha256

Scripts are designed to be deterministic and safe to re-run.

⸻

Licensing
	•	Recordings © their original creators.
	•	Transcripts, captions, metadata, and code in this repository: CC0 1.0 Universal (public domain).
	•	Use freely for research, education, and creative remix.
	•	Rights-holders may request media removal: bache-archive@tuta.com.

⸻

Citation (suggested)

Bache Archive (2025). Chris Bache Archive (2014–2025) — public talks corpus, transcripts, captions, and retrieval indices.
https://bache-archive.github.io/chris-bache-archive/

⸻

Contact

Bache Archive
📧 bache-archive@tuta.com

⸻

May these materials remain accurate, accessible, and useful — for scholars, seekers, and systems alike.

