#!/usr/bin/env python3
import os, json, datetime, pathlib, requests, yaml
from dotenv import load_dotenv

# load ../tools/.env if present
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

DATE = datetime.date.today().isoformat()

HOST_TALKS = os.environ.get("HOST_TALKS", "http://127.0.0.1:8000")   # bache-rag-api
HOST_BOOK  = os.environ.get("HOST_BOOK",  "http://127.0.0.1:9000")   # lsdmu-rag-api
KEY_TALKS  = os.environ.get("API_KEY_TALKS", "dev")
KEY_BOOK   = os.environ.get("API_KEY_BOOK",  "dev")

TOP_K = int(os.environ.get("TOP_K", "20"))
QUESTIONS_PATH = os.environ.get("QUESTIONS_PATH", "questions/questions.yaml")

BACHE_RAG_REPO  = os.environ.get("BACHE_RAG_REPO",  "../bache-rag-api")
LSDMU_RAG_REPO  = os.environ.get("LSDMU_RAG_REPO",  "../lsdmu-rag-api")
ARCHIVE_REPO    = os.environ.get("ARCHIVE_REPO",    ".")

def ensure_dir(p): pathlib.Path(p).mkdir(parents=True, exist_ok=True)

def write_text(path, text):
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

def write_json(path, obj):
    write_text(path, json.dumps(obj, ensure_ascii=False, indent=2))

def post_json(host, path, key, payload):
    r = requests.post(f"{host}{path}",
                      headers={"Authorization": f"Bearer {key}",
                               "Content-Type": "application/json"},
                      json=payload, timeout=60)
    r.raise_for_status()
    return r.json()

def md_quote_pack(chunks):
    # Group by title; list “[hh:mm:ss](ts_url) — “text””
    by_title = {}
    for c in chunks:
        title = c.get("archival_title") or c.get("title") or "Untitled"
        by_title.setdefault(title, []).append(c)
    lines = []
    for title in sorted(by_title.keys()):
        lines.append(f"# {title}")
        for c in sorted(by_title[title], key=lambda x: (x.get("start_hhmmss") or "99:99:99")):
            start = c.get("start_hhmmss") or "—:—:—"
            ts = c.get("ts_url") or c.get("url") or ""
            text = (c.get("text") or "").replace("\n"," ").strip()
            lines.append(f'* [{start}]({ts}) — “{text}”')
        lines.append("")
    return "\n".join(lines).strip() + "\n"

def seed_index_if_missing(folder, qid):
    idx = os.path.join(folder, "index.md")
    if not os.path.exists(idx):
        write_text(idx, f"# {qid}\n\n_(Draft seeded; run editorial pass to finalize.)_\n")

def main():
    with open(QUESTIONS_PATH, "r", encoding="utf-8") as f:
        questions = yaml.safe_load(f)

    for q in questions:
        qid = q["id"]
        q_search = q["query_search"]
        q_answer = q["query_answer"]

        # --- TALKS (bache-rag-api)
        talks_dir = f"{BACHE_RAG_REPO}/reports/quote_packs/{DATE}/{qid}"
        talks_search = post_json(HOST_TALKS, "/search", KEY_TALKS, {"query": q_search, "top_k": TOP_K})
        write_json(f"{talks_dir}/talks.search.json", talks_search)
        try:
            talks_answer = post_json(HOST_TALKS, "/answer", KEY_TALKS, {"query": q_answer})
            write_text(f"{talks_dir}/talks.preface.txt", talks_answer.get("answer","").strip()+"\n")
        except Exception as e:
            write_text(f"{talks_dir}/talks.preface.txt", f"(no preface; {e})\n")
        write_text(f"{talks_dir}/talks.quote_pack.md", md_quote_pack(talks_search.get("chunks", [])))

        # --- BOOK (lsdmu-rag-api)
        book_dir = f"{LSDMU_RAG_REPO}/reports/quote_packs/{DATE}/{qid}"
        book_search = post_json(HOST_BOOK, "/search", KEY_BOOK, {"query": q_search, "top_k": TOP_K})
        write_json(f"{book_dir}/book.search.json", book_search)
        try:
            book_answer = post_json(HOST_BOOK, "/answer", KEY_BOOK, {"query": q_answer})
            write_text(f"{book_dir}/book.preface.txt", book_answer.get("answer","").strip()+"\n")
        except Exception as e:
            write_text(f"{book_dir}/book.preface.txt", f"(no preface; {e})\n")

        # --- ARCHIVE (final editorial bundle)
        out_dir = f"{ARCHIVE_REPO}/docs/educational/{qid}"
        ensure_dir(out_dir)
        bundle = {
            "talks": talks_search,
            "book":  book_search,
            "meta": {
                "date": DATE,
                "top_k": TOP_K,
                "qid": qid,
                "queries": {"search": q_search, "answer": q_answer}
            }
        }
        write_json(f"{out_dir}/sources.json", bundle)
        seed_index_if_missing(out_dir, qid)

    print("OK: harvested all questions.")

if __name__ == "__main__":
    main()
