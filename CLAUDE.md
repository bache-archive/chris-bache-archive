# Claude Code Instructions

This repo is the canonical preservation corpus. Read `AGENTS.md` first, then
read parent workspace instructions when available:

- `../AGENTS.md`
- `../CODEX_WORKSPACE.md`
- `../SOUL.md`

Optimization target:

- Future repo operators are coding AI agents with very large context windows.
- Prefer machine-readable workflow state and command manifests over
  human-oriented prose.
- For autonomous public video ingestion, start from
  `docs/AGENT_AUTONOMOUS_VIDEO_INGESTION_SPEC.json`.
- Current staged URL batch status is written by:

```bash
make youtube-batch-status BATCH_OUT=patches/2026-07-15-youtube-public-batch
```

Identity boundary:

- Use `GH_CONFIG_DIR="$HOME/.config/gh-bache"` for GitHub CLI.
- Remote must be `git@github-bache:bache-archive/chris-bache-archive.git`.
- Local Git identity must be `Bache Archive <bache-archive@tuta.com>`.
- Do not commit `.env*`, `tools/client_secret.json`, `tools/token.json`,
  downloaded media, private material, OAuth tokens, API keys, logs, `reports/`,
  or local ML working artifacts.

Codex note:

- Do not add `CODEX.md`. Codex uses `AGENTS.md` in this workspace.
