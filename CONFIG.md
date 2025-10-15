# ⚙️ CONFIG.md — Bache Talks RAG System

**Version:** v3.0-alpha  
**Date:** 2025-10-15  
**Maintainer:** Bache Archive Project  
**Repositories:**  
- [`chris-bache-archive`](https://github.com/bache-archive/chris-bache-archive) — CC0 corpus and vectors  
- [`bache-rag-api`](https://github.com/bache-archive/bache-rag-api) — MIT backend service  

---

## 🧠 Core Parameters

| Parameter | Value | Description |
|------------|--------|-------------|
| **Corpus size** | 63 public talks (2014–2025) | All verified public lectures, interviews, and presentations. |
| **Total text volume** | ≈ 1,000,000 characters | Approximate combined text length across transcripts. |
| **Chunk count** | 2,817 | Paragraph-level segments (≈1,000–1,500 chars each, 80–120 overlap). |
| **Embedding model** | `text-embedding-3-large` | 3,072-dimensional OpenAI embedding model. |
| **Embedding dimension** | 3,072 | Size of each vector embedding. |
| **Vector index type** | FAISS `IndexFlatIP` | Cosine-normalized similarity search. |
| **Index file** | `vectors/bache-talks.index.faiss` | Binary FAISS index file. |
| **Metadata file** | `vectors/bache-talks.embeddings.parquet` | Parquet metadata table for chunks. |
| **Top-k retrieval** | 8 | Maximum number of nearest neighbors returned per query. |
| **MAX_PER_TALK** | 2 | Post-filter limit to ensure multi-talk diversity. |
| **Citation format** | `(YYYY-MM-DD, Title, chunk N)` | Standardized inline citation convention. |
| **Context limit** | ≈ 3,000 tokens | Max text window per synthesis call. |
| **RAG synthesis mode** | Deterministic compositor | Merges multi-talk excerpts into 2–6 sentence summaries. |

---

## 🧩 File Paths

chris-bache-archive/
├─ sources/transcripts/             # Markdown transcripts (CC0)
├─ vectors/
│   ├─ bache-talks.index.faiss      # FAISS cosine index
│   └─ bache-talks.embeddings.parquet
├─ manifests/                       # Per-talk SHA-256 manifest files
├─ checksums/                       # Release-level checksum files
├─ reports/                         # Evaluation logs
└─ tools/                           # ETL + embedding scripts

---

## 🌐 Deployment Configuration (Render)

| Environment Variable | Example / Description |
|----------------------|------------------------|
| `API_KEY` | `openssl rand -hex 32` — Authorization for all API routes |
| `OPENAI_API_KEY` | Valid OpenAI key for embeddings + completions |
| `FAISS_INDEX_PATH` | `vectors/bache-talks.index.faiss` |
| `METADATA_PATH` | `vectors/bache-talks.embeddings.parquet` |
| `EMBED_MODEL` | `text-embedding-3-large` |
| `EMBED_DIM` | `3072` |
| `MAX_PER_TALK` | `2` |

**Service:** [https://bache-rag-api.onrender.com](https://bache-rag-api.onrender.com)

---

## 🧪 Evaluation Snapshot

**Latest test:** [`reports/2025-10-15_gpt-eval_bache-talks.md`](reports/2025-10-15_gpt-eval_bache-talks.md)  
**Result:** ★★★★☆ (4.5 / 5)  
**Index statistics:**
- FAISS vectors: 2,817  
- Dimensions: 3,072  
- Metadata rows: 2,817  
- Load verified: ✅  
- OpenAI key present: ✅  

**Latency:** < 1.5 seconds / query (Render free tier)

---

## 🧾 Version Provenance

| Field | Value |
|-------|-------|
| **Commit hash** | `<fill from \`git rev-parse --short HEAD\`>` |
| **FAISS build date** | 2025-10-14 |
| **Parquet rows verified** | 2,817 |
| **Checksum log** | `checksums/RELEASE-v3.0-alpha.sha256` |
| **Manifest schema version** | 1.2 |
| **Embedding batch size** | 100 |
| **Overlap tokens** | ~80–120 |

---

## ✅ Acceptance Benchmarks

| Metric | Target | Status |
|---------|---------|---------|
| Transcript coverage | ≥ 98 % | ✅ Complete |
| Factual grounding | ≥ 90 % | ✅ Verified |
| Citations per answer | ≥ 2 | ✅ Met |
| Query latency | < 1.5 s | ✅ Achieved |
| FAISS + Metadata + Key | All True | ✅ Confirmed |
| Evaluation Score | ≥ 4 / 5 | ✅ 4.5 / 5 |

---

## 📜 Licensing

- **Corpus & Transcripts:** CC0 1.0 Universal (Public Domain Dedication)  
- **Codebase:** MIT License © 2025 Bache Archive Project

---

## 🌟 Notes for Future Versions

| Planned Improvement | Target Version |
|----------------------|----------------|
| Citation range compression (e.g., “chunks 12–15”) | v3.1 |
| Stylistic post-processing pass | v3.1 |
| Integration testing for multi-query threads | v3.2 |
| Longitudinal evaluation log automation | v3.3 |

---

> *This configuration defines the verifiable parameters of the Bache Talks RAG system at the moment it first went live (v3.0-alpha). Any reproduction of this system must match these values or declare explicit deviations.*
