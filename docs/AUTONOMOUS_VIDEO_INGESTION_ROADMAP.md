# Autonomous Video Discovery And Ingestion Roadmap

This document describes the target "human-zero effort" system for public Chris
Bache videos. It also records the current readiness boundary so future agents do
not confuse a controlled workflow with a fully autonomous one.

## Current State

As of 2026-07-15, the archive has the pieces needed for a controlled
end-to-end public YouTube ingestion run:

- YouTube discovery: `tools/intake/find_bache_videos.py`
- Batch URL normalization and duplicate detection:
  `make prepare-youtube-batch`
- Public metadata fetch through `yt-dlp`: `make fetch-youtube-metadata`
- Caption capture: `make captions`
- Local diarization with WhisperX and pyannote: `make diarize`
- Chris Bache speaker reference manifest: `make speaker-reference`
- Speaker identity QA: `make speaker-identify`
- Canonical transcript rebuild: `make transcript`
- Corpus publication/fixity: `make finalize`
- YouTube playlist sync: `make playlist-sync`
- Web frontend sync: `cd ../bache-archive-web && npm run sync:archive`
- RAG rebuild scripts under `tools/rag/`

The earlier URL batch is staged at:

```text
patches/2026-07-15-youtube-public-batch
```

That batch contains 15 new public videos with fetched metadata. One supplied
URL, `IBCN4z5P-8s`, was already indexed.

## Not Yet Human-Zero

The current workflow should still be treated as controlled and review-gated.
The unresolved automation gaps are:

- No scheduled runner is configured to invoke discovery periodically.
- Candidate acceptance still needs policy logic for public-source scope,
  duplicates, channel trust, title relevance, duration, and likely Chris
  participation.
- Diarization can run, but speaker identity labels still need confidence
  thresholds and spot-check policy before being accepted without review.
- Transcript cleanup can run, but there is not yet an automated transcript QA
  gate for hallucinated edits, missing timestamps, speaker swaps, or low-ASR
  sections.
- RAG vector rebuild, API deployment/checking, web deployment, GitHub Pages
  publication, and YouTube playlist sync are not yet orchestrated as one durable
  workflow with resumable state.
- There is no automatic issue/PR handoff for uncertain candidates or failed
  media/transcription jobs.

## Target Autonomous Loop

The desired mature system is:

1. On a schedule, search YouTube for new Chris Bache candidates.
2. Compare candidates against `index.json`, previous discovery reports, and
   denied/accepted candidate history.
3. Auto-create a dated patch workspace for high-confidence public candidates.
4. Fetch public metadata, captions, and local audio artifacts.
5. Diarize and run Chris speaker identity QA.
6. Generate canonical transcript drafts with source timestamps and speaker
   labels.
7. Run automated QA:
   - source URL reachable
   - metadata complete
   - captions or ASR present
   - Chris speaker confidence above threshold
   - timestamp anchors present
   - transcript length and language plausible
   - no private/local artifacts staged
8. If the candidate is high-confidence, finalize corpus and open a PR or merge
   according to the archive policy at that time.
9. Rebuild RAG vectors from the accepted corpus commit and run representative
   `/search` and `/answer` checks.
10. Sync and deploy `bache-archive-web`.
11. Sync the public YouTube playlist from accepted `index.json` entries.
12. Report the run: new videos accepted, rejected, uncertain, corpus commit,
   GitHub Pages status, RAG status, web deployment URL, and playlist URL.

## Recommended First Automation Milestone

Build a scheduled discovery job before building unattended publication.

The safe first milestone is a GitHub Actions or external Codex scheduled job
that runs weekly or monthly:

```bash
make install-ingest-deps
make find-youtube-candidates \
  DISCOVERY_AFTER=<last-run-date> \
  DISCOVERY_BEFORE=<today> \
  DISCOVERY_MAX_PER_QUERY=20
```

The job should commit or attach only candidate reports, not transcripts or media,
and open an issue or PR for review. This keeps discovery automatic while
preserving the archive's standards for speaker identity and transcript fidelity.

## Toward Unattended Publication

After discovery is reliable, add automation in this order:

1. Candidate registry with accepted, rejected, duplicate, and uncertain states.
2. A resumable ingestion state file per video.
3. Automated audio/caption download with media kept ignored.
4. Diarization and speaker-ID scoring thresholds.
5. Transcript QA checks against raw ASR and timestamps.
6. Corpus finalization and fixity verification.
7. RAG rebuild and API smoke tests.
8. Web sync/build/deploy verification.
9. YouTube playlist dry-run, then apply mode.
10. End-of-run report and issue/PR comments.

Human-zero publication should only be enabled after the acceptance thresholds
are calibrated on several reviewed videos.
