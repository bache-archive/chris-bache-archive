#!/usr/bin/env python3
"""
tools/make_checksums.py

Create focused SHA256 manifests for archival & web-served artifacts.

Outputs:
  - checksums/RELEASE-<version>.sha256     (primary manifest)
  - downloads/checksums.sha256             (optional, for downloads/)
  - updates checksums/FIXITY_LOG.md

Usage:
  python3 tools/make_checksums.py --version v3.3.5
  python3 tools/make_checksums.py --version v3.3.5 --verify
  python3 tools/make_checksums.py --version v3.3.5 --no-downloads
"""

from __future__ import annotations
from pathlib import Path
import argparse, hashlib, sys, os, datetime

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "checksums"
DL_DIR  = ROOT / "downloads"
FIXITY_LOG = OUT_DIR / "FIXITY_LOG.md"

# ---- selection rules ----

INCLUDE_FILE_GLOBS = [
    # site/landing & sitemaps
    "index.html", "index.md", "index.json", "robots.txt",
    "sitemap*.xml", "LICENSE", "README*.md", "CONFIG.md",
    "assets/style.css",

    # educational pages
    "docs/educational/*/index.md",
    "docs/educational/*/index.html",
    "docs/educational/*/sources.json",

    # manifests (exclude quarantined)
    "manifests/*.json",

    # sources (captions/diarist/transcripts)
    "sources/captions/**/*",
    "sources/diarist/**/*",
    "sources/transcripts/**/*",

    # vectors (FAISS/parquet/chunks manifest)
    "vectors/bache-talks.index.faiss",
    "vectors/bache-talks.embeddings.parquet",
    "vectors/chunks.jsonl",
]

TEXTY_EXT_WHITELIST = {
    ".md", ".json", ".vtt", ".srt", ".txt", ".html", ".css", ".xml"
}

EXCLUDE_DIR_PREFIXES = {
    ".git", ".venv", "build", "tmp", "reports", "backups",
    "private_backups", "bundle-v2.3-media", "alignments",
    "checksums/_archive",
    "manifests/_quarantined",
}

def is_excluded(p: Path) -> bool:
    parts = p.relative_to(ROOT).parts
    return any(parts and parts[0].startswith(prefix) for prefix in EXCLUDE_DIR_PREFIXES)

def sha256_of(path: Path, bufsize: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(bufsize)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def iter_globs(patterns: list[str]):
    for pat in patterns:
        for p in ROOT.glob(pat):
            if p.is_dir():
                continue
            if is_excluded(p):
                continue
            # For sources/** we often only want text-ish sidecars (skip big media if any slipped in)
            if any(p.as_posix().startswith(f"sources/{sub}") for sub in ("captions","diarist","transcripts")):
                if p.suffix and p.suffix.lower() not in TEXTY_EXT_WHITELIST:
                    continue
            yield p

def build_primary_list() -> list[Path]:
    # dedupe & sort
    seen = set()
    out = []
    for p in iter_globs(INCLUDE_FILE_GLOBS):
        rp = p.relative_to(ROOT).as_posix()
        if rp in seen:
            continue
        seen.add(rp)
        out.append(p)
    return sorted(out, key=lambda x: x.relative_to(ROOT).as_posix())

def write_manifest(paths: list[Path], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for p in paths:
        digest = sha256_of(p)
        rel = p.relative_to(ROOT).as_posix()
        # Match `shasum -a 256` style: "<hash>  <path>"
        lines.append(f"{digest}  {rel}")
    text = "\n".join(lines) + ("\n" if lines else "")
    dest.write_text(text, encoding="utf-8")

def verify_manifest(manifest: Path) -> int:
    ok = 0
    bad = 0
    missing = 0
    for line in manifest.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            digest, rel = line.split(None, 1)
            rel = rel.strip()
            if rel.startswith("*") or rel.startswith(" "):
                rel = rel.lstrip("* ").strip()
        except ValueError:
            print(f"[warn] malformed line: {line}")
            bad += 1
            continue
        fpath = ROOT / rel
        if not fpath.exists():
            print(f"[MISS] {rel}")
            missing += 1
            continue
        cur = sha256_of(fpath)
        if cur == digest:
            ok += 1
        else:
            print(f"[FAIL] {rel}")
            bad += 1
    if bad == 0 and missing == 0:
        print(f"[ok] verified {ok} entries")
    else:
        print(f"[warn] verify: ok={ok} fail={bad} missing={missing}")
    return bad + missing

def build_downloads_manifest(dest: Path) -> int:
    if not DL_DIR.exists():
        return 0
    files = [p for p in DL_DIR.rglob("*") if p.is_file()]
    files = [p for p in files if not is_excluded(p)]
    files_sorted = sorted(files, key=lambda x: x.relative_to(ROOT).as_posix())
    if not files_sorted:
        return 0
    write_manifest(files_sorted, dest)
    return len(files_sorted)

def append_fixity_log(version: str, primary_count: int, downloads_count: int) -> None:
    FIXITY_LOG.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now().strftime("%Y-%m-%d")
    entry = (
        f"\n### {version} — {now}\n"
        f"- Wrote checksums/RELEASE-{version}.sha256 ({primary_count} entries)\n"
        f"- Wrote downloads/checksums.sha256 ({downloads_count} entries)\n"
    )
    with FIXITY_LOG.open("a", encoding="utf-8") as f:
        f.write(entry)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True, help="Release tag, e.g. v3.3.5")
    ap.add_argument("--verify", action="store_true", help="Verify after writing")
    ap.add_argument("--no-downloads", action="store_true", help="Skip downloads/ manifest")
    args = ap.parse_args()

    primary_paths = build_primary_list()
    primary_dest = OUT_DIR / f"RELEASE-{args.version}.sha256"
    write_manifest(primary_paths, primary_dest)
    print(f"[ok] wrote {primary_dest} ({len(primary_paths)} entries)")

    dl_count = 0
    if not args.no_downloads:
        dl_dest = DL_DIR / "checksums.sha256"
        dl_count = build_downloads_manifest(dl_dest)
        if dl_count:
            print(f"[ok] wrote {dl_dest} ({dl_count} entries)")
        else:
            print("[info] downloads/ empty or skipped")

    append_fixity_log(args.version, len(primary_paths), dl_count)

    if args.verify:
        print("[verify] primary manifest")
        rc = verify_manifest(primary_dest)
        if rc != 0:
            sys.exit(2)
        if not args.no_downloads and (DL_DIR / "checksums.sha256").exists():
            print("[verify] downloads manifest")
            rc2 = verify_manifest(DL_DIR / "checksums.sha256")
            if rc2 != 0:
                sys.exit(3)

if __name__ == "__main__":
    main()
