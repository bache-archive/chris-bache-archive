#!/usr/bin/env python3
"""
tools/transcripts/rebuild_transcripts.py

Rebuild markdown transcripts from diarist .txt files using GPT normalization
with externalized prompt templates and glossary.

Worklist is driven by a file of basenames (one per line) provided via:
  - environment variable MISSING (path to the file), or
  - --missing-file PATH

Inputs:
  - sources/diarist/<basename>.txt   (also tolerates 'sources/diarists/')
  - index.json (optional; for title/date lookup)
  - tools/prompt_templates/edited_transcript_system.prompt.md
  - tools/prompt_templates/edited_transcript_user.prompt.md
  - assets/glossary/bache_glossary.json

Output:
  - sources/transcripts/<basename>.md  (archives any existing file to _archive/)

Key flags:
  --missing-file PATH      : file listing basenames to process (one per line)
  --index PATH             : index.json or {"items":[...]} (optional)
  --apply                  : write to sources/transcripts/ (default True)
  --dry-run                : show planned work, no writes
  --normalize-labels       : normalize body labels to diarist canonical names
  --sync-speakers-yaml     : write YAML speakers list from body labels
  --verbose                : verbose logging

Environment:
  OPENAI_API_KEY           : required
  OPENAI_MODEL             : default "gpt-5"
  CHUNK_CHARS              : max chars per chunk (default 30000)
  MAX_DIARIST_CHARS        : optional clip for testing (default 0 = no clip)
  MISSING                  : optional path to basenames file (same as --missing-file)
"""

from __future__ import annotations
import argparse, json, os, re, sys, time, hashlib, shutil, datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, List

# --- optional .env loading (silent if missing) ---
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=".env")
    load_dotenv(dotenv_path=".env.local", override=True)
except Exception:
    pass

DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
MAX_RETRIES = 5
RETRY_BASE_SEC = 2

# Prompt & glossary paths
SYSTEM_PROMPT_PATH = Path("tools/prompt_templates/edited_transcript_system.prompt.md")
USER_PROMPT_PATH   = Path("tools/prompt_templates/edited_transcript_user.prompt.md")
GLOSSARY_PATH      = Path("assets/glossary/bache_glossary.json")

# OpenAI SDK
try:
    from openai import OpenAI
except ImportError:
    print("Please: pip install openai>=1.40.0", file=sys.stderr)
    sys.exit(1)

# ------------------- regex & utilities -------------------

YAML_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
DIAR_SHA1_LINE_RE = re.compile(r'(?m)^\s*diarist_sha1:\s*([0-9a-f]{40})\s*$')
DIAR_SHA1_HTML_RE = re.compile(r'<!--\s*diarist_sha1:([0-9a-f]{40})\s*-->')

# Fallback minimal system prompt (used only if file missing)
SYSTEM_MSG_FALLBACK = (
    "You are editing a diarized transcript into a clear, faithful Markdown transcript. "
    "Preserve meaning and sequence, enforce speaker tags as **Name:**, no hallucinations."
)

def info(enabled: bool, msg: str) -> None:
    if enabled:
        print(f"[info] {msg}", flush=True)

def warn(msg: str) -> None:
    print(f"[warn] {msg}", flush=True)

def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")

def write_text(p: Path, text: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")

def split_front_matter(md: str):
    m = YAML_FM_RE.match(md)
    if not m:
        return None, md
    return m.group(1), md[m.end():]  # (fm_without_delims, body)

def join_front_matter(fm_body: Optional[str], body: str) -> str:
    if fm_body is None:
        return f"---\n---\n{body}"
    return f"---\n{fm_body}\n---\n{body}"

def sha1_bytes(b: bytes) -> str:
    h = hashlib.sha1()
    h.update(b)
    return h.hexdigest()

def sha1_str(s: str) -> str:
    return sha1_bytes(s.encode("utf-8"))

def ts_str() -> str:
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

def archive_with_timestamp(path: Path, archive_dir: Path) -> Optional[Path]:
    if not path.exists():
        return None
    archived = archive_dir / f"{path.stem}.{ts_str()}{path.suffix}"
    archive_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, archived)
    return archived

def ensure_client() -> OpenAI:
    if not OPENAI_API_KEY:
        print("Error: OPENAI_API_KEY not set.", file=sys.stderr)
        sys.exit(1)
    return OpenAI(api_key=OPENAI_API_KEY, timeout=300.0)

def call_model(client: OpenAI, model: str, system_msg: str, user_msg: str) -> str:
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
            )
            out = (resp.choices[0].message.content or "").strip()
            if out:
                return out
            raise RuntimeError("empty_completion_from_chat_api")
        except Exception as e1:
            last_err = e1
            try:
                r = client.responses.create(
                    model=model,
                    input=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": user_msg},
                    ],
                )
                if hasattr(r, "output") and r.output:
                    parts = []
                    for item in r.output:
                        if getattr(item, "type", "") == "message":
                            for c in getattr(item, "content", []):
                                if getattr(c, "type", "") == "output_text":
                                    parts.append(getattr(c, "text", ""))
                    out = "\n".join(parts).strip()
                    if out:
                        return out
                if hasattr(r, "output_text") and r.output_text:
                    return r.output_text.strip()
                raise RuntimeError("empty_completion_from_responses_api")
            except Exception as e2:
                last_err = e2
                if attempt == MAX_RETRIES:
                    raise
                sleep_s = RETRY_BASE_SEC * (2 ** (attempt - 1))
                warn(f"API error ({last_err}); retry {attempt}/{MAX_RETRIES} in {sleep_s:.1f}s")
                time.sleep(sleep_s)
    raise last_err or RuntimeError("Unknown API failure")

def normalize_label_spacing(text: str) -> str:
    # "Speaker :" -> "Speaker:"
    return re.sub(r"([^\n:]{1,80})\s+:\s", r"\1: ", text)

def chunk_text(s: str, max_chars: int = 30000) -> List[str]:
    if len(s) <= max_chars:
        return [s]
    parts, buf, total = [], [], 0
    for para in s.split("\n\n"):
        block = para + "\n\n"
        if total + len(block) > max_chars and buf:
            parts.append("".join(buf)); buf, total = [], 0
        buf.append(block); total += len(block)
    if buf: parts.append("".join(buf))
    return parts

# --------------- index / metadata helpers ----------------

def load_index(index_path: Path) -> Optional[list]:
    if not index_path or not index_path.exists():
        return None
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else data.get("items", [])
    except Exception as e:
        warn(f"Failed to parse {index_path}: {e}")
        return None

def index_by_basename(idx: Optional[list]) -> Dict[str, dict]:
    m: Dict[str, dict] = {}
    if not idx:
        return m
    for entry in idx:
        path = entry.get("transcript") or entry.get("file") or ""
        base = Path(path).stem if path else ""
        if base:
            m[base] = entry
    return m

def derive_title_from_index_entry(entry: dict, default_base: str) -> str:
    return (entry.get("archival_title") or entry.get("title") or "").strip() or default_base

def derive_date_from_index_entry(entry: dict) -> str:
    for k in ("published", "published_at", "date", "recorded_at"):
        v = (entry.get(k) or "").strip()
        if v:
            return v
    file_path = entry.get("file","")
    m = re.search(r"/(\d{4}-\d{2}-\d{2})-", file_path or "")
    return m.group(1) if m else ""

# --------------- diarist / label helpers ----------------

def diarist_path_for(base: str) -> Optional[Path]:
    p1 = Path("sources/diarist") / f"{base}.txt"
    if p1.exists():
        return p1
    p2 = Path("sources/diarists") / f"{base}.txt"   # tolerate plural folder
    if p2.exists():
        return p2
    return None

def extract_speakers_from_diarist(txt: str) -> List[str]:
    labs = []
    seen = set()
    for line in txt.splitlines():
        if ":" not in line or line.strip().startswith("---"):
            continue
        lab = line.split(":", 1)[0]
        lab = re.sub(r"\s+\d+$", "", lab).strip()
        if not lab:
            continue
        if lab.lower().startswith("transcribed by "):
            continue
        if lab not in seen:
            seen.add(lab)
            labs.append(lab)
    return labs

def set_yaml_speakers(md: str, speakers_list: List[str]) -> str:
    m = YAML_FM_RE.match(md)
    speakers_line = 'speakers: [' + ", ".join(f'"{s}"' for s in speakers_list) + ']'
    if not m:
        return f"---\n{speakers_line}\n---\n{md}"
    fm = m.group(1)
    body = md[m.end():]
    fm = re.sub(r'(?m)^\s*speakers:\s*(\[[^\n]*\]|\\\[[^\n]*\\\])\s*\n?', "", fm)
    if fm and not fm.endswith("\n"):
        fm += "\n"
    fm += speakers_line + "\n"
    return f"---\n{fm}---\n{body}"

def normalize_body_labels_to_diarist(md: str, speakers: List[str]) -> str:
    m = YAML_FM_RE.match(md)
    fm = m.group(1) if m else None
    body = md[m.end():] if m else md
    for name in sorted(speakers, key=len, reverse=True):
        prefix = r'(^[>#*\-\s]*?(?:\*\*|\*|__|_|`)?\s*)'
        name_ci = re.escape(name)
        pat = re.compile(prefix + r'(' + name_ci + r')\s*\d*(?=:\s)', re.IGNORECASE | re.MULTILINE)
        def _repl(mo): return f"{mo.group(1)}{name}"
        body = pat.sub(_repl, body)
    return f"---\n{fm}\n---\n{body}" if fm is not None else body

def extract_recorded_diarist_sha1(md_path: Path) -> Optional[str]:
    if not md_path.exists():
        return None
    text = md_path.read_text(encoding="utf-8")
    m = DIAR_SHA1_LINE_RE.search(text)
    if m:
        return m.group(1)
    m = DIAR_SHA1_HTML_RE.search(text)
    if m:
        return m.group(1)
    return None

# --------------- prompts & glossary ----------------

def load_system_prompt() -> str:
    if SYSTEM_PROMPT_PATH.exists():
        return read_text(SYSTEM_PROMPT_PATH).strip()
    warn(f"Missing system prompt at {SYSTEM_PROMPT_PATH}, using fallback.")
    return SYSTEM_MSG_FALLBACK

def load_user_template() -> str:
    if USER_PROMPT_PATH.exists():
        return read_text(USER_PROMPT_PATH).strip()
    warn(f"Missing user prompt at {USER_PROMPT_PATH}, using inline fallback.")
    # simple fallback with raw transcript placeholder
    return (
        "# INPUT TRANSCRIPT (verbatim)\n{raw_transcript_text}\n\n"
        "# CONTEXT\n"
        "Archival title: {title}\n"
        "Recorded/published date: {date}\n"
        "Chunk {i} of {n}. Process only this chunk.\n\n"
        "# GLOSSARY\n{glossary_json_or_empty_object}\n"
    )

def load_glossary_json() -> str:
    try:
        if GLOSSARY_PATH.exists():
            obj = json.loads(read_text(GLOSSARY_PATH))
            # Serialize compactly but stably
            return json.dumps(obj, ensure_ascii=False, separators=(",", ": "))
    except Exception as e:
        warn(f"Failed to read/parse glossary at {GLOSSARY_PATH}: {e}")
    # fallback empty object
    return "{}"

def render_user_prompt(
    template: str,
    title: str,
    date: str,
    diarist_chunk: str,
    i: int,
    n: int,
    glossary_json: str
) -> str:
    # Replace known placeholders (both variants supported)
    out = template
    replacements = {
        "{raw_transcript_text}": diarist_chunk,
        "{diarist_chunk}": diarist_chunk,
        "{title}": title,
        "{date}": date,
        "{i}": str(i),
        "{n}": str(n),
        "{glossary_json_or_empty_object}": glossary_json,
    }
    for k, v in replacements.items():
        out = out.replace(k, v)

    # If the template didn't include context tokens, append a minimal context block
    if "{title}" not in template and "{date}" not in template and "{i}" not in template:
        out = (
            f"{out.rstrip()}\n\n"
            f"# CONTEXT\n"
            f"Archival title: {title}\n"
            f"Recorded/published date: {date}\n"
            f"Chunk {i} of {n}. Process only this chunk.\n"
        )

    # Ensure glossary is present
    if "{glossary_json_or_empty_object}" not in template and "GLOSSARY" not in out:
        out = f"{out.rstrip()}\n\n# GLOSSARY\n{glossary_json}\n"

    return out

# --------------- core processing ----------------

def process_one(
    basename: str,
    args,
    client: OpenAI,
    idx_map: Dict[str, dict],
    system_msg: str,
    user_template: str,
    glossary_json: str,
) -> Tuple[str, Optional[str]]:
    # locate diarist
    diar_path = diarist_path_for(basename)
    if not diar_path or not diar_path.exists():
        return "skipped", f"no diarist for {basename}"

    # target paths
    target_rel = Path("sources/transcripts") / f"{basename}.md"
    target_abs = Path(".").resolve() / target_rel

    # load diarist text
    diar_text = read_text(diar_path)
    diar_hash = sha1_str(diar_text)

    if args.verbose:
        info(True, f"{basename}: diarist chars={len(diar_text):,}")
    max_chars = int(os.environ.get("MAX_DIARIST_CHARS", "0") or "0")
    if max_chars > 0 and len(diar_text) > max_chars:
        if args.verbose:
            info(True, f"{basename}: clipping diarist to {max_chars:,} chars for this run")
        diar_text = diar_text[:max_chars]

    # prepare front matter from existing transcript if present
    fm_body = None
    if target_abs.exists():
        fm_body, _ = split_front_matter(read_text(target_abs))

    # title/date from index (optional)
    entry = idx_map.get(basename, {})
    title = derive_title_from_index_entry(entry, basename)
    date  = derive_date_from_index_entry(entry)

    # chunk & call model
    chunk_size = int(os.environ.get("CHUNK_CHARS", "30000"))
    chunks = chunk_text(diar_text, max_chars=chunk_size)
    outs = []
    for i, ch in enumerate(chunks, 1):
        if args.verbose:
            info(True, f"{basename}: sending chunk {i}/{len(chunks)} ({len(ch):,} chars)")
        user_msg = render_user_prompt(user_template, title, date, ch, i, len(chunks), glossary_json)
        piece = call_model(client, args.model, system_msg, user_msg)
        piece = normalize_label_spacing(piece)
        outs.append(piece)
    out = "\n\n".join(outs)

    # strip inline timecodes that slipped through
    out = re.sub(r'^([#>* _`-]*[^\n:]{1,80})\s+[0-9]{1,2}:[0-9]{2}(?::[0-9]{2})?\s*:', r'\1:', out, flags=re.M)

    # stage lines to resolve generics after we know mains
    generic_pat = re.compile(r'^\s*(Unknown Speaker|Speaker\s+\d+)\s*:', re.I)
    staged = []
    last_named = None
    for line in out.splitlines():
        if ":" in line and not line.startswith("<!--"):
            left, rest = line.split(":", 1)
            label = left.strip()
            text  = rest.lstrip()
            if generic_pat.match(label):
                staged.append(("__GENERIC__", text))
            else:
                last_named = label
                staged.append((label, text))
        else:
            staged.append((None, line))

    # mains/interviewer guess from diarist labels
    diar_labs = extract_speakers_from_diarist(diar_text)
    mains = [s for s in diar_labs if not re.match(r'(?i)unknown speaker|speaker\s+\d+', s)]
    interviewer = next((s for s in mains if s.lower() in {"interviewer", "host", "moderator"}), None)
    if not interviewer and mains:
        interviewer = next((s for s in mains if s.lower() != "chris bache"), mains[0] if mains else None)

    rebuilt = []
    last_named = interviewer or (mains[0] if mains else None)
    for label, text in staged:
        if label is None:
            rebuilt.append(text)
            continue
        if label == "__GENERIC__":
            target = interviewer if (text.endswith("?") and interviewer) else (last_named or interviewer or (mains[0] if mains else "Interviewer"))
            rebuilt.append(f"{target}: {text}")
            last_named = target
        else:
            rebuilt.append(f"{label}: {text}")
            if label in mains:
                last_named = label

    body = "\n".join(rebuilt)

    # optional body label normalization
    if mains and args.normalize_labels:
        tmp = join_front_matter(None, body)  # attach empty YAML for helper
        tmp = normalize_body_labels_to_diarist(tmp, mains)
        mtmp = YAML_FM_RE.match(tmp)
        body = tmp[mtmp.end():] if mtmp else tmp

    # final polish
    body = re.sub(r'\b([0-9]{1,2}:[0-9]{2}(?::[0-9]{2})?)\b', '', body)
    body = re.sub(r'[ \t]{2,}', ' ', body)
    body = re.sub(r'\n{3,}', '\n\n', body)
    body = re.sub(r'(?m)^[#>* _`-]*\b(?:Unknown Speaker|Speaker\s+\d+)\s*:', 'Audience:', body)

    # compose final md with YAML
    fm_body_updated = fm_body or ""
    if "diarist_sha1:" in fm_body_updated:
        fm_body_updated = re.sub(DIAR_SHA1_LINE_RE, f"diarist_sha1: {diar_hash}", fm_body_updated)
    else:
        if fm_body_updated and not fm_body_updated.endswith("\n"):
            fm_body_updated += "\n"
        fm_body_updated += f"diarist_sha1: {diar_hash}\n"

    # also keep an HTML comment tag near top for quick grepping
    body_with_tag = f"<!-- diarist_sha1:{diar_hash} -->\n{body}".strip() + "\n"
    final_md = join_front_matter(fm_body_updated, body_with_tag)

    if args.dry_run:
        return "planned", str(target_rel)

    # archive & write
    if args.apply:
        archive_dir = target_abs.parent / "_archive"
        if target_abs.exists():
            archived = archive_with_timestamp(target_abs, archive_dir)
            if archived:
                info(args.verbose, f"archive: {target_abs.name} -> {archived.name}")
        write_text(target_abs, final_md)
        return "applied", str(target_rel)
    else:
        build_out = Path("./build") / target_rel
        write_text(build_out, final_md)
        return "built", str(build_out)

# --------------- worklist (MISSING) ----------------

SAFE_BASE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

def load_missing_list(path: Path, verbose: bool=False) -> List[str]:
    if not path or not path.exists():
        return []
    basenames: List[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if "File name too long" in line:
            continue
        if SAFE_BASE_RE.match(line):
            basenames.append(line)
        else:
            warn(f"Skipping suspicious basename in MISSING: {line}")
    if verbose:
        info(True, f"MISSING list loaded: {len(basenames)} items from {path}")
    return basenames

# --------------- main ----------------

def main():
    ap = argparse.ArgumentParser(description="Rebuild transcripts from diarist using GPT; write to sources/transcripts.")
    ap.add_argument("--root", default=".", help="Repo root")
    ap.add_argument("--index", default="index.json", help="index.json path (optional)")
    ap.add_argument("--missing-file", default=os.environ.get("MISSING", ""), help="Path to file containing basenames (one per line)")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="OpenAI model (default env OPENAI_MODEL or gpt-5)")
    ap.add_argument("--apply", action="store_true", default=True, help="Write to sources/transcripts (default: True)")
    ap.add_argument("--no-archive", action="store_true", help="(reserved) kept for compatibility; archiving is on by default")
    ap.add_argument("--dry-run", action="store_true", help="List planned work, do not write files")
    ap.add_argument("--normalize-labels", action="store_true", help="Normalize body labels to diarist canonical names")
    ap.add_argument("--sync-speakers-yaml", action="store_true", help="Write YAML speakers list from body labels (applied if fm exists)")
    ap.add_argument("--verbose", action="store_true", help="Verbose logging")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    os.chdir(root)

    client = ensure_client()

    # Load prompts & glossary
    system_msg = load_system_prompt()
    user_template = load_user_template()
    glossary_json = load_glossary_json()

    # Load index (optional)
    idx = load_index(Path(args.index)) if args.index else None
    idx_map = index_by_basename(idx)

    # Worklist from MISSING
    missing_path = Path(args.missing_file) if args.missing_file else None
    work = load_missing_list(missing_path, verbose=args.verbose) if missing_path else []

    if not work:
        warn("No basenames to process. Provide --missing-file or set $MISSING to a file with one basename per line.")
        sys.exit(1)

    planned = built = applied = skipped = errors = 0
    for i, base in enumerate(work, 1):
        try:
            if args.dry_run:
                status, where = process_one(base, args, client, idx_map, system_msg, user_template, glossary_json)
                if status in ("planned",):
                    planned += 1
                    print(f"[plan] {base} -> {where}")
                else:
                    print(f"[plan?] {base}: unexpected status {status}")
                continue

            status, where = process_one(base, args, client, idx_map, system_msg, user_template, glossary_json)
            if status == "applied":
                applied += 1
                print(f"[applied] {base} -> {where}")
            elif status == "built":
                built += 1
                print(f"[built]   {base} -> {where}")
            elif status == "skipped":
                skipped += 1
                print(f"[skip]    {base}: {where}")
            else:
                print(f"[{status}] {base} -> {where}")
        except KeyboardInterrupt:
            print("\nInterrupted.")
            break
        except Exception as e:
            errors += 1
            print(f"[error] {base}: {e}", file=sys.stderr)

    print("\n=== Summary ===")
    print(f"Planned:  {planned}")
    print(f"Built:    {built}")
    print(f"Applied:  {applied}")
    print(f"Skipped:  {skipped}")
    print(f"Errors:   {errors}")

if __name__ == "__main__":
    main()