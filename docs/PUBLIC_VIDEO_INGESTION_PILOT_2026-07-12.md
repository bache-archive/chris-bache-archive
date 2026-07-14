# Public Video Ingestion Pilot - 2026-07-12

Pilot video:

- YouTube ID: `KgqQiLkg1mM`
- URL: `https://youtu.be/KgqQiLkg1mM`
- Title: `73 LSD Sessions / Journey through the Mind of the Universe?`
- Channel: `Magical Egypt`
- Published: `2026-05-31`
- Duration: `29:04`
- Pilot slug: `2026-05-31-73-lsd-sessions-journey-through-the-mind-of-the-universe`

## Result

The workflow is partially tested but not ready to call fully end-to-end.

Validated:

- URL normalization and duplicate detection.
- Public YouTube metadata fetch.
- One-record reviewed patch generation and merge dry run.
- Caption download.
- Local audio staging under ignored `downloads/audio/`.
- WhisperX ASR smoke test with `DIAR_MODEL=tiny`.
- Speaker-ID command execution against existing Chris reference clips.

Blocked or not publication-ready:

- Pyannote speaker diarization did not run. At the time of the pilot, the
  configured Hugging Face token could not access the gated
  `pyannote/speaker-diarization-3.1` model. A later local check confirmed
  access to `pyannote/speaker-diarization-3.1` and `pyannote/segmentation-3.0`,
  but current `pyannote.audio` also requires
  `pyannote/speaker-diarization-community-1`.
- The resulting diarist output fell back to one speaker, so it cannot distinguish
  Chris from the host and is not archival speaker attribution.
- Canonical transcript rebuild could not run because the configured OpenAI API
  key returned `insufficient_quota`.
- RAG rebuild, web sync, GitHub Pages update, and production deploy were not run
  because no accepted canonical transcript was produced.

## Bugs Found And Fixed

- `tools/diarist/diarize_talk.py` now supports both `token=` and legacy
  `use_auth_token=` for `Pipeline.from_pretrained`.
- `tools/diarist/diarize_talk.py` no longer applies category-style lexicon
  lists as destructive text substitutions.
- `Makefile` `transcript` target now supports `TRANSCRIPT_PYTHON` and stops on
  command failures.
- `tools/transcripts/rebuild_transcripts.py` now exits nonzero when any item
  errors.

## Follow-Up Required

1. Accept the gated pyannote model terms for the Hugging Face account tied to
   `PYANNOTE_TOKEN`, including `pyannote/speaker-diarization-community-1`, or
   switch the workflow to a non-gated diarization backend.
2. Restore OpenAI API quota or configure a working archive transcription model
   endpoint.
3. Rerun this pilot with production settings, ideally on a faster GPU/cloud
   runner:

```bash
set -a; source .env; set +a
make diarize \
  DIAR_PYTHON=.venv-diarize/bin/python \
  SLUG=2026-05-31-73-lsd-sessions-journey-through-the-mind-of-the-universe \
  AUDIO=downloads/audio/2026-05-31-73-lsd-sessions-journey-through-the-mind-of-the-universe.mp3 \
  DIAR_MODEL=large-v3 \
  DIAR_NUM_SPEAKERS=2
```

4. Only after speaker labels and transcript text are reviewed should the pilot
   enter `index.json`, `sources/transcripts/`, fixity, RAG, web sync, and
   deployment.
