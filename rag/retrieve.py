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
from typing import Any, Dict, List, Optional

import faiss
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "vectors/bache-talks.index.faiss")
METADATA_PATH = os.getenv("METADATA_PATH", "vectors/bache-talks.embeddings.parquet")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-large")
PER_TALK_CAP = int(os.getenv("MAX_PER_TALK", "3"))
TOP_K_DEFAULT = int(os.getenv("TOP_K_DEFAULT", "8"))


def _l2_normalize_rows(mat: np.ndarray) -> np.ndarray:
    """Row-wise L2 normalize (with 0-safe guard)."""
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return mat / norms


class Retriever:
    """
    Parameters
    ----------
    parquet_path : str
        Parquet produced by tools/embed_and_faiss.py (must include 'id', 'embedding', 'text', etc.)
    faiss_path : str
        FAISS index path (IndexIDMap2 over IndexFlatIP recommended; positional fallback supported)
    model : str
        OpenAI embedding model for query vectors.
    per_talk_cap : int
        Max number of hits per talk.
    top_k_default : int
        Default K when not specified in .search()
    """

    def __init__(
        self,
        parquet_path: str = METADATA_PATH,
        faiss_path: str = FAISS_INDEX_PATH,
        model: str = EMBED_MODEL,
        per_talk_cap: int = PER_TALK_CAP,
        top_k_default: int = TOP_K_DEFAULT,
    ):
        self.parquet_path = parquet_path
        self.faiss_path = faiss_path
        self.model = model
        self.per_talk_cap = per_talk_cap
        self.top_k_default = top_k_default

        # Load Parquet → pandas
        table = pq.read_table(parquet_path)
        df = table.to_pandas()

        if "embedding" not in df.columns:
            raise RuntimeError("Parquet is missing 'embedding' column.")
        if "id" not in df.columns:
            # Back-compat: synthesize ids as row index
            df["id"] = np.arange(len(df), dtype=np.int64)

        self.df = df.reset_index(drop=True)
        self.df_by_id = self.df.set_index("id", drop=False)

        # Load FAISS index
        self.index = faiss.read_index(faiss_path)

        # OpenAI client
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set.")
        self.client = OpenAI(api_key=api_key)

        # Infer embedding dim from first row
        try:
            first = self.df.iloc[0]["embedding"]
            self.embed_dim = int(len(first))
        except Exception:
            self.embed_dim = None

    # ---------- Query embedding ----------

    def _embed_query(self, query: str) -> np.ndarray:
        """Return a 1×D L2-normalized vector for cosine/IP search (NumPy 2.x safe)."""
        resp = self.client.embeddings.create(model=self.model, input=[query])
        arr = np.asarray(resp.data[0].embedding, dtype=np.float32)  # allow copy if needed
        vec = arr.reshape(1, -1)
        return _l2_normalize_rows(vec)

    # ---------- Row helpers ----------

    def _row_from_faiss_id(self, fid: int) -> pd.Series:
        """
        If index uses IDMap labels that match df['id'], resolve by id.
        Fallback: treat label as positional index.
        """
        try:
            return self.df_by_id.loc[int(fid)]
        except Exception:
            return self.df.iloc[int(fid)]

    def _format_row(self, row: pd.Series, score: float) -> Dict[str, Any]:
        """Return a clean dict with core + human-readable fields."""
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

    # ---------- Public API ----------

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
        k : int, optional
        filters : dict, optional (exact-match AND, e.g., {"talk_id": "..."})
        oversample_factor : int

        Returns
        -------
        List[dict] with text, citation, url, etc.
        """
        k = k or self.top_k_default
        qv = self._embed_query(query)

        # Oversample to keep diversity cap without losing total k
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
                if not all(str(row.get(fk)) == str(fv) for fk, fv in filters.items()):
                    continue

            tkey = row.get("talk_id")
            if tkey is not None:
                cnt = per_talk.get(tkey, 0)
                if cnt >= self.per_talk_cap:
                    continue
                per_talk[tkey] = cnt + 1

            out.append(self._format_row(row, sc))
            if len(out) >= k:
                break

        return out

    def status(self) -> Dict[str, Any]:
        """
        Lightweight runtime status for /_rag_status:
        - parquet rows, faiss ntotal
        - embed model & dim
        - caps & paths
        """
        try:
            faiss_ntotal = int(self.index.ntotal)
        except Exception:
            faiss_ntotal = None
        return {
            "parquet_rows": int(len(self.df)),
            "faiss_ntotal": faiss_ntotal,
            "embed_model": self.model,
            "embed_dim": self.embed_dim,
            "per_talk_cap": int(self.per_talk_cap),
            "faiss_index_path": self.faiss_path,
            "metadata_path": self.parquet_path,
        }


# --------- Module-level helpers used by app.py ---------

_RETRIEVER: Optional[Retriever] = None


def _get_retriever() -> Retriever:
    global _RETRIEVER
    if _RETRIEVER is None:
        _RETRIEVER = Retriever(
            parquet_path=METADATA_PATH,
            faiss_path=FAISS_INDEX_PATH,
            model=EMBED_MODEL,
            per_talk_cap=PER_TALK_CAP,
            top_k_default=TOP_K_DEFAULT,
        )
    return _RETRIEVER


def search_chunks(query: str, top_k: int = TOP_K_DEFAULT, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Convenience wrapper for the API layer."""
    return _get_retriever().search(query=query, k=top_k, filters=filters)


def rag_status() -> Dict[str, Any]:
    """
    Return a dict suitable for the /_rag_status endpoint without performing any embeddings.
    """
    # Avoid throwing if OPENAI_API_KEY is missing; still report useful info
    try:
        r = _get_retriever()
        status = r.status()
    except Exception as e:
        # best-effort path existence reporting
        status = {
            "error": f"{type(e).__name__}: {e}",
            "faiss_index_path": FAISS_INDEX_PATH,
            "metadata_path": METADATA_PATH,
            "embed_model": EMBED_MODEL,
            "per_talk_cap": PER_TALK_CAP,
        }
    return status


# ---------- Manual smoke test ----------
if __name__ == "__main__":
    r = _get_retriever()
    print("STATUS:", r.status())
    hits = r.search("What does Bache mean by Diamond Luminosity?", k=5)
    for h in hits:
        src = h.get("citation") or h.get("transcript_path")
        print(f"— {src} · chunk {h.get('chunk_index')} · score {h['_score']:.4f}")
        if h.get("url"):
            print(f"   {h['url']}")