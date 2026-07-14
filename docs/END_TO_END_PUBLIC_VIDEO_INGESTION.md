# End-To-End Public Video Ingestion

This is the production workflow for a public YouTube video or batch. It covers
the preservation corpus, GitHub Pages mirror, RAG API, and
`chrisbachearchive.com` frontend.

## Readiness

The workflow is ready as a controlled, review-gated process. It is not intended
to be fully unattended because archival transcripts need human review for:

- rights/public-source scope
- speaker identity
- transcript quality
- final publication acceptance

Pilot status: the 2026-07-12 pilot on `KgqQiLkg1mM` validated metadata,
caption, audio, ASR, and speaker-ID command execution, but did not complete
full publication. Pyannote model access and OpenAI API quota blocked archival
diarization and transcript rebuild. See
`docs/PUBLIC_VIDEO_INGESTION_PILOT_2026-07-12.md`.

## Repositories

- Corpus, transcript, fixity, GitHub Pages mirror:
  `chris-bache-archive`
- RAG/search/answer API:
  `bache-rag-api`
- `chrisbachearchive.com` frontend:
  `bache-archive-web`

Use archive Git identity and remotes throughout:

```bash
make -C /Users/howardrhee/projects/bache-archive/chris-bache-archive identity-audit
```

## 1. Prepare A Batch

In `chris-bache-archive`, create a dated patch workspace:

```bash
BATCH_OUT=patches/YYYY-MM-DD-youtube-public-batch
mkdir -p "$BATCH_OUT/inputs"
$EDITOR "$BATCH_OUT/inputs/urls.txt"
```

Normalize URLs and check duplicates:

```bash
make prepare-youtube-batch BATCH_OUT="$BATCH_OUT" BATCH_URLS="$BATCH_OUT/inputs/urls.txt"
```

Fetch public metadata:

```bash
make fetch-youtube-metadata BATCH_OUT="$BATCH_OUT" BATCH_URLS="$BATCH_OUT/inputs/urls.txt"
```

Review:

- `outputs/intake_status.csv`
- `outputs/youtube_metadata.json`
- `work/index.patch.metadata.json`

Promote reviewed metadata to:

```text
work/index.patch.json
```

Edit titles, channels, source types, publication dates, slugs, and rights notes
before merge. Do not merge `TODO-*` slugs.

## 2. Merge Reviewed Metadata

```bash
python3 tools/curation/merge_index.py \
  --base index.json \
  --patch "$BATCH_OUT/work/index.patch.json" \
  --out "$BATCH_OUT/outputs/index.merged.json"
```

Review the diff:

```bash
git diff --no-index index.json "$BATCH_OUT/outputs/index.merged.json" || true
```

Adopt only after review:

```bash
cp "$BATCH_OUT/outputs/index.merged.json" index.json
```

## 3. Capture Source Artifacts

For each accepted slug:

```bash
make captions SLUG=<slug>
```

Stage public audio under ignored `downloads/audio/` using the media tooling or a
scoped `yt-dlp` command. Do not commit downloaded media.

## 4. Diarize And Identify Speakers

Create a diarization environment if needed:

```bash
python3.11 -m venv .venv-diarize
. .venv-diarize/bin/activate
pip install whisperx pyannote.audio torch torchaudio numpy pandas tqdm pyyaml
export PYANNOTE_TOKEN=<token>
```

The Hugging Face account behind `PYANNOTE_TOKEN` must have accepted all gated
models needed by the installed pyannote stack. For the current local stack this
includes:

- `pyannote/speaker-diarization-3.1`
- `pyannote/segmentation-3.0`
- `pyannote/speaker-diarization-community-1`

Run diarization:

```bash
make diarize DIAR_PYTHON=.venv-diarize/bin/python SLUG=<slug> AUDIO=downloads/audio/<slug>.mp3
```

Build or refresh the Chris reference clips when local source audio is present:

```bash
make speaker-reference
make speaker-reference-clips
```

Create a speaker-ID environment if needed:

```bash
python3.11 -m venv .venv-speakers
. .venv-speakers/bin/activate
pip install speechbrain torch torchaudio
```

Run speaker identity QA:

```bash
make speaker-identify SPEAKER_PYTHON=.venv-speakers/bin/python SLUG=<slug> AUDIO=downloads/audio/<slug>.mp3
```

Review `reports/diarization/<slug>.speaker_identity.json`. The report is a
suggestion, not an archival label. Confirm by listening before accepting labels.

## 5. Build Canonical Transcript

After speaker labels and raw diarist artifacts are accepted:

```bash
make transcript SLUG=<slug>
```

Review `sources/transcripts/<slug>.md`, including front matter, speaker names,
timestamps, citations/source links, and source provenance.

## 6. Finalize Corpus And GitHub Pages Mirror

```bash
make index
make finalize
```

Commit and push the corpus branch. GitHub Pages for the preservation mirror is
configured from the `main` branch root:

```text
https://bache-archive.github.io/chris-bache-archive/
```

The Pages mirror updates only after the accepted corpus changes reach `main`.

## 7. Rebuild RAG Artifacts

Only after canonical transcripts are accepted, rebuild vectors in
`chris-bache-archive`:

```bash
python3 tools/rag/chunk_transcripts.py
python3 tools/rag/embed_and_faiss.py
make audit-parquet
make finalize
```

Then update `bache-rag-api` with the expected vector artifacts and run
representative `/search` and `/answer` checks for:

- Diamond Luminosity
- Future Human
- reincarnation
- collective consciousness

Record vector count, metadata row count, and source corpus commit.

## 8. Update chrisbachearchive.com

In `bache-archive-web`:

```bash
npm run sync:archive
npm run typecheck
npm run lint
npm run build
```

Commit and push the web repo. Deploy the pushed commit to Vercel production for:

```text
https://chrisbachearchive.com
```

Vercel ownership is currently allowed under Howard's personal Vercel account,
while GitHub identity remains under `bache-archive`.

## 9. Acceptance Checklist

Before calling ingestion complete:

- `index.json` contains reviewed metadata and stable slugs.
- Captions, raw diarist files, transcript Markdown, HTML, sitemaps, checksums,
  manifests, and fixity are updated.
- Raw downloaded media and ML working artifacts remain ignored.
- GitHub Pages mirror is updated from `main`.
- RAG API uses vectors built from the accepted corpus commit.
- `chrisbachearchive.com` has the synced corpus data and passes production build.
- Representative frontend pages, search, and answer flows work.
