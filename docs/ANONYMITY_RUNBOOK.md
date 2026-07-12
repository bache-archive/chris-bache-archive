# Bache Archive Anonymity Runbook

This project should remain operationally separate from personal GitHub, Vercel, email, domain, and API identities.

## Current local guardrails

- Local repository root: `/Users/howardrhee/projects/bache-archive/chris-bache-archive`
- GitHub owner: `bache-archive`
- SSH host alias: `github-bache`
- SSH key: `~/.ssh/id_ed25519_bache`
- Commit identity: `Bache Archive <bache-archive@tuta.com>`
- Canonical remote shape: `git@github-bache:bache-archive/<repo>.git`

Run this before any archive commit, push, dependency install, Vercel link, or deployment:

```bash
make identity-audit
```

## Rules for future work

- Use only the `github-bache` SSH host alias for archive repositories.
- Do not push archive work through `https://github.com/...`, the default `github.com` SSH host, or a personal `gh` login.
- Use the archive email for commits, GitHub notifications, Vercel ownership, domain registration, and API/vendor accounts wherever feasible.
- Keep raw private materials, email exports, OAuth tokens, API keys, and local `.env` files out of Git.
- Treat GitHub Pages as the preservation mirror. Use Vercel for a separate public frontend only after linking it from the archive-owned Vercel account or team.
- Do not ingest Chris's email or private papers until written permission, scope, and publication rules are recorded.

## Pre-flight checklist

1. `make identity-audit` passes.
2. `git status --short --branch` shows only the intended files.
3. `git remote -v` uses `git@github-bache:bache-archive/...`.
4. `git config --local user.name` is `Bache Archive`.
5. `git config --local user.email` is `bache-archive@tuta.com`.
6. Any deployment target is owned by the archive identity, not a personal identity.

## Known local cautions

- The machine global Git identity is personal. Archive repos must rely on local repo config.
- Some sibling repos may have unrelated local changes. Do not clean or overwrite them without reviewing their purpose.
- Local secret-looking files in this repo, including `tools/.env`, `tools/client_secret.json`, and `tools/token.json`, are ignored and should remain untracked.
