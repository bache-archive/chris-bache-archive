#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
from rapidfuzz import fuzz
from ftfy import fix_text
import re, os

PARQ="vectors/bache-talks.embeddings.parquet"
CAPS=Path("sources/captions")
TS=re.compile(r"(?P<sh>\d{1,2}):(?P<sm>\d{2}):(?P<ss>\d{2})\.\d+\s*-->\s*"
              r"(?P<eh>\d{1,2}):(?P<em>\d{2}):(?P<es>\d{2})\.\d+")

def norm(t): return re.sub(r"\s+"," ", fix_text((t or "").strip()))

def pick_vtt(tid):
    for suf in ("-human.vtt",".human.vtt",".vtt"):
        p=CAPS/f"{tid}{suf}"
        if p.exists(): return p

def parse_vtt(p):
    segs=[]; start=None; buf=[]
    for ln in p.read_text(encoding="utf-8",errors="ignore").splitlines():
        m=TS.search(ln)
        if m:
            if start is not None and buf:
                segs.append({"start":start,"text":norm(" ".join(buf))})
            start=int(m["sh"])*3600+int(m["sm"])*60+int(m["ss"])
            buf=[]
            continue
        if ln.strip() and not ln.startswith("WEBVTT"):
            buf.append(ln.strip())
    if start is not None and buf: segs.append({"start":start,"text":norm(" ".join(buf))})
    return segs

def windows(segs, minc=160, maxc=480):
    n=len(segs); i=0
    while i<n:
        j=i; parts=[]; total=0
        while j<n and total<minc: parts.append(segs[j]["text"]); total+=len(segs[j]["text"]); j+=1
        while j<n and total<maxc: parts.append(segs[j]["text"]); total+=len(segs[j]["text"]); j+=1
        yield (segs[i]["start"], norm(" ".join(parts)))
        i+=max(1,(j-i)//2)

def probe(text, lo=180, hi=320):
    t=norm(text)
    target=max(lo, min(hi, int(0.4*len(t))))
    return t[:target]

df=pd.read_parquet(PARQ)
miss=df[df["start_hhmmss"].isna()].copy()

samples=[]
for tid, g in miss.groupby("talk_id"):
    vtt=pick_vtt(tid)
    if not vtt: continue
    segs=parse_vtt(vtt)
    if not segs: continue
    for _,row in g.head(12).iterrows():  # sample first 12 misses
        q=probe(row["text"])
        best=0
        for _, blob in windows(segs):
            s=fuzz.partial_ratio(q.lower(), blob.lower())
            if s>best: best=s
        samples.append((tid, best, row["archival_title"][:50]))

samples=sorted(samples, key=lambda x: x[1], reverse=True)
print("Top 30 best scores among current failures:")
for tid,sc,title in samples[:30]:
    print(f"{tid:80}  best_score={sc}  {title}")
