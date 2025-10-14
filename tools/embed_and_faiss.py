#!/usr/bin/env python3
"""
tools/embed_and_faiss.py

Reads JSONL chunks → computes embeddings → writes Parquet + FAISS (cosine).
Also emits a small QC report with counts, dims, and SHA-256 checksums.

Usage:
  export OPENAI_API_KEY="sk-..."
  pip install "openai==1.*" faiss-cpu pandas pyarrow numpy tqdm
  python tools/embed_and_faiss.py \
    --chunks build/chunks/bache-talks.chunks.jsonl \
    --parquet vectors/bache-talks.embeddings.parquet \
    --faiss vectors/bache-talks.index.faiss \
    --report reports/embedding_qc.json \
    --model text-embedding-3-large
"""

import argparse
import json
import os
import time
import hashlib
from pathlib import Path
from typing import List, Dict

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import faiss
from tqdm import tqdm

from openai import OpenAI
from openai.types import Embedding

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

def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def load_jsonl(path: Path) -> List[Dict]:
    rows = []
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
                # OpenAI v1 returns .data sorted like the input order
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
# Writers
# ----------------------------

def write_parquet(rows: List[Dict], embeddings: np.ndarray, out_path: Path) -> None:
    """
    Attach embeddings to rows and write a Parquet file with a list<float> column.
    Preserves ordering of rows to align with FAISS index.
    """
    ensure_parent(out_path)

    # Minimal column selection to keep Parquet compact yet useful
    # (You can add/remove fields as needed.)
    keep_cols = [
        "chunk_id", "talk_id", "archival_title", "published",
        "channel", "source_type", "transcript",
        "chunk_index", "char_len", "token_est", "hash", "text"
    ]
    # Ensure columns exist (missing -> None)
    norm_rows = []
    for r in rows:
        nr = {k: r.get(k) for k in keep_cols}
        norm_rows.append(nr)

    df = pd.DataFrame(norm_rows)
    df["embedding"] = embeddings.tolist()

    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, out_path)

def build_faiss_cosine(embeddings: np.ndarray, out_path: Path) -> None:
    """
    Build cosine-similarity FAISS index using inner product on normalized vectors.
    """
    ensure_parent(out_path)
    vecs = normalize_for_cosine(embeddings.astype("float32"))
    d = vecs.shape[1]
    index = faiss.IndexFlatIP(d)
    index.add(vecs)
    faiss.write_index(index, str(out_path))

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
    args = ap.parse_args()

    chunks_path = Path(args.chunks)
    parquet_path = Path(args.parquet)
    faiss_path = Path(args.faiss)
    report_path = Path(args.report)

    if not chunks_path.exists():
        raise SystemExit(f"Chunks JSONL not found: {chunks_path}")

    rows = load_jsonl(chunks_path)
    if not rows:
        raise SystemExit(f"No rows found in {chunks_path}")

    # Keep deterministic order based on file order; validate minimal fields
    for i, r in enumerate(rows):
        if "text" not in r or "chunk_id" not in r:
            raise SystemExit(f"Row {i} missing required fields (needs 'text' and 'chunk_id').")

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

    # Parquet
    write_parquet(rows, embeddings, parquet_path)

    # FAISS (cosine)
    build_faiss_cosine(embeddings, faiss_path)

    # QC report
    ensure_parent(report_path)
    qc = {
        "chunks_input": str(chunks_path),
        "chunks_input_sha256": sha256_file(chunks_path),
        "rows": len(rows),
        "embedding_dim": int(embeddings.shape[1]),
        "parquet_path": str(parquet_path),
        "parquet_sha256": sha256_file(parquet_path),
        "faiss_path": str(faiss_path),
        "faiss_sha256": sha256_file(faiss_path),
        "model": args.model,
        "batch_size": args.batch,
        "env": {
            "python_version": os.sys.version.split()[0],
            "faiss_cpu": getattr(faiss, "__version__", "unknown"),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "pyarrow": pa.__version__,
        },
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(qc, f, ensure_ascii=False, indent=2)

    print(f"Wrote Parquet → {parquet_path}")
    print(f"Wrote FAISS   → {faiss_path}")
    print(f"Vectors: {embeddings.shape[0]} x {embeddings.shape[1]}")
    print(f"QC report → {report_path}")

if __name__ == "__main__":
    main()
