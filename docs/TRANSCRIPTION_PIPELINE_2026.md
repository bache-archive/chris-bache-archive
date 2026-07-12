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
- Spot-check at least 5 minutes or 10% of the source, whichever is smaller.
- Confirm timestamp anchors link to the original video/audio when available.
- Run `make finalize`.
- Rebuild RAG vectors only after the canonical transcript is accepted.

## Frontend Contract

The web frontend should consume generated public metadata, not raw working files. Public pages can link to:

- Canonical transcript HTML
- Markdown source
- Original public video/audio source
- RAG citations with stable transcript URLs

