#!/usr/bin/env python3
from typing import List, Dict

def _cite(row: Dict) -> str:
    # chunk number is 1-based in your JSON
    title = row.get("archival_title", "").strip()
    date  = row.get("published", "").strip()
    idx   = row.get("chunk_index", 0)
    return f"[({date}, {title}, chunk {idx})]"

def answer_from_chunks(query: str, hits: List[Dict], max_sentences: int = 6) -> str:
    """
    Ultra-simple extractive composer:
      - picks 2–3 strongest chunks
      - returns a concise synthesis + inline citations
    """
    if not hits:
        return "I don’t have sufficient context to answer. Try adding a date, venue, or specific term."

    # Take top 2–3 chunks
    top = hits[:3]
    snippets = []
    for h in top:
        txt = (h["text"].strip().replace("\n", " "))
        # keep each snippet reasonably short
        if len(txt) > 500: 
            txt = txt[:500].rsplit(" ", 1)[0] + "…"
        snippets.append(f"{txt} { _cite(h) }")

    # Compose: one or two sentences of synthesis + snippets
    synthesis = "Based on the archived talks, here are the most relevant passages:"
    body = " ".join(snippets)
    return f"{synthesis} {body}"
