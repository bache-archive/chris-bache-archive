#!/usr/bin/env python3
import os, numpy as np, pyarrow.parquet as pq, faiss
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class Retriever:
    def __init__(self,
                 parquet_path="vectors/bache-talks.embeddings.parquet",
                 faiss_path="vectors/bache-talks.index.faiss",
                 model="text-embedding-3-large",
                 per_talk_cap=3):
        self.model = model
        self.per_talk_cap = per_talk_cap
        self.table = pq.read_table(parquet_path)
        self.df = self.table.to_pandas()
        # Pre-normalize embeddings for cosine
        self.emb = np.stack(self.df["embedding"].to_list()).astype("float32")
        n = np.linalg.norm(self.emb, axis=1, keepdims=True); n[n==0]=1
        self.emb = self.emb / n
        self.index = faiss.read_index(faiss_path)
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    def _embed_query(self, q: str) -> np.ndarray:
        v = self.client.embeddings.create(model=self.model, input=[q]).data[0].embedding
        v = np.array(v, dtype="float32")[None, :]
        n = np.linalg.norm(v, axis=1, keepdims=True); n[n==0]=1
        return v / n

    def search(self, query: str, k: int = 8, filters=None):
        """filters: dict like {"talk_id": "...", "channel": "..."} (optional)"""
        qv = self._embed_query(query)
        # Oversample to allow per-talk capping
        scores, idxs = self.index.search(qv, k * 8)
        idxs, scores = idxs[0].tolist(), scores[0].tolist()

        rows, per_talk = [], {}
        for i, s in zip(idxs, scores):
            if i < 0:
                continue
            row = self.df.iloc[i].to_dict()
            if filters:
                # simple AND filter on exact match keys
                ok = all(str(row.get(fk)) == str(fv) for fk, fv in filters.items())
                if not ok: 
                    continue
            tid = row["talk_id"]
            per_talk[tid] = per_talk.get(tid, 0) + 1
            if per_talk[tid] <= self.per_talk_cap:
                row["_score"] = float(s)
                rows.append(row)
            if len(rows) >= k:
                break
        return rows
