#!/usr/bin/env python3
# tools/scaffold_curriculum.py
from __future__ import annotations
from pathlib import Path
import json, datetime

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "educational"

# qid | title | seed queries (guide harvesters)
MODULES = [
    ("journey-structure", "The Journey Structure (Sessions 1–73)", [
        "journey structure", "sessions 1-73", "protocol", "dosage", "method", "map",
        "LSD sessions structure", "overview of LSDMU journey"
    ]),
    ("nature-of-consciousness", "The Nature of Consciousness", [
        "nature of consciousness", "mind of the universe", "cosmic consciousness",
        "nondual awareness", "vast mind", "collective mind"
    ]),
    ("psychedelics-and-spiritual-evolution", "The Role of Psychedelics in Spiritual Evolution (context)", [
        "psychedelics and spiritual evolution", "evolution of consciousness psychedelics",
        "sacred medicine practice", "entheogens as practice"
    ]),
    ("ocean-of-suffering", "The Ocean of Suffering", [
        "ocean of suffering", "collective suffering", "purification pain", "karmic suffering"
    ]),
    ("archetypal-and-collective-realities", "Archetypal and Collective Realities", [
        "archetypal", "collective psyche", "perinatal matrices", "transpersonal",
        "cosmos and psyche", "jung archetypes"
    ]),
    ("diamond-luminosity", "The Diamond Luminosity and Ultimate Reality", [
        "diamond luminosity", "ultimate reality", "luminous", "clear light", "brilliance"
    ]),
    ("atman-brahman", "Atman = Brahman (The Identity of Self and Source)", [
        "atman brahman identity", "nonduality", "union with source", "identity with divine"
    ]),
    ("feminine-divine-cosmic-birth", "The Feminine Divine and Cosmic Birth", [
        "divine feminine", "cosmic birth", "mother universe", "shakti", "birthing humanity"
    ]),
    ("evolution-of-the-species-mind", "Evolution of the Species Mind", [
        "species mind", "collective evolution", "humanity evolution consciousness",
        "planetary mind"
    ]),
    ("future-human", "The Future Human", [
        "future human", "future humanity", "new human", "transformation of species"
    ]),
    ("universe-as-a-school", "The Universe as a School", [
        "universe as a school", "ring of destiny", "life between lives", "learning across lives"
    ]),
    ("integration-and-return", "Integration and Return", [
        "integration and return", "bringing it back", "post-session integration", "teaching impact"
    ]),
    ("great-death-and-rebirth", "The Great Death and Rebirth of the Cosmos (synthesis)", [
        "death and rebirth of cosmos", "cosmological rebirth", "apocalypse as unveiling",
        "kali yuga into new age"
    ]),
]

def main():
    today = datetime.date.today().isoformat()
    wrote = 0
    for qid, title, queries in MODULES:
        d = DOCS / qid
        d.mkdir(parents=True, exist_ok=True)
        sources = {
            "meta": {
                "qid": qid,
                "title": title,
                "date": today,
                "version": "v1",
                "source_policy": "Book-first. Public transcripts as color with timestamped links."
            },
            # book chunks left empty to be curated later (or populated by your own pipeline)
            "book": {
                "chunks": []
            },
            # talks: we store harvest *intent* here; the merger will fill `chunks`
            "talks": {
                "queries": queries,
                "chunks": []
            }
        }
        sj = d / "sources.json"
        if sj.exists():
            # non-destructive update: only add missing keys
            existing = json.loads(sj.read_text(encoding="utf-8"))
            existing.setdefault("meta", sources["meta"])
            existing.setdefault("book", {"chunks":[]})
            existing.setdefault("talks", {"queries":queries, "chunks":[]})
            if "queries" not in existing["talks"]:
                existing["talks"]["queries"] = queries
            sj.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
        else:
            sj.write_text(json.dumps(sources, indent=2, ensure_ascii=False), encoding="utf-8")
        # placeholder index to prevent 404s before build
        idx = d / "index.md"
        if not idx.exists():
            idx.write_text(f"---\ntitle: \"{title}\"\nid: \"{qid}\"\ndate: \"{today}\"\nversion: \"v1\"\n"
                           f"source_policy: \"Book-first. Public transcripts as color with timestamped links.\"\n---\n\n"
                           f"_Scaffolded. Run harvest + build to populate._\n", encoding="utf-8")
        wrote += 1
        print(f"[ok] {qid}: {sj}")
    print(f"\nScaffolded {wrote} module(s).")

if __name__ == "__main__":
    main()
