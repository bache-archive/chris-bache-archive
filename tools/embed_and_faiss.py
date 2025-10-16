#!/usr/bin/env python3
"""
tools/embed_and_faiss.py

Reads JSONL chunks → computes embeddings → writes Parquet + FAISS (cosine).
Also emits a small QC report with counts, dims, and SHA-256 checksums.
NOW: attaches human-readable citation metadata from rag/citation_labels.json
and backfills canonical URLs from index.json.

Usage:
  export OPENAI_API_KEY="sk-..."
  pip install "openai==1.*" faiss-cpu pandas pyarrow numpy tqdm python-dotenv

  python tools/embed_and_faiss.py \
    --chunks vectors/chunks.jsonl \
    --parquet vectors/bache-talks.embeddings.parquet \
    --faiss vectors/bache-talks.index.faiss \
    --report reports/embedding_qc.json \
    --model text-embedding-3-large \
    --citation_labels rag/citation_labels.json \
    --index index.json
"""

import argparse
import json
import os
import time
import hashlib
from pathlib import Path
from typing import List, Dict, Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import faiss
from tqdm import tqdm

from openai import OpenAI
from openai.types import Embedding  # noqa: F401

from dotenv import load_dotenv
load_dotenv()


# ----------------------------
# Utilities
# ----------------------------

def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows

def normalize_for_cosine(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms

def load_citation_labels(path: Path) -> Dict[str, str]:
    """
    Load mapping from FULL transcript path → human-readable label.
    Example key: 'sources/transcripts/2019-11-13-...md'
    """
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def normalize_repo_path(p: str) -> str:
    """
    Normalize to repo-style forward slashes and strip leading './'.
    """
    if not p:
        return ""
    posix = Path(p).as_posix()
    if posix.startswith("./"):
        posix = posix[2:]
    return posix

def transcript_stem(transcript_path: str) -> str:
    """
    sources/transcripts/2019-11-13-foo-bar.md → 2019-11-13-foo-bar
    (used only as a last-resort fallback key)
    """
    base = os.path.basename(transcript_path) if transcript_path else ""
    stem, _ = os.path.splitext(base)
    return stem

def load_index_url_map(index_path: Path) -> Dict[str, str]:
    """
    Build transcript_path → canonical URL map from index.json.
    Tries several common fields: web_url, youtube_url, media.youtube, media.url.
    """
    if not index_path.exists():
        return {}
    with open(index_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # index.json appears to be an array of items, not {"talks":[...]}
    items = data if isinstance(data, list) else data.get("talks", [])
    url_map: Dict[str, str] = {}

    for it in items:
        tpath = it.get("transcript") or it.get("transcript_path")
        if not tpath:
            continue
        tpath_norm = normalize_repo_path(str(tpath))
        media = it.get("media") or {}
        url = (
            it.get("web_url")
            or it.get("youtube_url")
            or media.get("youtube")
            or media.get("url")
        )
        if url:
            url_map[tpath_norm] = url
    return url_map


# ----------------------------
# Embedding
# ----------------------------

def embed_texts(
    client: OpenAI,
    model: str,
    texts: List[str],
    batch_size: int = 256,
    max_retries: int = 6,
    initial_backoff_s: float = 2.0,
) -> np.ndarray:
    """
    Batches requests to the embeddings API with simple exponential backoff.
    Returns float32 numpy array [N, D] in the same order as `texts`.
    """
    all_vecs: List[List[float]] = []
    for start in tqdm(range(0, len(texts), batch_size), desc="Embedding"):
        batch = texts[start:start + batch_size]
        # Retry loop
        tries, backoff = 0, initial_backoff_s
        while True:
            try:
                resp = client.embeddings.create(model=model, input=batch)
                vecs = [d.embedding for d in resp.data]  # type: ignore[attr-defined]
                all_vecs.extend(vecs)
                break
            except Exception as e:
                tries += 1
                if tries > max_retries:
                    raise RuntimeError(f"Embedding failed after {max_retries} retries at batch {start}: {e}") from e
                time.sleep(backoff)
                backoff *= 2.0
    arr = np.array(all_vecs, dtype="float32")
    return arr


# ----------------------------
# Enrichment & Writers
# ----------------------------

KEEP_COLS = [
    # existing core fields (as in your previous script)
    "chunk_id", "talk_id", "archival_title", "published",
    "channel", "source_type", "transcript",
    "chunk_index", "char_len", "token_est", "hash", "text",
    # new human-readable citation fields
    "id", "citation", "date", "venue", "url", "transcript_path",
]

def enrich_rows_with_citation(
    rows: List[Dict[str, Any]],
    citation_map: Dict[str, str],
    url_map: Dict[str, str],
) -> List[Dict[str, Any]]:
    """
    Attach 'id', 'citation', 'date', 'venue', 'url', 'transcript_path' to each row.
    We DO NOT rename any files; we look up using full transcript path keys
    (as provided in rag/citation_labels.json) and backfill URL from index.json.
    """
    enriched: List[Dict[str, Any]] = []
    for ridx, r in enumerate(rows):
        # Resolve transcript path and normalize to repo style
        tpath_raw = r.get("transcript") or r.get("transcript_path") or r.get("source_file") or ""
        tpath_norm = normalize_repo_path(str(tpath_raw))
        stem = transcript_stem(tpath_norm)

        # Human-readable label lookup (full path first)
        citation = (
            citation_map.get(tpath_norm) or
            citation_map.get(tpath_raw) or
            citation_map.get("./" + tpath_norm) or
            citation_map.get("sources/transcripts/" + os.path.basename(tpath_norm)) or
            citation_map.get(stem)  # last resort if a stem-only key exists
        )

        # Additional metadata (be generous with field names)
        date  = r.get("published") or r.get("recorded_date") or r.get("date")
        venue = r.get("channel")   or r.get("venue")

        # URL: prefer per-row if present; otherwise backfill from index.json map
        url   = (
            r.get("web_url")
            or r.get("youtube_url")
            or r.get("url")
            or url_map.get(tpath_norm)
            or url_map.get(tpath_raw)
        )

        # Stable numeric id (row index). Used as FAISS external label.
        r["id"] = int(ridx)
        r["citation"] = citation or tpath_norm or tpath_raw  # readable fallback chain
        r["date"] = date
        r["venue"] = venue
        r["url"] = url
        r["transcript_path"] = tpath_norm or tpath_raw

        enriched.append(r)
    return enriched

def write_parquet(rows: List[Dict[str, Any]], embeddings: np.ndarray, out_path: Path) -> None:
    """
    Attach embeddings to rows and write a Parquet file with a list<float> column.
    Preserves ordering of rows to align with FAISS index (also stores 'id').
    """
    ensure_parent(out_path)
    norm_rows: List[Dict[str, Any]] = [{k: r.get(k) for k in KEEP_COLS} for r in rows]
    df = pd.DataFrame(norm_rows)
    df["embedding"] = embeddings.tolist()
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, out_path)

def build_faiss_cosine_with_ids(embeddings: np.ndarray, ids: np.ndarray, out_path: Path) -> None:
    """
    Build cosine-similarity FAISS index using inner product on normalized vectors,
    wrapping with IndexIDMap2 so labels == our stable 'id' column.
    """
    ensure_parent(out_path)
    vecs = normalize_for_cosine(embeddings.astype("float32"))
    d = vecs.shape[1]
    base = faiss.IndexFlatIP(d)
    idmap = faiss.IndexIDMap2(base)
    idmap.add_with_ids(vecs, ids.astype("int64"))
    faiss.write_index(idmap, str(out_path))


# ----------------------------
# Main
# ----------------------------

def main():
    ap = argparse.ArgumentParser(description="Embed chunks and build Parquet + FAISS.")
    ap.add_argument("--chunks", default="build/chunks/bache-talks.chunks.jsonl", help="Input JSONL of chunks")
    ap.add_argument("--parquet", default="vectors/bache-talks.embeddings.parquet", help="Output Parquet path")
    ap.add_argument("--faiss", default="vectors/bache-talks.index.faiss", help="Output FAISS index path")
    ap.add_argument("--report", default="reports/embedding_qc.json", help="Output QC report JSON")
    ap.add_argument("--model", default="text-embedding-3-large", help="Embedding model")
    ap.add_argument("--batch", type=int, default=256, help="Embedding batch size")
    ap.add_argument("--citation_labels", default="rag/citation_labels.json", help="Path to citation_labels.json")
    ap.add_argument("--index", default="index.json", help="Path to index.json (for URL backfill)")
    args = ap.parse_args()

    chunks_path = Path(args.chunks)
    parquet_path = Path(args.parquet)
    faiss_path = Path(args.faiss)
    report_path = Path(args.report)
    citation_path = Path(args.citation_labels)
    index_path = Path(args.index)

    if not chunks_path.exists():
        raise SystemExit(f"Chunks JSONL not found: {chunks_path}")

    rows = load_jsonl(chunks_path)
    if not rows:
        raise SystemExit(f"No rows found in {chunks_path}")

    # Validate minimal fields
    for i, r in enumerate(rows):
        if "text" not in r or "chunk_id" not in r:
            raise SystemExit(f"Row {i} missing required fields (needs 'text' and 'chunk_id').")

    # Human-readable labels + URL backfill map
    citation_labels = load_citation_labels(citation_path)
    index_url_map = load_index_url_map(index_path)

    # Enrich rows (NO filename changes)
    rows = enrich_rows_with_citation(rows, citation_labels, index_url_map)

    texts = [r["text"] for r in rows]

    # OpenAI client (API key via env)
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY not set in environment.")
    client = OpenAI(api_key=api_key)

    # Embed
    embeddings = embed_texts(
        client=client,
        model=args.model,
        texts=texts,
        batch_size=args.batch,
    )

    # Parquet (with enriched metadata + embeddings)
    write_parquet(rows, embeddings, parquet_path)

    # FAISS (cosine) with external ids == row index
    ids = np.arange(len(rows), dtype="int64")
    build_faiss_cosine_with_ids(embeddings, ids, faiss_path)

    # QC report
    ensure_parent(report_path)
    sample_block = []
    for r in rows[:3]:
        sample_block.append({
            "id": r.get("id"),
            "citation": r.get("citation"),
            "date": r.get("date"),
            "venue": r.get("venue"),
            "url": r.get("url"),
            "transcript_path": r.get("transcript_path"),
            "chunk_index": r.get("chunk_index"),
        })

    qc = {
        "chunks_input": str(chunks_path),
        "chunks_input_sha256": sha256_file(chunks_path),
        "rows": len(rows),
        "embedding_dim": int(embeddings.shape[1]) if embeddings.ndim == 2 else None,
        "parquet_path": str(parquet_path),
        "parquet_sha256": sha256_file(parquet_path),
        "faiss_path": str(faiss_path),
        "faiss_sha256": sha256_file(faiss_path),
        "model": args.model,
        "batch_size": args.batch,
        "citation_labels_path": str(citation_path),
        "citation_labels_count": len(citation_labels),
        "index_path": str(index_path),
        "index_url_entries": len(index_url_map),
        "env": {
            "python_version": os.sys.version.split()[0],
            "faiss_cpu": getattr(faiss, "__version__", "unknown"),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "pyarrow": pa.__version__,
        },
        "sample_enriched_rows": sample_block,
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(qc, f, ensure_ascii=False, indent=2)

    print(f"Wrote Parquet → {parquet_path}")
    print(f"Wrote FAISS   → {faiss_path}")
    print(f"Vectors: {embeddings.shape[0]} x {embeddings.shape[1]}")
    print(f"Citation labels: {citation_path} (found {len(citation_labels)} entries)")
    print(f"Index URL entries: {len(index_url_map)} from {index_path}")
    print(f"QC report → {report_path}")
    print("[OK] Embeddings + FAISS built with human-readable citations and URL backfill.")

if __name__ == "__main__":
    main()