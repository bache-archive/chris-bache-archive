# Video Batch Ingestion

Use this workflow for public YouTube batches before any media download,
diarization, transcript editing, RAG rebuild, or frontend sync.

For the complete cross-repo publication path, see
`docs/END_TO_END_PUBLIC_VIDEO_INGESTION.md`.

## 1. Stage URLs

Put public YouTube URLs in a dated patch workspace:

```bash
patches/YYYY-MM-DD-youtube-public-batch/inputs/urls.txt
```

Use normalized `https://youtu.be/<id>` URLs when possible. Tracking parameters
such as `?si=...` are not preserved.

## 2. Prepare Offline Batch Artifacts

```bash
make prepare-youtube-batch \
  BATCH_OUT=patches/YYYY-MM-DD-youtube-public-batch \
  BATCH_URLS=patches/YYYY-MM-DD-youtube-public-batch/inputs/urls.txt
```

This writes:

- `inputs/urls.normalized.txt`
- `outputs/intake_status.csv`
- `work/new_video_ids.txt`
- `work/existing_video_ids.txt`
- `work/index.patch.skeleton.json`

The skeleton patch is intentionally not merge-ready. Fill title, channel,
published date, duration, source type, and final slug before promoting it to
`work/index.patch.json`.

## 3. Fetch Public Metadata

Run this in a network-capable shell with current `yt-dlp`:

```bash
make fetch-youtube-metadata \
  BATCH_OUT=patches/YYYY-MM-DD-youtube-public-batch \
  BATCH_URLS=patches/YYYY-MM-DD-youtube-public-batch/inputs/urls.txt
```

Use `outputs/youtube_metadata.json` and `work/index.patch.metadata.json` to
complete reviewed `work/index.patch.json`, then merge with:

```bash
python3 tools/curation/merge_index.py \
  --base index.json \
  --patch patches/YYYY-MM-DD-youtube-public-batch/work/index.patch.json \
  --out patches/YYYY-MM-DD-youtube-public-batch/outputs/index.merged.json
```

Review the diff before replacing `index.json`.

## 4. Ingest Each Accepted Slug

For each accepted slug:

```bash
make captions SLUG=<slug>
make diarize SLUG=<slug> AUDIO=<path-to-audio.mp3>
make transcript SLUG=<slug>
```

The preferred replacement for the old Otter step is:

1. Download or otherwise stage the public audio locally.
2. Run `make diarize`, which wraps `tools/diarist/diarize_talk.py`.
3. Inspect `sources/diarist/<slug>.json`, `.srt`, and `.txt`.
4. Run `make speaker-identify` when reference clips and speaker ML dependencies
   are available.
5. Identify which generated speaker labels correspond to Chris, host, audience,
   or unknown speakers.
6. If needed, rerun with mappings through `DIAR_EXTRA`, for example
   `DIAR_EXTRA='--map-speaker SPEAKER_00=Chris_Bache'`. Use underscores or
   another stable no-space label during diarization, then normalize display
   names during transcript cleanup if needed.
7. Only then run `make transcript`.

The diarizer uses WhisperX for ASR/alignment and pyannote for speaker turns. It
requires a local ML environment plus a Hugging Face token accepted for the
pyannote speaker-diarization model and its gated submodels:

```bash
export PYANNOTE_TOKEN=<token>
python3 -m venv .venv-diarize
. .venv-diarize/bin/activate
pip install whisperx pyannote.audio torch torchaudio numpy pandas tqdm pyyaml
make diarize DIAR_PYTHON=.venv-diarize/bin/python SLUG=<slug> AUDIO=<path-to-audio.mp3>
```

For current `pyannote.audio` releases, accept at least these Hugging Face model
terms for the account behind `PYANNOTE_TOKEN`:

- `pyannote/speaker-diarization-3.1`
- `pyannote/segmentation-3.0`
- `pyannote/speaker-diarization-community-1`

Otter should now be treated as a legacy fallback or comparison source, not the
normal archival path. Preserve raw diarized artifacts under `sources/diarist/`
before transcript cleanup.

## 5. Finalize and Hand Off

After transcripts are reviewed:

```bash
make finalize
```

Then rebuild downstream systems:

- RAG/API: rebuild vectors in `chris-bache-archive`, copy/update the expected
  artifacts in `bache-rag-api`, and run representative `/search` and `/answer`
  checks.
- Web: in `bache-archive-web`, run
  `npm run sync:archive && npm run typecheck && npm run lint && npm run build`.
