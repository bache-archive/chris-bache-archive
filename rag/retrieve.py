#!/usr/bin/env python3
"""
rag/retrieve.py

Retriever that queries a FAISS cosine index and returns rows from the Parquet
metadata table. Supports human-readable citations that were embedded by
tools/embed_and_faiss.py (columns: citation, date, venue, url, transcript_path).

Requirements:
  pip install "openai==1.*" faiss-cpu numpy pandas pyarrow python-dotenv
  export OPENAI_API_KEY="sk-..."
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

import faiss
import numpy as np
import pyarrow.parquet as pq
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def _l2_normalize(mat: np.ndarray) -> np.ndarray:
    """Row-wise L2 normalize (with 0-safe guard)."""
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


class Retriever:
    """
    Parameters
    ----------
    parquet_path : str
        Path to the Parquet file written by tools/embed_and_faiss.py
        (must include 'id', 'embedding', 'text', and citation columns).
    faiss_path : str
        Path to the FAISS index (IndexIDMap2 over IndexFlatIP is recommended).
    model : str
        OpenAI embedding model for query embeddings.
    per_talk_cap : int
        Max number of hits per talk (diversity cap).
    top_k_default : int
        Default number of results returned if k not provided to .search().
    """

    def __init__(
        self,
        parquet_path: str = "vectors/bache-talks.embeddings.parquet",
        faiss_path: str = "vectors/bache-talks.index.faiss",
        model: str = "text-embedding-3-large",
        per_talk_cap: int = 2,
        top_k_default: int = 8,
    ):
        self.model = model
        self.per_talk_cap = per_talk_cap
        self.top_k_default = top_k_default

        # Load Parquet → pandas
        table = pq.read_table(parquet_path)
        df = table.to_pandas()

        # Basic checks
        if "embedding" not in df.columns:
            raise RuntimeError("Parquet is missing 'embedding' column.")
        if "id" not in df.columns:
            # For backward compatibility: synthesize ids as row index
            df["id"] = np.arange(len(df), dtype=np.int64)

        # Keep two views: by original order (iloc) and by id (for IDMap).
        self.df = df.reset_index(drop=True)
        self.df_by_id = self.df.set_index("id", drop=False)

        # Load FAISS index
        self.index = faiss.read_index(faiss_path)

        # OpenAI client
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set.")
        self.client = OpenAI(api_key=api_key)

    # ---------- Query embedding ----------

    def _embed_query(self, query: str) -> np.ndarray:
        """Return a 1×D L2-normalized vector for cosine/IP search (NumPy 2.x safe)."""
        resp = self.client.embeddings.create(model=self.model, input=[query])
        arr = np.asarray(resp.data[0].embedding, dtype=np.float32)  # allow copy if needed
        vec = arr.reshape(1, -1)
        # L2 normalize
        norms = np.linalg.norm(vec, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vec / norms

    # ---------- Row resolution helpers ----------

    def _row_from_faiss_id(self, fid: int) -> pd.Series:
        """
        Resolve a FAISS label to a row:
          - If the FAISS index was built with IndexIDMap2 and labels == df['id'],
            we look up by id.
          - Otherwise, we fall back to positional iloc.
        """
        # Fast path: try id lookup
        try:
            return self.df_by_id.loc[int(fid)]
        except Exception:
            # Fallback: interpret fid as positional index
            return self.df.iloc[int(fid)]

    def _format_row(self, row: pd.Series, score: float) -> Dict[str, Any]:
        """Return a clean dict with both core and human-readable fields."""
        return {
            # Core retrieval info
            "id": int(row.get("id")),
            "_score": float(score),
            "text": row.get("text"),
            "talk_id": row.get("talk_id"),
            "archival_title": row.get("archival_title"),
            "chunk_index": row.get("chunk_index"),
            "published": row.get("published"),
            "channel": row.get("channel"),
            "source_type": row.get("source_type"),
            # Human-readable citation metadata (added in the new pipeline)
            "citation": row.get("citation"),
            "date": row.get("date"),
            "venue": row.get("venue"),
            "url": row.get("url"),
            "transcript_path": row.get("transcript_path"),
        }

    # ---------- Public search ----------

    def search(
        self,
        query: str,
        k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        oversample_factor: int = 8,
    ) -> List[Dict[str, Any]]:
        """
        Execute a semantic search.

        Parameters
        ----------
        query : str
            Natural-language query.
        k : int, optional
            Number of results to return (default: self.top_k_default).
        filters : dict, optional
            Simple AND filter on exact-match keys (e.g., {"talk_id": "..."})
        oversample_factor : int
            Multiple of k to fetch from FAISS before capping per talk.

        Returns
        -------
        List[dict]
            Each dict contains 'text', 'citation', 'url', etc.
        """
        k = k or self.top_k_default
        qv = self._embed_query(query)

        # Oversample to allow per-talk capping without losing total k
        nprobe = max(k * oversample_factor, k)
        scores, ids = self.index.search(qv, nprobe)
        ids_list = ids[0].tolist()
        scores_list = scores[0].tolist()

        out: List[Dict[str, Any]] = []
        per_talk: Dict[Any, int] = {}

        for fid, sc in zip(ids_list, scores_list):
            if fid < 0:
                continue

            row = self._row_from_faiss_id(int(fid))

            # Optional AND-filters (exact match)
            if filters:
                ok = True
                for fk, fv in filters.items():
                    if str(row.get(fk)) != str(fv):
                        ok = False
                        break
                if not ok:
                    continue

            talk_key = row.get("talk_id")
            if talk_key is not None:
                cnt = per_talk.get(talk_key, 0)
                if cnt >= self.per_talk_cap:
                    continue
                per_talk[talk_key] = cnt + 1

            out.append(self._format_row(row, sc))
            if len(out) >= k:
                break

        return out


# ---------- Convenience for quick manual tests ----------
if __name__ == "__main__":
    r = Retriever()
    hits = r.search("What does Bache mean by Diamond Luminosity?", k=5)
    for h in hits:
        # Example: — Bache · 2025-05-18 · New Thinking Allowed · Diamond Luminosity (live stream)
        src = h.get("citation") or h.get("transcript_path")
        print(f"— {src} · chunk {h.get('chunk_index')} · score {h['_score']:.4f}")
        if h.get("url"):
            print(f"   {h['url']}")