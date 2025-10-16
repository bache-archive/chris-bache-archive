#!/usr/bin/env python3
from typing import List, Dict, Optional, Set, Tuple

# -------- helpers --------

def _trim(s: Optional[str], limit: int = 500) -> str:
    s = (s or "").strip().replace("\n", " ")
    if len(s) <= limit:
        return s
    cut = s[:limit]
    # try to cut on a word boundary
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,;—") + "…"

def _label_from_row(row: Dict) -> str:
    """
    Prefer human-readable 'citation'. Fallback to "DATE, TITLE".
    """
    label = (row.get("citation") or "").strip()
    if label:
        return label
    title = (row.get("archival_title") or "").strip()
    date  = (row.get("published") or row.get("recorded_date") or row.get("date") or "").strip()
    fallback = f"{date}, {title}".strip(", ")
    return fallback or "Source"

def _inline_cite(row: Dict) -> str:
    """
    Inline citation: "(Label, chunk N)".
    """
    label = _label_from_row(row)
    idx = int(row.get("chunk_index", 0) or 0)
    return f"({label}, chunk {idx})"

def format_sources(hits: List[Dict], max_sources: int = 6) -> str:
    """
    Render a readable 'Sources' block with human-friendly labels and URLs.
    De-duplicates by (talk_id, chunk_index) while preserving order.
    """
    seen: Set[Tuple[Optional[str], int]] = set()
    lines: List[str] = []
    for h in hits:
        key = (h.get("talk_id"), int(h.get("chunk_index", 0) or 0))
        if key in seen:
            continue
        seen.add(key)

        label = _label_from_row(h)
        idx   = int(h.get("chunk_index", 0) or 0)
        url   = (h.get("url") or "").strip()

        line = f"— {label} · chunk {idx}"
        if url:
            line += f" · {url}"
        lines.append(line)

        if len(lines) >= max_sources:
            break

    return "\n".join(lines)

# -------- main composer --------

def answer_from_chunks(
    query: str,
    hits: List[Dict],
    *,
    max_sentences: int = 5,
    max_snippets: Optional[int] = None,
) -> str:
    """
    Ultra-simple extractive composer:
      - picks up to N strongest chunks (N = max_snippets or max_sentences)
      - returns a concise synthesis with an appended Sources block
      - uses human-readable citation labels
    NOTE: Accepts both `max_sentences` and `max_snippets` for backward compatibility.
    """
    if not hits:
        return "I don’t have sufficient context to answer. Try adding a date, venue, or specific term."

    n = max_snippets or max_sentences  # prefer explicit max_snippets if provided

    # Take top N chunks as supporting snippets
    top = hits[: max(1, n)]
    snippets: List[str] = []
    for h in top:
        txt = _trim(h.get("text"), limit=500)
        snippets.append(f"{txt} {_inline_cite(h)}")

    synthesis = "Based on the archived talks, here are the most relevant passages:"
    body = " ".join(snippets)

    # Sources block
    sources_block = format_sources(hits)

    return f"{synthesis} {body}\n\nSources:\n{sources_block}"