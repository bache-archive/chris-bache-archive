# CONFIG (RAG v1)
EMBED_MODEL: text-embedding-3-large
CHUNK_TARGET: 1200
CHUNK_OVERLAP: 100
FILES:
  chunks_jsonl: build/chunks/bache-talks.chunks.jsonl
  parquet_out:  vectors/bache-talks.embeddings.parquet
  faiss_out:    vectors/bache-talks.index.faiss
