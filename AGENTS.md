# Chris Bache Archive Agent Instructions

This repository is the canonical preservation corpus. Treat provenance, fixity, and identity separation as higher priority than feature speed.

## Required Checks

- Run `make identity-audit` before commits, pushes, dependency installs, Vercel links, or deployments.
- Run `make finalize` after archive content, transcript, sitemap, checksum, or manifest changes.
- If the default Python environment lacks `markdown`, use a repo-local virtualenv or an explicit compatible interpreter; do not mutate system Python.

## Git Identity

- Remote must be `git@github-bache:bache-archive/chris-bache-archive.git`.
- Local Git identity must be `Bache Archive <bache-archive@tuta.com>`.
- Do not use personal GitHub CLI auth or personal GitHub remotes. Vercel is currently allowed under Howard's personal Vercel account by explicit user choice.

## Content Policy

- Public talks and public pages can enter the archive after source metadata is captured.
- Chris's private emails, private papers, or unpublished materials require explicit written permission and a recorded publication scope before ingestion.
- Preserve raw ASR, diarization, captions, and source metadata separately from edited transcript output.
- LLM cleanup is an editorial pass only. Never let an LLM-cleaned transcript replace source artifacts without provenance.

## Pipeline Expectations

- Prefer structured ingestion: source URL -> metadata -> audio/caption capture -> diarized transcript -> normalized Markdown/HTML -> checksums/manifests -> RAG rebuild.
- Keep generated media and private working files ignored.
- Keep public transcript URLs stable whenever possible.
