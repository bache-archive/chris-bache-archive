# Public Talk Transcription Pipeline

This workflow replaces the old manual YouTube download -> Otter diarization -> LLM cleanup process.

## Source Intake

For each public item, record:

- Source URL
- Original title
- Channel or publisher
- Published or recorded date
- Rights / public availability note
- Whether source captions already exist
- Target slug

Do not add private emails, private papers, or unpublished files until permission and publication scope are recorded.

## Recommended Tool Order

1. `yt-dlp` + `ffmpeg` for public source metadata, captions, audio extraction, and source preservation.
2. OpenAI `gpt-4o-transcribe-diarize` for speaker-aware transcript JSON when cloud processing is acceptable.
3. WhisperX + pyannote for local/offline or reproducibility-sensitive diarized transcripts.
4. AssemblyAI as a managed fallback when utterance confidence, word timings, or provider comparison is useful.
5. LLM editorial cleanup only after raw ASR and diarization artifacts are saved.

## Artifact Layout

For each slug, preserve:

- `sources/captions/<slug>.vtt` when source captions exist.
- `sources/diarist/<slug>.json` or `.txt` for raw diarized transcript output.
- `sources/transcripts/<slug>.md` for the edited canonical transcript.
- `manifests/<slug>.json` for source metadata, checksums, and provenance.
- Optional working files under ignored local paths only.

## Quality Gate

- Confirm speaker labels for Chris, host, and audience segments.
- For newly diarized files, use `make speaker-identify` when local reference clips
  are available, then confirm the suggested Chris cluster by review.
- Spot-check at least 5 minutes or 10% of the source, whichever is smaller.
- Confirm timestamp anchors link to the original video/audio when available.
- Run `make finalize`.
- Rebuild RAG vectors only after the canonical transcript is accepted.

## Current Repo Commands

For an individual public talk slug, prefer the Makefile wrapper so future script moves stay centralized:

```bash
make add SLUG=<yyyy-mm-dd-title> YT=<public_source_url>
make captions SLUG=<yyyy-mm-dd-title>
make diarize SLUG=<yyyy-mm-dd-title> AUDIO=<path-to-audio.mp3>
make transcript SLUG=<yyyy-mm-dd-title>
make index
make site
make sitemaps
make finalize
```

`make diarize` is the preferred replacement for the old Otter export step. It wraps `tools/diarist/diarize_talk.py`, which uses WhisperX for ASR/alignment and pyannote for speaker turns. It writes `sources/diarist/<slug>.txt`, `.srt`, and `.json`.

`make transcript` expects the raw diarist text at `sources/diarist/<slug>.txt` and uses `tools/transcripts/rebuild_transcripts.py`. Preserve the raw diarist files before running any LLM cleanup.

## Frontend Contract

The web frontend should consume generated public metadata, not raw working files. Public pages can link to:

- Canonical transcript HTML
- Markdown source
- Original public video/audio source
- RAG citations with stable transcript URLs
