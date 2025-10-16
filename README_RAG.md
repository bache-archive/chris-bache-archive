# 📚 Bache Talks — Retrieval-Augmented Generation (RAG) System

**Version:** v3.1 · **Date:** 2025-10-15  
**Status:** ✅ Live on Render — [https://bache-rag-api.onrender.com](https://bache-rag-api.onrender.com)

---

## 🧭 Purpose

This system transforms the *Chris Bache Public Talks Archive (2014 – 2025)* into a **verifiable, citable semantic knowledge base**.  
It implements a full **Retrieval-Augmented Generation (RAG)** pipeline that converts 63 public talks into searchable paragraph-level vectors, enabling precise citation-grounded answers through a public API and the **Bache Talks Librarian** Custom GPT.

All source material is CC0-licensed and excludes copyrighted book text.

---

## 🏗 System Architecture

| Layer | Description |
|-------|--------------|
| **Corpus** | 63 verified Markdown transcripts (~1 M characters) stored under `sources/transcripts/`. |
| **Chunking** | ~2 800 overlapping paragraph-level chunks (1 000–1 500 chars, 80–120 char overlap). |
| **Embeddings** | `text-embedding-3-large` → 3 072-dim vectors (cosine-normalized). |
| **Indexing** | FAISS `IndexFlatIP` + Parquet metadata (talk ID, title, date, chunk index, sha256). |
| **Retrieval** | Top-k = 8 (≤ 2 per talk), filtered by similarity and source diversity. |
| **Synthesis** | Deterministic multi-talk compositor producing 2–6 sentence citation-grounded answers. |
| **Metadata v3.1** | Each chunk now includes a human-readable `citation` and canonical `url` (backfilled from `index.json`). |
| **Serving** | FastAPI backend (`bache-rag-api/`) exposing `/search`, `/answer`, `/_debug`, and `/_rag_status`. |

---

## ⚙️ Reproducibility Pipeline

1. **ETL + Chunking**  
   `tools/chunk_transcripts.py`  
   → splits transcripts → `vectors/chunks.jsonl`

2. **Embedding (v3.1)**  
   `tools/embed_and_faiss.py`  
   - Calls OpenAI `text-embedding-3-large`  
   - Attaches human-readable citations (from `rag/citation_labels.json`)  
   - Backfills canonical URLs (from `index.json`)  
   → writes `vectors/bache-talks.embeddings.parquet`

3. **FAISS Index**  
   Builds cosine-normalized `vectors/bache-talks.index.faiss`

4. **Verification**  
   Each chunk hashed (SHA-256) and listed in per-talk manifests.  
   Release-level fixity recorded in `checksums/RELEASE-<version>.sha256`.

5. **Deployment**  
   Upload both index files (`.faiss` + `.parquet`) to the Render-hosted API.  
   Configure environment variables as listed in `CONFIG.md`.

---

## 🌐 API Overview

**Repository:** [`bache-rag-api`](https://github.com/bache-archive/bache-rag-api)  
**Live service:** [https://bache-rag-api.onrender.com](https://bache-rag-api.onrender.com)

| Endpoint | Method | Function |
|-----------|---------|-----------|
| `/search` | POST | Semantic nearest-neighbor search (with citation & URL metadata). |
| `/answer` | POST | Citation-grounded synthesis from retrieved chunks. |
| `/_rag_status` | GET | Confirms FAISS + metadata + OpenAI key load status. |

Example:
```bash
curl -X POST https://bache-rag-api.onrender.com/answer \
  -H "Authorization: Bearer <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"query":"What does Bache mean by Diamond Luminosity?"}'


⸻

🤖 Custom GPT Integration

Name: Bache Talks Librarian
Schema URL: https://bache-rag-api.onrender.com/openapi.json
Auth: Authorization: Bearer <API_KEY>

GPT logic:
	1.	Call /search (top_k = 8).
	2.	Compose a 2–6 sentence answer using only retrieved context.
	3.	Include citations using the new human-readable form plus URL.
	4.	If no results, reply that none were found and suggest refinements.

⸻

🧪 Evaluation

Report: reports/2025-10-15_gpt-eval_bache-talks.md
Result: ★★★★☆ (4.6 / 5) — Improved metadata fidelity

Strengths
	•	Cross-temporal synthesis from multiple talks
	•	Readable citations + live URLs for source verification
	•	Fast retrieval (< 1.5 s)
	•	Consistent chunk-level alignment with archive index

Next steps
	•	Add optional timecode anchors from caption files
	•	Integrate multi-format retrieval (book sections, interviews)
	•	Support hybrid keyword + semantic search

⸻

📦 Directory Map

chris-bache-archive/
├─ sources/transcripts/      # 63 verified Markdown transcripts
├─ vectors/                  # FAISS + Parquet index (v3.1 enriched)
├─ rag/                      # Citation labels + retriever modules
├─ manifests/, checksums/    # Provenance & fixity layers
├─ tools/                    # ETL + build scripts
├─ reports/                  # Evaluation + QC logs
├─ README_RAG.md             # (this file)
├─ CONFIG.md                 # Model + parameter config
└─ CHANGELOG.md              # Version history


⸻

✅ Acceptance Criteria

Metric	Target	Status
Transcript coverage	≥ 98 %	✅ Complete
Factual grounding	≥ 90 %	✅ Verified
Readable citations + URLs	100 %	✅ Enriched
Query latency	< 1.5 s	✅ Achieved
FAISS + Metadata + Key	All True	✅ Confirmed
Evaluation Score	≥ 4 / 5	✅ 4.6 / 5


⸻

📜 Licensing & Citation
	•	Corpus: CC0 1.0 Universal (Public Domain Dedication)
	•	Code: MIT License © 2025 Bache Archive

Citation format:

Christopher M. Bache — Public Talks (2014 – 2025), Bache · YYYY-MM-DD · Venue · Title, chunk N.
[YouTube URL]

⸻

🌟 North Star

Preserve the living voice of Christopher M. Bache’s public teachings through a clean, verifiable semantic interface for researchers, seekers, and future AIs.
Together, the CC0 data repo (chris-bache-archive/) and the MIT-licensed backend (bache-rag-api/) form a trustworthy bridge between historical archive and living dialogue.

“A luminous record of the awakening of the species — faithfully preserved for the Future Human.”
