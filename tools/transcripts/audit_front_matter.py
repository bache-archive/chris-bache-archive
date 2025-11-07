#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import re, json, sys
from collections import Counter, defaultdict
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
TRANS = ROOT / "sources" / "transcripts"
INDEX = ROOT / "index.json"

FM_RE = re.compile(r'^\s*---\s*\n(.*?)\n---\s*\n', re.S)
META_LINE = re.compile(r'^\s*([A-Za-z0-9_\.]+)\s*:\s*(.+?)\s*$', re.M)

TYPE_NORMALIZE = {
    "talk":"lecture","lecture":"lecture","Lecture":"lecture","TALK":"lecture",
    "interview":"interview","Interview":"interview",
    "panel":"panel","Panel":"panel","panel-discussion":"panel","discussion":"panel",
    "q&a":"qanda","qanda":"qanda","Q&A":"qanda","qa":"qanda",
    "conversation":"conversation","reading":"reading","sermon":"sermon","clip":"clip"
}

def load_index_map():
    try:
        data = json.loads(INDEX.read_text(encoding="utf-8"))
        items = data["items"] if isinstance(data, dict) and "items" in data else data
    except Exception as e:
        print(f"[warn] could not load index.json: {e}", file=sys.stderr)
        items = []
    m = {}
    for it in items or []:
        p = (ROOT / it.get("transcript","")).resolve()
        m[str(p)] = it
    return m

def parse_fm(txt:str):
    m = FM_RE.match(txt)
    if not m: return {}, False
    block = m.group(1)
    meta = {}
    # very tolerant parse: key: value lines only
    for mm in META_LINE.finditer(block):
        k, v = mm.group(1).strip(), mm.group(2).strip().strip('"').strip("'")
        meta[k] = v
    return meta, True

def main():
    idx = load_index_map()
    files = sorted(TRANS.glob("*.md"))
    key_freq = Counter()
    type_raw_freq = Counter()
    type_norm_freq = Counter()
    missing_fm = []
    bad_date = []
    stray_urls = []
    unknown_keys = Counter()
    examples_unknown = defaultdict(list)

    known_keys = {
        "title","slug","date","type","channel","language","license","provenance",
        "diarist_txt","diarist_srt","identifiers","identifiers.wikidata_person","identifiers.openalex_person"
    }

    for md in files:
        txt = md.read_text(encoding="utf-8")
        meta, has = parse_fm(txt)
        if not has:
            missing_fm.append(md)
            continue

        # Flatten identifiers.* keys for key inventory
        keys = set(meta.keys())
        # also scan nested identifiers keys (quick/naive)
        if "identifiers" in meta:
            keys.add("identifiers")
        for k in keys:
            key_freq[k]+=1
            if k not in known_keys:
                unknown_keys[k]+=1
                if len(examples_unknown[k])<3:
                    examples_unknown[k].append(md.name)

        # type
        t_raw = meta.get("type","").strip()
        if t_raw:
            type_raw_freq[t_raw]+=1
            t_norm = TYPE_NORMALIZE.get(t_raw, "other")
            type_norm_freq[t_norm]+=1

        # date sanity (YYYY-MM-DD)
        d = meta.get("date","")
        if d:
            try:
                datetime.strptime(d, "%Y-%m-%d")
            except:
                bad_date.append((md.name, d))

        # look for obvious URL fields we want to drop from FM
        for k in ("youtube","url","youtube_url","blob_url","raw_url","audio","video"):
            if k in meta:
                stray_urls.append((md.name, k))

    # report
    total = len(files)
    print(f"Transcripts with missing front matter: {len(missing_fm)}/{total}")
    for m in missing_fm[:8]:
        print("  -", m.name)
    if len(missing_fm)>8: print("  ...")

    print("\nKey frequencies (top 20):")
    for k, c in key_freq.most_common(20):
        print(f"  {k:28s} {c}")

    print("\nUnknown/nonstandard keys (likely cleanup candidates):")
    for k, c in unknown_keys.most_common():
        ex = ", ".join(examples_unknown[k])
        print(f"  {k:28s} {c}  e.g. {ex}")

    print("\nType values (raw → normalized):")
    for r, c in type_raw_freq.most_common():
        n = TYPE_NORMALIZE.get(r, "other")
        print(f"  {r:18s} {c:3d}  → {n}")

    if bad_date:
        print("\nBad or non-ISO dates:")
        for name, d in bad_date[:12]:
            print(f"  {name:60s}  {d}")
        if len(bad_date)>12: print("  ...")

    if stray_urls:
        print("\nFront-matter fields that should be dropped (break DRY):")
        for name, k in stray_urls[:20]:
            print(f"  {name:60s}  {k}")
        if len(stray_urls)>20: print("  ...")

if __name__ == "__main__":
    main()
