#!/usr/bin/env python3
from typing import List, Dict

# -------- helpers --------

def _trim(s: str, limit: int = 500) -> str:
    s = (s or "").strip().replace("\n", " ")
    if len(s) <= limit:
        return s
    cut = s[:limit]
    # try to cut on a word boundary
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,;—") + "…"

def _inline_cite(row: Dict) -> str:
    """
    Prefer human-readable 'citation' from embeddings metadata.
    Fallback to (date, title) if needed. Always show chunk index.
    """
    label = (row.get("citation") or "").strip()
    if not label:
        title = (row.get("archival_title") or "").strip()
        date  = (row.get("published") or row.get("recorded_date") or "").strip()
        label = f"{date}, {title}".strip(", ")
    idx = int(row.get("chunk_index", 0))
    return f"({label}, chunk {idx})"

def format_sources(hits: List[Dict], max_sources: int = 6) -> str:
    """
    Render a readable 'Sources' block with human-friendly labels and URLs.
    De-duplicates by (talk_id, chunk_index) while preserving order.
    """
    seen = set()
    lines = []
    for h in hits:
        key = (h.get("talk_id"), int(h.get("chunk_index", 0)))
        if key in seen:
            continue
        seen.add(key)

        label = (h.get("citation") or "").strip()
        if not label:
            title = (h.get("archival_title") or "").strip()
            date  = (h.get("published") or h.get("recorded_date") or "").strip()
            label = f"{date}, {title}".strip(", ")

        idx = int(h.get("chunk_index", 0))
        url = (h.get("url") or "").strip()

        line = f"— {label} · chunk {idx}"
        if url:
            line += f" · {url}"
        lines.append(line)

        if len(lines) >= max_sources:
            break

    return "\n".join(lines)

# -------- main composer --------

def answer_from_chunks(query: str, hits: List[Dict], max_snippets: int = 3) -> str:
    """
    Ultra-simple extractive composer:
      - picks up to `max_snippets` strongest chunks
      - returns a concise synthesis with an appended Sources block
      - uses human-readable citation labels
    """
    if not hits:
        return "I don’t have sufficient context to answer. Try adding a date, venue, or specific term."

    # Take top N chunks as supporting snippets
    top = hits[:max_snippets]
    snippets = []
    for h in top:
        txt = _trim(h.get("text", ""), limit=500)
        snippets.append(f"{txt} {_inline_cite(h)}")

    synthesis = "Based on the archived talks, here are the most relevant passages:"
    body = " ".join(snippets)

    # Sources block
    sources_block = format_sources(hits)

    return f"{synthesis} {body}\n\nSources:\n{sources_block}"