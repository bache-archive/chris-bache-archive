import sys, os, csv, re, math, time
from pathlib import Path

try:
    from rapidfuzz.fuzz import partial_ratio
    HAVE_RF = True
except Exception:
    from difflib import SequenceMatcher
    HAVE_RF = False

def hhmmss(t):
    t = max(0.0, float(t))
    h = int(t//3600); m = int((t%3600)//60); s = int(round(t%60))
    return f"{h:02d}:{m:02d}:{s:02d}"

WORD_RE = re.compile(r"[A-Za-z0-9]+'?[A-Za-z0-9]+")
def normalize_text(s):
    toks = WORD_RE.findall((s or "").lower())
    return " ".join(toks)

def read_timeline(tsv_path):
    if not tsv_path or not os.path.isfile(tsv_path): return None
    words = []
    with open(tsv_path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 3: continue
            w, a, b = parts[0], float(parts[1]), float(parts[2])
            words.append((w, a, b))
    if not words: return None
    text_pieces, idx_map = [], []
    for i, (w, a, b) in enumerate(words):
        if i>0:
            text_pieces.append(" "); idx_map.append(-1)
        text_pieces.append(w)
        for _ in w: idx_map.append(i)
    stream = "".join(text_pieces)
    return {"words": words, "stream": stream, "idx_map": idx_map}

def exact_match(stream, chunk_norm):
    pos = stream.find(chunk_norm)
    if pos < 0: return None
    return pos, pos + len(chunk_norm)

def char_span_to_word_span(idx_map, start_char, end_char):
    n = len(idx_map)
    start_char = max(0, min(n-1, start_char))
    end_char = max(0, min(n-1, end_char-1))
    i = start_char
    while i < n and idx_map[i] == -1: i += 1
    if i >= n: return 0, 1
    j = end_char
    while j >= 0 and idx_map[j] == -1: j -= 1
    if j < 0: return 0, 1
    return idx_map[i], idx_map[j] + 1

def word_span_times(words, wi0, wi1):
    wi0 = max(0, wi0); wi1 = min(len(words), wi1)
    if wi0 >= wi1:
        a = words[wi0][1]; b = words[wi0][2]
        return a, b
    return words[wi0][1], words[wi1-1][2]

def local_fuzzy_score(a, b):
    if HAVE_RF:
        return partial_ratio(a, b) / 100.0
    return SequenceMatcher(None, a, b).ratio()

def anchor_candidates(chunk_words, stream_words, K=3, anchor_len=8, stride=12):
    """
    Yield (anchor_string, anchor_start_word_idx) from chunk_words.
    We take K anchors roughly spaced across the chunk.
    """
    L = len(chunk_words)
    if L == 0: return []
    idxs = [max(0, min(L-anchor_len, i)) for i in [0, L//2 - anchor_len//2, L - anchor_len]]
    idxs = sorted(set(idxs))[:K]
    anchors = []
    for i in idxs:
        j = min(L, i + anchor_len)
        anchors.append((" ".join(chunk_words[i:j]), i))
    return anchors

def find_anchor_in_stream(anchor, stream_words, start_at=0):
    """
    Exact locate a small anchor (string) in the stream by joining windows.
    Returns word index if found else -1. Uses a hash map for speed.
    """
    key_len = len(anchor.split())
    if key_len == 0: return -1
    # Build index for the first call (cache on function attribute)
    if not hasattr(find_anchor_in_stream, "cache") or find_anchor_in_stream.cache.get(id(stream_words), None) is None:
        # map from 3-gram of words to positions; speeds up probing
        index = {}
        sw = [w for (w,_,_) in stream_words]
        for i in range(0, len(sw)-2):
            tri = (sw[i], sw[i+1], sw[i+2])
            index.setdefault(tri, []).append(i)
        find_anchor_in_stream.cache = { id(stream_words): (index, sw) }
    index, sw = find_anchor_in_stream.cache[id(stream_words)]
    aw = anchor.split()
    if len(aw) < 3:
        # fall back to linear scan for very short anchors
        window = " ".join(sw)
        pos = window.find(anchor)
        if pos < 0: return -1
        # approximate word idx by counting spaces — rough but acceptable
        return window[:pos].count(" ")
    tri = tuple(aw[:3])
    starts = index.get(tri, [])
    for i in starts:
        j = i + len(aw)
        if j <= len(sw) and sw[i:j] == aw:
            return i
    return -1

def fast_align(chunk_norm, stream, words, search_radius_words=60):
    """
    1) Try exact substring.
    2) Else pick K anchors to locate approximate region(s).
    3) Around each region, form a small window and compute a fuzzy score.
    Returns best candidate dict or None.
    """
    pos = exact_match(stream["stream"], chunk_norm)
    if pos:
        a_char, b_char = pos
        wi0, wi1 = char_span_to_word_span(stream["idx_map"], a_char, b_char)
        a, b = word_span_times(stream["words"], wi0, wi1)
        return {"start": a, "end": b, "method": "exact", "score": 1.0}

    cw = chunk_norm.split()
    best = None
    anchors = anchor_candidates(cw, stream["words"])
    sw = stream["words"]
    sw_only = [w for (w,_,_) in sw]

    for anchor, _local in anchors:
        loc = find_anchor_in_stream(anchor, stream["words"])
        if loc == -1:
            continue
        # small window around the located anchor
        w0 = max(0, loc - search_radius_words//2)
        w1 = min(len(sw), loc + search_radius_words//2)
        window_text = " ".join(sw_only[w0:w1])
        score = local_fuzzy_score(chunk_norm, window_text)
        if (best is None) or (score > best["score"]):
            a, b = word_span_times(sw, w0, w1)
            best = {"start": a, "end": b, "method": "fuzzy", "score": float(score)}
    return best

def pick(chosen_cap, chosen_dia):
    if chosen_cap and not chosen_dia: return "captions", chosen_cap, chosen_dia
    if chosen_dia and not chosen_cap: return "diarist", chosen_dia, chosen_cap
    if not chosen_cap and not chosen_dia: return None, None, None
    # exact > fuzzy
    if chosen_cap["method"] == "exact" and chosen_dia["method"] != "exact": return "captions", chosen_cap, chosen_dia
    if chosen_dia["method"] == "exact" and chosen_cap["method"] != "exact": return "diarist", chosen_dia, chosen_cap
    # higher score
    if abs(chosen_cap["score"] - chosen_dia["score"]) > 0.02:
        return ("captions", chosen_cap, chosen_dia) if chosen_cap["score"] > chosen_dia["score"] else ("diarist", chosen_dia, chosen_cap)
    # tie -> captions
    return "captions", chosen_cap, chosen_dia

def main():
    if len(sys.argv) < 3:
        print("usage: align_chunks.py <chunks.csv> <captions.tsv|/dev/null> [diarist.tsv]", file=sys.stderr)
        sys.exit(2)
    chunks_csv = sys.argv[1]
    cap_tsv = sys.argv[2] if len(sys.argv) >= 3 else None
    dia_tsv = sys.argv[3] if len(sys.argv) >= 4 else None

    cap = None if (not cap_tsv or cap_tsv == "/dev/null" or not os.path.isfile(cap_tsv)) else read_timeline(cap_tsv)
    dia = None if (not dia_tsv or not os.path.isfile(dia_tsv)) else read_timeline(dia_tsv)

    out_path = Path("vectors/alignment_timecodes.csv")
    if not out_path.exists():
        with out_path.open("w", encoding="utf-8", newline="") as w:
            w.write("talk_id,chunk_index,youtube_id,start_sec,end_sec,start_hhmmss,end_hhmmss,source_used,method,score,confidence,alt_source,alt_method,alt_score,alt_start_sec,alt_end_sec,calibrated,calib_a,calib_b,notes,created_at_utc\n")

    now_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    with open(chunks_csv, "r", encoding="utf-8") as f, out_path.open("a", encoding="utf-8", newline="") as w:
        r = csv.DictReader(f)
        out = csv.writer(w)

        talk_id_preview = None
        row_count = 0
        for row in r:
            talk_id = row["talk_id"]
            if talk_id_preview is None:
                talk_id_preview = talk_id
                print(f"[align] talk={talk_id} — starting", file=sys.stderr)
            idx = int(row["chunk_index"])
            yid = row.get("youtube_id") or ""
            chunk_norm = normalize_text(row["chunk_text"])
            row_count += 1
            if row_count % 10 == 0:
                print(f"[align] talk={talk_id} chunk={idx}...", file=sys.stderr)

            cand_cap = fast_align(chunk_norm, cap, cap["words"]) if cap else None
            if cand_cap: cand_cap["source"] = "captions"
            cand_dia = fast_align(chunk_norm, dia, dia["words"]) if dia else None
            if cand_dia: cand_dia["source"] = "diarist"

            src, best, alt = pick(cand_cap, cand_dia)
            if best:
                a = max(0.0, best["start"]); b = max(a, best["end"])
                out.writerow([
                    talk_id, idx, yid,
                    f"{a:.3f}", f"{b:.3f}", hhmmss(a), hhmmss(b),
                    src, best["method"], f"{best['score']:.4f}", f"{best['score']:.4f}",
                    (alt["source"] if alt else ""), (alt["method"] if alt else ""),
                    (f"{alt['score']:.4f}" if alt else ""), (f"{alt['start']:.3f}" if alt else ""), (f"{alt['end']:.3f}" if alt else ""),
                    "false", "", "", "", now_utc
                ])
            else:
                out.writerow([
                    talk_id, idx, yid,
                    "", "", "", "",
                    "", "", "", "", "", "", "", "", "",
                    "false", "", "", "unmatched", now_utc
                ])

        print(f"[align] talk={talk_id_preview} — done ({row_count} chunks)", file=sys.stderr)

if __name__ == "__main__":
    main()
