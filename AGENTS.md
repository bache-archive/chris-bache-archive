# Chris Bache Archive Agent Instructions

This repository is the canonical preservation corpus. Treat provenance, fixity, and identity separation as higher priority than feature speed.

## Codex Startup From This Repo

- These instructions must be sufficient when Codex CLI is started from this repository instead of `/Users/howardrhee/projects/bache-archive`.
- Also read `../AGENTS.md` and `../CODEX_WORKSPACE.md` when they are available; they contain cross-repo policy and current workspace priorities.
- Use `AGENTS.md` for durable Codex instructions. Do not create `CODEX.md` unless a separate non-Codex tool explicitly requires it.
- For GitHub CLI commands, set `GH_CONFIG_DIR="$HOME/.config/gh-bache"` so archive auth does not overwrite or use personal GitHub accounts.
- Start broad archive work from `/Users/howardrhee/projects/bache-archive`; keep corpus/transcript/fixity implementation work in this repo.
- Web/frontend/domain work belongs in `../bache-archive-web`.
- RAG/API/chat-answer work belongs in `../bache-rag-api`.

## GitHub Issue Ownership

When taking on a GitHub issue, always mark it as in progress before starting local work so other agents can see it is claimed.

1. Read recent issue comments first. If another agent already owns the issue and there is no clear handoff or completion note, do not duplicate the work.
2. Before any code change, branch creation, or dependency install, post a claim comment on the issue using this exact format:

```text
🤖 In progress — branch agent/issue-{N}-{short-slug}
```

3. After posting the claim comment, try to add the GitHub label:

```bash
GH_CONFIG_DIR="$HOME/.config/gh-bache" gh issue edit {N} --add-label "in-progress"
```

If the label does not exist or permissions do not allow it, do not block on that step. The claim comment is still required.

4. Then create the branch and start implementation.
5. When the work is done, blocked, or handed off, comment again with the outcome. If the issue was labeled `in-progress`, remove that label when appropriate.

## Required Checks

- Run `make identity-audit` before commits, pushes, dependency installs, Vercel links, or deployments.
- Run `make finalize` after archive content, transcript, sitemap, checksum, or manifest changes.
- If the default Python environment lacks `markdown`, use a repo-local virtualenv or an explicit compatible interpreter; do not mutate system Python.

## Git Identity

- Remote must be `git@github-bache:bache-archive/chris-bache-archive.git`.
- Local Git identity must be `Bache Archive <bache-archive@tuta.com>`.
- Do not use personal GitHub CLI auth or personal GitHub remotes. Vercel is currently allowed under Howard's personal Vercel account by explicit user choice.
- The canonical public domain is `https://chrisbachearchive.com`; treat `www.chrisbachearchive.com` and shorter domains as redirects/aliases.

## Content Policy

- Public talks and public pages can enter the archive after source metadata is captured.
- Chris's private emails, private papers, or unpublished materials require explicit written permission and a recorded publication scope before ingestion.
- Preserve raw ASR, diarization, captions, and source metadata separately from edited transcript output.
- LLM cleanup is an editorial pass only. Never let an LLM-cleaned transcript replace source artifacts without provenance.

## Pipeline Expectations

- Prefer structured ingestion: source URL -> metadata -> audio/caption capture -> diarized transcript -> normalized Markdown/HTML -> checksums/manifests -> RAG rebuild.
- For public YouTube/video ingestion, follow `docs/END_TO_END_PUBLIC_VIDEO_INGESTION.md`. Treat `make add` and `make quick` as legacy helpers, not the production batch workflow.
- Keep generated media and private working files ignored.
- Keep public transcript URLs stable whenever possible.
