# Anonymous Relaunch Baseline

The relaunch should first preserve the existing archive safely, then layer new public experiences on top.

## Baseline architecture

- `chris-bache-archive`: canonical corpus, transcript pages, static GitHub Pages site, vectors, checksums, and fixity tooling.
- `bache-rag-api`: FastAPI service for citation-grounded search and answers over the talk corpus.
- `bache-archive-meta`, `lsdmu-bibliography`, `bache-educational-docs`, `lsdmu-summaries-public`, and related repos: supporting metadata, bibliography, educational, and book-summary layers.

## First milestone

1. Keep the current GitHub Pages archive working as the preservation mirror.
2. Verify anonymous local Git identity and remote configuration with `make identity-audit`.
3. Rebuild and verify the current site before major feature work:

```bash
make finalize
```

4. Review all generated diffs before committing.
5. Only after the baseline is clean, create a separate Vercel frontend repo under `bache-archive`.

## Frontend milestone

- Build a Vercel-hosted public frontend that reads from the static archive and existing RAG API.
- Keep transcript source pages linkable and citation-friendly.
- Add a chat UI that displays retrieved citations and links back to source transcript pages.
- Do not expose raw ingestion, private email, or unpublished papers in the first public frontend.

## Content expansion milestone

- Public talks and Substack posts: add via documented source intake, metadata, transcript/page generation, sitemap update, checksums, and RAG rebuild.
- Papers from Chris: record permission and publication scope before adding public files.
- Emails: require explicit written permission, define private/public boundaries, and store raw exports outside the public archive.
