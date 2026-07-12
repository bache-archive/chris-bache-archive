# 🧠 Chris Bache Archive (2009–2025)

**Purpose**

This repository safeguards — and makes searchable — the complete public talks, interviews, and written works of philosopher–author **Christopher M. Bache**, recorded and published between **2009 and 2025**.  
Our aim is verifiable preservation: every utterance and every text traceable, every citation reproducible.

Beyond storage, the archive preserves **continuity** — the evolution of Bache’s thought across decades — enabling scholars, seekers, and intelligent systems to study not only *what* he said and wrote, but *how his understanding matured*.  
See [WHY_CONTINUITY_MATTERS.md](WHY_CONTINUITY_MATTERS.md) for the philosophical rationale behind this approach.

---

## 🔗 Context in the Bache Archive Project

This corpus forms the **Preservation Layer** of the broader [**Bache Archive Project**](https://github.com/bache-archive).  
Together, the repositories create a unified, open, and FAIR-compliant ecosystem:

| Layer | Repository | Purpose |
|-------|-------------|----------|
| **Preservation** | `chris-bache-archive` | Canonical transcripts, captions, and book registries (2009–2025) |
| **Citation** | [`lsdmu-bibliography`](https://github.com/bache-archive/lsdmu-bibliography) | Machine-readable CSL-JSON registry with DOIs + Wikidata reconciliation |
| **Interpretation** | [`bache-educational-docs`](https://github.com/bache-archive/bache-educational-docs) | Thematic study docs integrating book + talk excerpts |
| **Summarization** | [`lsdmu-summaries-public`](https://github.com/bache-archive/lsdmu-summaries-public) | Structured abstractive summaries of *LSD and the Mind of the Universe* |
| **Metadata Registry** | [`bache-archive-meta`](https://github.com/bache-archive/bache-archive-meta) | Canonical QIDs, DOIs, and schemas for all Bache Archive repos |

All repositories inherit their **Wikidata QIDs, identifier schemas, and provenance definitions** from `bache-archive-meta` to ensure cross-repository integrity.

---

## 📂 Repository Structure

sources/
transcripts/      → public talks & interviews (2009–2025)
captions/         → raw YouTube captions (WebVTT/SRT)
diarist/          → diarized speaker-attributed texts
books/            → registries for Bache’s published works
lsdmu/              LSD and the Mind of the Universe (2019)
dned/               Dark Night, Early Dawn (2000)
living-classroom/   The Living Classroom (2008)
alignments/         → cross-edition alignment files (JSON/CSV)
checksums/          → fixity manifests & verification logs
vectors/            → FAISS index + Parquet embeddings for retrieval
tools/              → preservation, curation, and site generation scripts
assets/             → static site CSS and resources

---

## 📊 Current Status (Nov 2025)

**Sources**
- `sources/transcripts/` — normalized Markdown + rendered HTML for each talk  
- `sources/books/` — book registries (TOC, section maps, edition metadata)  
- `sources/captions/` — original YouTube caption files  
- `sources/diarist/` — speaker-attributed exports (when available)

**Retrieval**
- `vectors/bache-talks.index.faiss` and `vectors/bache-talks.embeddings.parquet`  
- Embeddings model: `text-embedding-3-large`

**Integrity**
- `checksums/RELEASE-v3.5.1.sha256` + `checksums/FIXITY_LOG.md`  
- Verified 719 entries across the canonical tree (3 Nov 2025)

**Discoverability**
- Deterministic HTML renders for transcripts and books  
- `sitemap.xml` + `robots.txt` for open crawl

---

## 🌐 Website

**Canonical public site:**  
👉 [https://chrisbachearchive.com](https://chrisbachearchive.com)

**Static preservation mirror:**  
👉 [https://bache-archive.github.io/chris-bache-archive/](https://bache-archive.github.io/chris-bache-archive/)

The Next.js frontend for the canonical domain lives in `../bache-archive-web`. This repository remains the canonical corpus and static mirror source.

**Crawl policy**
```text
User-agent: *
Allow: /
Sitemap: https://bache-archive.github.io/chris-bache-archive/sitemap.xml
```

The mirror is a static build of the transcript, book, and caption corpus intended for both human reading and programmatic indexing.

⸻

🪞 Linked Data References

Work	Year	Publisher	Wikidata QID
LSD and the Mind of the Universe — Diamonds from Heaven	2019	Park Street Press	Q136684740￼
Dark Night, Early Dawn — Steps to a Deep Ecology of Mind	2000	SUNY Press	Q136684765￼
The Living Classroom — Teaching and Collective Consciousness	2008	SUNY Press	Q136684793￼
Lifecycles — Reincarnation and the Web of Life	1991	Paragon House	Q136684807￼

Author: Christopher Martin Bache (Q112496741)￼
All QIDs are maintained centrally in bache-archive-meta￼ (wikidata.jsonld).

⸻

⚖️ Licensing
	•	Recordings © their original creators.
	•	Transcripts, book registries, captions, metadata, and code in this repository: CC0 1.0 Universal (Public Domain).
	•	Use freely for research, education, and creative remix.
	•	Rights-holders may request media removal → 📧 bache-archive@tuta.com

⸻

🧾 Citation

Bache Archive (2025).
Chris Bache Archive (2009 – 2025) — public talks, book registries, transcripts, captions, and retrieval indices.
https://chrisbachearchive.com

⸻

📬 Contact

Bache Archive
📧 bache-archive@tuta.com

⸻

🕊️ Closing Reflection

May these materials remain accurate, accessible, and useful — for scholars, seekers, and systems alike.
Together with its sibling repositories, this corpus anchors a living, open framework dedicated to the faithful preservation of Christopher M. Bache’s voice and vision.
