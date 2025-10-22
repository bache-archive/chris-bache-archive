---
title: "{{title}}"
id: "{{id}}"
date: "{{date}}"
version: "v1"
source_policy: "Book-first. Public transcripts as color with timestamped links."
---

> {{preface_optional}}

## Primary citation (book)
**LSD and the Mind of the Universe** — {{book_citation}}  
_Editorial summary:_ {{book_summary}}

## Supporting transcript quotes
{{#each quotes}}
- “{{this.text}}” **[{{this.start}}]({{this.ts_url}})** — *{{this.title}}* ({{this.date}})
{{/each}}

## Editorial notes (optional)
- {{note1}}
- {{note2}}

## Provenance
- Built from `sources.json` on {{date}}.
- Cite as: _Christopher M. Bache — Public Talks (2014–2025), retrieved via Bache Talks RAG v1.2-rc1._
