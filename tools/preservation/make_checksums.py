#!/usr/bin/env python3
"""
tools/preservation/make_checksums.py

Create focused SHA256 manifests for archival & web-served artifacts.

Outputs:
  - checksums/RELEASE-<version>.sha256     (primary manifest; sorted, portable)
  - downloads/checksums.sha256             (optional; for local downloads/)
  - appends checksums/FIXITY_LOG.md

Usage:
  python3 tools/preservation/make_checksums.py --version v3.5.0
  python3 tools/preservation/make_checksums.py --version v3.5.0 --verify
  python3 tools/preservation/make_checksums.py --version v3.5.0 --no-downloads
"""

from __future__ import annotations
from pathlib import Path
import argparse, hashlib, sys, os, datetime

ROOT = Path(__file__).resolve().parents[2]  # .../tools/preservation -> repo root
OUT_DIR = ROOT / "checksums"
DL_DIR  = ROOT / "downloads"
FIXITY_LOG = OUT_DIR / "FIXITY_LOG.md"

# ---- selection rules ----
# Keep this conservative: only hash files that are part of the canonical archive or the public site.
INCLUDE_FILE_GLOBS = [
    # Root site & docs landing
    "index.html", "index.md", "index.json", "robots.txt",
    "sitemap*.xml", "LICENSE", "README*.md", "CONFIG.md",

    # Site assets (css/images used by the site)
    "assets/**/*",

    # Meta & schemas
    "meta/**/*",

    # Educational subpages (if present)
    "docs/educational/*/index.md",
    "docs/educational/*/index.html",
    "docs/educational/*/sources.json",

    # Manifests (exclude quarantined)
    "manifests/*.json",

    # Sources (text-ish only)
    "sources/captions/**/*",
    "sources/diarist/**/*",
    "sources/transcripts/**/*",

    # Book registries inside transcripts (e.g., LSDMU)
    "sources/books/**/*",

    # Alignments: JSON/CSV/YAML only (no media)
    "alignments/**/*",

    # Vectors (allow-list)
    "vectors/bache-talks.index.faiss",
    "vectors/bache-talks.embeddings.parquet",
    "vectors/chunks.jsonl",
]

# Only hash textish and small aux formats from sources/ & alignments/
TEXTY_EXT_WHITELIST = {
    ".md", ".json", ".vtt", ".srt", ".txt", ".html", ".css", ".xml",
    ".yaml", ".yml", ".csv", ".tsv", ".faiss", ".parquet", ".jsonl"
}

# Top-level directories to skip entirely
EXCLUDE_DIR_PREFIXES = {
    ".git", ".venv", "build", "tmp", "out", "logs", "reports", "backups",
    "private_backups", "bundle-v2.3-media", "downloads",
    "checksums/_archive", "manifests/_quarantined", "chris-bache-archive.mirror",
    "dist"  # release bundles often live here; not part of fixity over source tree
}

MEDIA_EXTS = {".mp3", ".mp4", ".m4a", ".webm", ".opus", ".wav", ".flac", ".mkv", ".mov", ".avi"}

def top_level_prefix(path: Path) -> str | None:
    try:
        return path.relative_to(ROOT).parts[0]
    except Exception:
        return None

def is_excluded(p: Path) -> bool:
    tl = top_level_prefix(p)
    return tl in EXCLUDE_DIR_PREFIXES

def wanted_path(p: Path) -> bool:
    """Apply per-area rules for included globs."""
    if is_excluded(p) or p.is_dir():
        return False

    rel = p.relative_to(ROOT).as_posix()

    # Never include media binaries in any area
    if p.suffix.lower() in MEDIA_EXTS:
        return False

    # Strict text-only for sources and alignments
    if rel.startswith("sources/") or rel.startswith("alignments/"):
        if p.suffix and p.suffix.lower() not in TEXTY_EXT_WHITELIST:
            return False

    # For assets/, allow common small web assets; skip massive binaries by suffix
    if rel.startswith("assets/"):
        # Allow typical web assets; if you later add videos in assets, they will be skipped by MEDIA_EXTS above.
        pass

    return True

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
    seen: set[str] = set()
    for pat in patterns:
        for p in ROOT.glob(pat):
            if not p.exists() or p.is_dir():
                continue
            if not wanted_path(p):
                continue
            rel = p.relative_to(ROOT).as_posix()
            if rel in seen:
                continue
            seen.add(rel)
            yield p

def build_primary_list() -> list[Path]:
    out = list(iter_globs(INCLUDE_FILE_GLOBS))
    # Deterministic ordering by POSIX path
    return sorted(out, key=lambda x: x.relative_to(ROOT).as_posix())

def write_manifest(paths: list[Path], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for p in paths:
        digest = sha256_of(p)
        rel = p.relative_to(ROOT).as_posix()
        # Match `shasum -a 256` format: "<hash><two spaces><path>"
        lines.append(f"{digest}  {rel}")
    text = "\n".join(lines) + ("\n" if lines else "")
    dest.write_text(text, encoding="utf-8")

def verify_manifest(manifest: Path) -> int:
    ok = bad = missing = 0
    for line in manifest.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s:
            continue
        try:
            digest, rel = s.split(None, 1)
            rel = rel.strip().lstrip("* ")  # tolerate 'coreutils' style
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
    if not files:
        return 0
    files_sorted = sorted(files, key=lambda x: x.relative_to(ROOT).as_posix())
    write_manifest(files_sorted, dest)
    return len(files_sorted)

def append_fixity_log(version: str, primary_count: int, downloads_count: int) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FIXITY_LOG.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        f"\n### {version} — {now}",
        f"- Wrote checksums/RELEASE-{version}.sha256 ({primary_count} entries)",
        f"- Wrote downloads/checksums.sha256 ({downloads_count} entries)" if downloads_count else "- Skipped downloads manifest",
    ]
    with FIXITY_LOG.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True, help="Release tag, e.g. v3.5.0")
    ap.add_argument("--verify", action="store_true", help="Verify after writing the primary manifest")
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