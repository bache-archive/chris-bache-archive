#!/usr/bin/env python3
# ---
# fixity: verifier
# version: 1.2
# default_scope: active release manifest only
# ---

"""
verify_fixity.py — Verify file integrity against JSON manifests.

Schema expected in each manifest (min):
{
  "files": [
    { "path": "relative/path/from/repo/root.ext", "sha256": "<hex>" },
    ...
  ]
}

Defaults to checking ONLY the active release manifest at:
  manifests/release-*.json   (newest by mtime)

Options allow verifying all manifests and/or including archived ones.

Log:
  Appends one-line summary (with limited details) to checksums/FIXITY_LOG.md

Exit codes:
  0 = success (no mismatches/missing/malformed)
  2 = problems found (any mismatches, missing, or malformed)
  1 = usage / setup error

Usage:
  python3 tools/preservation/verify_fixity.py
  python3 tools/preservation/verify_fixity.py --manifest manifests/release-v3.5.3.json
  python3 tools/preservation/verify_fixity.py --all
  python3 tools/preservation/verify_fixity.py --all --include-archive --limit 200
"""

from __future__ import annotations
from pathlib import Path
import argparse, hashlib, json, sys
from datetime import datetime, timezone

# Resolve repo root: tools/preservation/ -> tools/ -> <repo>
REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFESTS_DIR = REPO_ROOT / "manifests"
ARCHIVE_DIR   = MANIFESTS_DIR / "_archive"
FIXITY_LOG    = REPO_ROOT / "checksums" / "FIXITY_LOG.md"

def sha256_file(path: Path, bufsize: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(bufsize), b""):
            h.update(chunk)
    return h.hexdigest()

def newest_release_manifest() -> Path | None:
    """
    Pick the newest 'manifests/release-*.json' by mtime (ignores _archive).
    """
    if not MANIFESTS_DIR.exists():
        return None
    candidates = sorted(
        [p for p in MANIFESTS_DIR.glob("release-*.json") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None

def collect_manifests(all_manifests: bool, include_archive: bool, explicit: Path | None) -> list[Path]:
    if explicit:
      return [explicit]

    if all_manifests:
        manifests = []
        manifests += [p for p in MANIFESTS_DIR.glob("*.json") if p.is_file()]
        if include_archive and ARCHIVE_DIR.exists():
            manifests += [p for p in ARCHIVE_DIR.glob("*.json") if p.is_file()]
        return sorted(manifests)

    # default: active only
    active = newest_release_manifest()
    return [active] if active else []

def verify_manifest(mpath: Path, limit: int, totals: dict) -> None:
    rel_manifest = str(mpath.relative_to(REPO_ROOT))
    try:
        man = json.loads(mpath.read_text(encoding="utf-8"))
    except Exception as e:
        totals["malformed"].append((rel_manifest, f"manifest parse error: {e}"))
        return

    entries = man.get("files", [])
    if not isinstance(entries, list):
        totals["malformed"].append((rel_manifest, "manifest missing 'files' array"))
        return

    for entry in entries:
        rel = entry.get("path")
        expect = entry.get("sha256")
        if not rel or not expect:
            totals["malformed"].append((rel_manifest, f"bad entry: {entry!r}"))
            continue

        fpath = REPO_ROOT / rel
        if not fpath.is_file():
            totals["missing"].append(rel)
            continue

        got = sha256_file(fpath)
        totals["checked"] += 1
        if got.lower() != expect.lower():
            totals["mismatches"].append((rel, f"expected {expect[:12]}…, got {got[:12]}…"))

def append_log(scope_desc: str, totals: dict, limit: int) -> None:
    FIXITY_LOG.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with FIXITY_LOG.open("a", encoding="utf-8") as log:
        ok = not totals["mismatches"] and not totals["missing"] and not totals["malformed"]
        if ok:
            log.write(f"{ts}  Verified {totals['checked']} files — all hashes match. ({scope_desc})\n")
            return

        log.write(
            f"{ts}  Verified {totals['checked']} files — "
            f"{len(totals['mismatches'])} mismatches, {len(totals['missing'])} missing, "
            f"{len(totals['malformed'])} malformed. ({scope_desc})\n"
        )
        if totals["malformed"]:
            log.write("  Malformed manifests:\n")
            for rel, msg in totals["malformed"][:limit]:
                log.write(f"    - {rel}: {msg}\n")
            if len(totals["malformed"]) > limit:
                log.write(f"    (+{len(totals['malformed'])-limit} more)\n")
        if totals["mismatches"]:
            log.write("  Mismatches:\n")
            for rel, msg in totals["mismatches"][:limit]:
                log.write(f"    - {rel}: {msg}\n")
            if len(totals["mismatches"]) > limit:
                log.write(f"    (+{len(totals['mismatches'])-limit} more)\n")
        if totals["missing"]:
            log.write("  Missing files:\n")
            for rel in totals["missing"][:limit]:
                log.write(f"    - {rel}\n")
            if len(totals["missing"]) > limit:
                log.write(f"    (+{len(totals['missing'])-limit} more)\n")

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=str, default=None,
                    help="Path to a single manifest to verify (overrides --all).")
    ap.add_argument("--all", action="store_true",
                    help="Verify ALL manifests in manifests/ (excludes _archive unless --include-archive).")
    ap.add_argument("--include-archive", action="store_true",
                    help="When used with --all, also verify manifests/_archive/*.json.")
    ap.add_argument("--limit", type=int, default=50,
                    help="Max detail lines to write into FIXITY_LOG (default: 50).")
    args = ap.parse_args()

    if not MANIFESTS_DIR.exists():
        print(f"[error] manifests dir not found: {MANIFESTS_DIR}", file=sys.stderr)
        print("Hint: build manifests first (e.g., build_manifests_from_checksums.py).", file=sys.stderr)
        return 1

    explicit = Path(args.manifest).resolve() if args.manifest else None
    if explicit and not explicit.exists():
        print(f"[error] manifest not found: {explicit}", file=sys.stderr)
        return 1

    manifests = collect_manifests(args.all, args.include_archive, explicit)
    if not manifests:
        print("[error] no manifest(s) found to verify. "
              "Build one (release-v*.json) or pass --manifest.", file=sys.stderr)
        return 1

    # Describe scope for logs
    if explicit:
        scope_desc = f"manifest={explicit.relative_to(REPO_ROOT)}"
    elif args.all:
        scope_desc = f"manifests={'with-archive' if args.include_archive else 'all-active-dir'}"
    else:
        scope_desc = f"manifest={manifests[0].relative_to(REPO_ROOT)}"

    totals = {
        "checked": 0,
        "mismatches": [],  # list[(path, msg)]
        "missing": [],     # list[path]
        "malformed": []    # list[(manifest, msg)]
    }

    for m in manifests:
        verify_manifest(m, args.limit, totals)

    append_log(scope_desc, totals, args.limit)

    if not totals["mismatches"] and not totals["missing"] and not totals["malformed"]:
        print(f"[ok] Checked {totals['checked']} files. All hashes match. "
              f"See {FIXITY_LOG.relative_to(REPO_ROOT)}")
        return 0
    else:
        print(f"[warn] Checked {totals['checked']} files — mismatches={len(totals['mismatches'])}, "
              f"missing={len(totals['missing'])}, malformed={len(totals['malformed'])}.")
        print(f"       See {FIXITY_LOG.relative_to(REPO_ROOT)} for details.")
        return 2

if __name__ == "__main__":
    sys.exit(main())