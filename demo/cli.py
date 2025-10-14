#!/usr/bin/env python3
import argparse
from rag.retrieve import Retriever
from rag.answer import answer_from_chunks

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--q", required=True, help="Your query")
    ap.add_argument("--k", type=int, default=6)
    args = ap.parse_args()

    r = Retriever()
    hits = r.search(args.q, k=args.k)
    print(answer_from_chunks(args.q, hits))
    print("\n--- Top hits ---")
    for h in hits:
        print(f"{h['talk_id']}  score={h['_score']:.4f}  chunk={h['chunk_index']}")
        print(h["text"][:240].replace("\n"," ") + ("…" if len(h["text"])>240 else ""))
        print()

if __name__ == "__main__":
    main()
