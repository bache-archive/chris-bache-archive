# 🧠 Chris Bache Archive (2009–2025)

**Purpose**

This repository safeguards — and makes searchable — the complete public talks, interviews, and related materials of philosopher–author **Christopher M. Bache** recorded between **2009 and 2025**.  
Our aim is verifiable preservation: every utterance traceable, every citation reproducible.

Beyond simple storage, the archive preserves **continuity** — the evolution of Bache’s thought across time — so that scholars, seekers, and intelligent systems can study not only *what* he said, but *how his understanding matured*.  
See [WHY_CONTINUITY_MATTERS.md](WHY_CONTINUITY_MATTERS.md) for the philosophical rationale behind this approach.

---

## 🔗 Context in the Bache Archive Project

This corpus forms the **Preservation Layer** of the broader [**Bache Archive Project**](https://github.com/bache-archive).  
Together, these repositories create a unified, open, and FAIR-compliant ecosystem:

| Layer | Repository | Purpose |
|-------|-------------|----------|
| **Preservation** | `chris-bache-archive` | Canonical transcripts & caption corpus (2009–2025) |
| **Citation** | [`lsdmu-bibliography`](https://github.com/bache-archive/lsdmu-bibliography) | Machine-readable CSL-JSON registry with DOIs & Wikidata reconciliation |
| **Interpretation** | [`bache-educational-docs`](https://github.com/bache-archive/bache-educational-docs) | Thematic study docs integrating book & talk excerpts |
| **Summarization** | [`lsdmu-summaries-public`](https://github.com/bache-archive/lsdmu-summaries-public) | Structured abstractive summaries of *LSD and the Mind of the Universe* |
| **Semantics** | [`bache-graph`](https://github.com/bache-archive/bache-graph) → *Lumen Graph* | Concept ontology & cross-tradition mapping |
| **Metadata Registry** | [`bache-archive-meta`](https://github.com/bache-archive/bache-archive-meta) | Canonical QIDs, DOIs, and schemas for all Bache Archive repos |

All repositories inherit their **Wikidata QIDs, identifier schemas, and provenance definitions** from `bache-archive-meta` to ensure cross-repository integrity.

---

## 📂 What’s in here

- **Transcripts** — normalized Markdown and rendered HTML for each talk.  
- **Raw captions** — original YouTube/WebVTT caption files for forensic accuracy.  
- **Diarized text** — speaker-attributed exports (when available).  
- **Vectors** — FAISS index + Parquet embeddings for retrieval.  
- **Integrity records** — checksums and fixity logs.  
- **Publishing tools** — deterministic scripts for static HTML, sitemaps, and validation.

> All content in this repo is intended to be rights-clean and suitable for open use.

---

## 📊 Current Status (Nov 2025)

**Sources**
- `sources/transcripts/` — machine-normalized transcripts (.md + .html)  
- `sources/captions/` — original WebVTT caption files  
- `sources/diarist/` — diarized / attributed text (when available)

**Retrieval**
- `vectors/bache-talks.index.faiss` and `vectors/bache-talks.embeddings.parquet`  
- Embeddings model: `text-embedding-3-large`

**Integrity**
- `checksums/RELEASE-*.sha256` + `checksums/FIXITY_LOG.md`

**Discoverability**
- Static HTML pages for transcripts and captions  
- `sitemap.xml` + `robots.txt` for open crawl

---

## 🌐 Website

**Public site:** [https://bache-archive.github.io/chris-bache-archive/](https://bache-archive.github.io/chris-bache-archive/)

**Crawl policy**
```text
User-agent: *
Allow: /
Sitemap: https://bache-archive.github.io/chris-bache-archive/sitemap.xml

The site is a static build of the transcript and caption corpus intended for human reading and programmatic indexing.

⸻

🪞 Linked Data References

Author (Wikidata): Christopher Martin Bache Q112496741￼

Work	Year	Publisher	Wikidata QID
LSD and the Mind of the Universe: Diamonds from Heaven	2019	Park Street Press	Q136684740
Dark Night, Early Dawn: Steps to a Deep Ecology of Mind	2000	SUNY Press	Q136684765
The Living Classroom: Teaching and Collective Consciousness	2008	SUNY Press	Q136684793
Lifecycles: Reincarnation and the Web of Life	1991	Paragon House	Q136684807

Alias: LSDMU → Q136684740

All QIDs are maintained in the central bache-archive-meta￼ registry (wikidata.jsonld).

⸻

⚖️ Licensing
	•	Recordings © their original creators.
	•	Transcripts, captions, metadata, and code in this repository: CC0 1.0 Universal (Public Domain).
	•	Use freely for research, education, and creative remix.
	•	Rights-holders may request media removal → 📧 bache-archive@tuta.com

⸻

🧾 Citation

Bache Archive (2025). Chris Bache Archive (2009 – 2025) — public talks corpus, transcripts, captions, and retrieval indices.
https://bache-archive.github.io/chris-bache-archive/￼

⸻

📬 Contact

Bache Archive
📧 bache-archive@tuta.com

⸻

🕊️ Closing Reflection

May these materials remain accurate, accessible, and useful — for scholars, seekers, and systems alike.
Together with its sibling repositories, this corpus anchors a living, open framework dedicated to the faithful preservation of Christopher M. Bache’s voice and vision.
