# CHANGELOG.md — Chris Bache Archive

All notable updates to the **Chris Bache Archive (2014–2025)** are documented here.  
This file complements `POLICIES.md` (rules of practice) and `EDITORIAL_NOTES.md` (specific decisions).  
Each entry summarizes what changed, when, and why.

---

## v3.1.4 — 2025-10-17
**Automated Session Registry**

Introduces a machine-readable + human-readable session framework for *LSD and the Mind of the Universe*.

- Added `tools/generate_sessions_html.py` → builds `SESSIONS.html` from JSON registries.
- Added rendered `sources/transcripts/lsdmu/SESSIONS.html`.
- Rebuilt `sitemap.xml` for inclusion.
- Validated cross-chapter (9) session references.

Ensures each of the 73 LSD sessions is represented as a structured, permanent object within the archive.

---

## v3.1.2 — 2025-10-16  
**Book Segmentation Framework**

This update adds the full structural registry for *LSD and the Mind of the Universe* (2019), launching the archive’s **Book Segmentation Layer**.

**Changes**
- Added `sources/transcripts/lsdmu/TOC.md` and `toc.json` — human- and machine-readable tables of contents.  
- Updated `lsdmu.section-registry.json` — verified all chapters and sections.  
- Regenerated HTML and rebuilt `sitemap.xml` (133 URLs).  
- Verified sitemap accessibility (`HTTP 200` for Googlebot & Bingbot).  

**Significance**
- Establishes a permanent book-level scaffold for future paragraph segmentation and edition alignment.  
- Confirms full crawler visibility and citation stability for v3.1.2.

---

## v3.1.1 — 2025-10-17  
**Roadmap Addition**

This maintenance release introduces a clear, future-oriented roadmap to guide the continued growth and stewardship of the **Chris Bache Archive**.

**Changes**
- Added `ROADMAP.md` — defines post-v3.1 development priorities, ranked by impact-to-effort.  
- Outlines four tiers of focus:  
  - 🥇 Book metadata & taxonomy  
  - 🥈 Enhanced RAG experience  
  - 🥉 Oral history & licensing opportunities  
  - 💡 Creative visualizations  
- Establishes regular maintenance cadence for fixity checks, metadata sweeps, and policy reviews.

**Significance**
- Provides a structured vision for future contributors while keeping scope realistic and mission-aligned.  
- Marks the close of the **v3.1** development cycle and the transition toward preservation, citation accuracy, and long-term governance.  

**Verification**
- All Markdown lint checks passed (UTF-8, no broken links).  
- Repository fixity intact (`git status` clean, `HEAD == origin/main`).  

---

## v3.1 — 2025-10-15
**Citation & URL Enrichment**

This release enhances the **Bache Talks RAG** system with human-readable citations and canonical URLs, improving both interpretability and scholarly referencing.

**Changes**
- Added `rag/citation_labels.json` (maps transcript paths → readable “Bache · date · venue · title” strings).  
- Extended `tools/embed_and_faiss.py` to:
  - Load citation labels and enrich all chunk metadata.  
  - Backfill canonical URLs from `index.json` (`web_url`, `youtube_url`, `media.*`).  
  - Embed enriched rows and rebuild FAISS index with stable numeric IDs.  
  - Emit extended QC report (`reports/embedding_qc.json`) showing sample enriched rows.
- Updated retriever and answer pipelines to display these human-readable citations in results.

**Verification**
- 2,561 chunks re-embedded → 3,072-dim vectors.
- Parquet and FAISS counts matched (`len(df) == idx.ntotal`).
- Retriever functional: citation strings and URLs returned as expected.

**Significance**
- Greatly improves user-facing output of both `/search` and `/answer` endpoints.  
- Establishes a consistent metadata bridge between the RAG layer and the archive index for future timecode mapping and web integration.

---

## v3.0.1 — 2025-10-15
**Maintenance · Provenance Alignment · Clean Public Tree**

- Pruned one legacy item from public sources (transcript, diarist, HTML) and rebuilt site assets (`sitemap.xml` + HTML).
- Quarantined the related manifest for internal provenance (`manifests/_quarantined/...json`).
- Regenerated sitemaps; verified no public references remain.
- Updated `checksums/FIXITY_LOG.md` with a v3.0.1 baseline entry.
- No new features; routine archival housekeeping and metadata alignment.

---

## v3.0-alpha.1 — 2025-10-14  
**Live RAG Deployment · API Integration · Evaluation**

This release advances the Bache Talks RAG from a local proof-of-concept to a **live, citation-grounded semantic service** hosted on Render, complete with Custom GPT integration and verified evaluation.

**New components**
- **API Backend:**  
  Added standalone repo [`bache-rag-api`](https://github.com/bache-archive/bache-rag-api) implementing a FastAPI service with `/search`, `/answer`, `/openapi.json`, `/_debug`, and `/_rag_status` endpoints.
- **Hosting:**  
  Deployed successfully on Render (free tier) — confirmed 2,817 vectors × 3,072 dimensions loaded, metadata verified, OpenAI key active.
- **Custom GPT Integration:**  
  Created *Bache Talks Librarian* using the live OpenAPI schema; fully functional and limited to RAG-only retrieval.
- **Documentation:**  
  Added `README_RAG.md`, `CONFIG.md`, and updated `CHANGELOG.md` to reflect live deployment.  
  Evaluation log committed at `reports/2025-10-15_gpt-eval_bache-talks.md`.

**Verification**
- `/search` and `/answer` endpoints respond under 1.5 s with correct multi-talk citations.  
- Evaluation score: ★★★★☆ (4.5 / 5) — verified cross-year synthesis and factual grounding.  
- Confirmed configuration:  

EMBED_MODEL=text-embedding-3-large
EMBED_DIM=3072
MAX_PER_TALK=2
FAISS_INDEX_PATH=vectors/bache-talks.index.faiss
METADATA_PATH=vectors/bache-talks.embeddings.parquet

- Retrieval capped at ≤2 chunks per talk for citation diversity.

**Significance**
- Establishes the first **live, verifiable semantic interface** for the Bache Talks corpus.  
- Completes transition from static archive → dynamic knowledge system.  
- Forms the operational base for v3.x longitudinal evaluation and stylistic refinement.

**Next**
- Implement citation-range compression (e.g., “chunks 12–15”).  
- Add stylistic polish pass and evaluation automation.
- Prepare v3.1 release with improved synthesis formatting and dashboard metrics.

---

## v3.0-alpha — 2025-10-14
**RAG Pipeline Foundation · Chunking · Embeddings · Retrieval**

This milestone marks the beginning of the **Bache Talks RAG (Retrieval-Augmented Generation)** system — transforming the archive from a static corpus into an interactive, searchable knowledge base.

**New components**
- **Chunking:** Added `tools/chunk_transcripts.py` to segment 63 verified transcripts into ~2,800 text chunks (1,200-char target, 100-char overlap).
- **Embeddings:** Added `tools/embed_and_faiss.py` to compute `text-embedding-3-large` vectors and build both **Parquet** and **FAISS** indexes.
- **Retrieval:** Added `rag/retrieve.py` (semantic search) and `rag/answer.py` (citation-grounded synthesis).
- **CLI Demo:** Added `demo/cli.py` for terminal-based query testing and verification.
- **Artifacts:** Created `CONFIG.md` (RAG params) and `.gitignore` entries for build outputs (`build/`, `vectors/`, `reports/`, `.env`).

**Verification**
- 2,817 chunks embedded successfully → 3,072-dim vectors indexed in FAISS.
- Queries for *“Diamond Luminosity”*, *“Future Human”*, and *“death and rebirth”* return precise, multi-talk results with correct citations.

**Significance**
- Establishes **v3.x** line as “functional archive” — preserving provenance **and** enabling live semantic access.
- Lays groundwork for forthcoming web demo (`app.py`) and scholarly RAG interface.

---

## v2.6-dev — 2025-10-13
**Book Segmentation Framework: LSD and the Mind of the Universe**

- Added first **book-level work** to the archive:  
  *LSD and the Mind of the Universe: Diamonds from Heaven* (2019).
- Introduced canonical section registry (`sources/transcripts/lsdmu/lsdmu.section-registry.json`).
- Added hardcover pagination alignment (`alignments/lsdmu/innertraditions-2019-hc.json`).
- Added audiobook alignment (`alignments/lsdmu/audiobook-2019.json`) — 76 total entries, 59 mapped `seg_id`s, 17 auxiliary.
- Added conversion tool `tools/convert_durations_to_alignment.py` for future audiobook imports.
- Updated `index.json` and `README.md` to reference new work.
- No transcript content changes; structural metadata extension only.

---

## v2.5.2 — 2025-10-13
**Metadata Consistency (Markdown)**

- Corrected transcriber/model attribution in **Markdown** transcripts to:
  `Otter.ai (diarized, speaker-attributed) + GPT-5 normalization`.
- Rebuilt per-item manifests and release checksums.
- Verified all 511 files: hashes match (`verify_fixity.py --update`).
- No content changes — metadata/provenance consistency only.

---

## v2.5.1 — 2025-10-13
**Metadata Consistency (HTML) & Indexing polish**

- Fixed transcriber attribution wording across **HTML** transcript pages.
- Minor sitemap/robots polish for search engine submission (no URL changes).
- No transcript content changes.

---

## v2.5 — 2025-10-12
**Fixity & Provenance Layer + Web Publication & Indexing**

### Provenance & Integrity
- Implemented permanent **cryptographic provenance**:
  - 70 per-item manifests in `/manifests/` with SHA-256, sources, tools, license.
  - Global ledger `checksums/RELEASE-v2.4.sha256` (covers 511 files) and `checksums/FIXITY_LOG.md`.
  - Deterministic rebuild + verification scripts: `build_manifests.py`, `verify_fixity.py`.

### Web Publication
- Generated `.html` renderings for all transcripts (`tools/generate_html.py`).
- Published GitHub Pages site with valid `sitemap.xml` and `robots.txt`.
- Submitted sitemap to Google Search Console and Bing Webmaster Tools.
- Verified HTTP 200 and correct MIME types for transcript `.html` and diarist `.txt`.

### Docs
- Updated `README.md` with “Web Publication & Indexing”.
- Added/updated policy notes in `POLICIES.md`.

---

## v2.4 — 2025-10-01
**Transcript Rebuilds from Diarists · Repo Unification · Clean Index**

This release provides version 2.4 of the Chris Bache Archive, a curated collection of transcripts, diarist files, captions, and metadata covering Chris Bache’s talks, interviews, and lectures (2014–2025).

**Key updates in v2.4**
- **Transcripts rebuilt from diarists:** All 68 transcripts regenerated from diarized sources, significantly improving speaker attribution. Earlier versions relied on captions + GPT inference, which sometimes mis-labeled speakers. (Minor residual errors may remain.)
- **Unified transcript paths:** All transcripts now live under `sources/transcripts/` (deprecates older `sources/` locations).
- **`index.json` cleaned:** Normalized filenames; corrected diarist/transcript/media references.
- **New transcript added:** *DMT Entity Encounters — Chapter 9 (Tyringham Hall)*.
- **Captions included:** Where available, original YouTube captions remain in `sources/captions/` for comparison.
- **Diarists preserved:** Raw diarized text files are included for transparency and future reprocessing.

**Notes**
- This bundle **excludes media** (audio/video). Media are preserved via dedicated Internet Archive collections and Zenodo deposit.
- License: **CC0 1.0 Universal** (public domain dedication).

---

## v2.3 — 2025-09-30
**Three New Recordings · Diarist Updates · Archive Re-org**

- Added three recordings (2020-01-10 ECR; 2020-05-13 Ryan & Mo; 2023-06-30 Inbodied Life).  
- Added matching Otter.ai diarized transcripts and readable transcript shells.  
- Reorganized repository under `sources/transcripts/`.  
- Updated `index.json` and `index.md`.  
- Standardized naming (`YYYY-MM-DD-slug`); reaffirmed CC0 1.0 Universal.

---

## v2.2.1 — 2025-09-30
**Complete Otter.ai Diarized Transcripts**

- Added remaining diarized `.txt` transcripts with speaker attribution.  
- Normalized filenames across layers; updated `README`.  
- Audio/video media unchanged since v2.1.1.

---

## v2.2 — 2025-09-29
**Initial Otter.ai Diarized Transcripts**

- Introduced `sources/diarist/` directory with first 10 transcripts.  
- Updated `README` to describe three-layer structure (*edited / captions / diarist*).  
- Media bundle unchanged (same as v2.1.1).  
- Dedicated to CC0 1.0 Universal.

---

## v2.1.1 — 2025-09-29
**First Release with Media Bundle**

- Added complete `downloads/video/` (MP4) + `downloads/audio/` (MP3).  
- Published `chris-bache-archive-v2.1.1-media.zip`.  
- Added `checksums.sha256`.  
- Established full audio/video preservation layer.

---

## v2.1 — 2025-09-29
**Media Automation & Archive Hygiene**

- Added `download_media.sh` (yt-dlp) to automate MP4/MP3 fetch.  
- Created `downloads/` substructure and updated `.gitignore`.  
- Normalized slugs (fixed punctuation, removed “prof.” period).  
- Media managed via Zenodo & Internet Archive.

---

## v2.0 — 2025-09-11
**CC0 Public Domain Dedication**

- All curated text + metadata released under **CC0 1.0 Universal**.  
- Source recordings remain © original creators.  
- Updated README + LICENSE.  
- No text changes — licensing/metadata only.

---

## v1.0.1 — 2025-09-09
**Minor Documentation & Metadata Patch**

- Fixed README links and metadata typos from initial release.  
- No content changes.

---

## v1.0 — 2025-09-09
**Initial Public Release**

- First public version of the Chris Bache Archive.  
- 59 cleaned transcripts of public talks + raw YouTube captions.  
- Licensed **CC BY 4.0** (predecessor to later CC0 dedication).

---

*End of CHANGELOG — maintained by bache-archive (2025-10-13).*