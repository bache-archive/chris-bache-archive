#!/usr/bin/env python3
"""
build_manifests_from_checksums.py — Convert a shasum list to a JSON manifest.

Input format (e.g., checksums/LATEST.sha256):
<sha256>  relative/path/from/repo

Output: manifests/release-<version>.json
{
  "version": "vX.Y.Z",
  "source": "checksums/RELEASE-vX.Y.Z.sha256|LATEST.sha256",
  "generated": "UTC timestamp",
  "files": [{"path":"...", "sha256":"..."}]
}
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import argparse, json, sys

REPO = Path(__file__).resolve().parents[2]

def parse_shasum(path: Path):
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        # Accept "<hash><spaces><path>"
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        sha, rel = parts
        rel = rel.strip().lstrip("*").strip()
        entries.append({"path": rel, "sha256": sha})
    return entries

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checksums", default="checksums/LATEST.sha256",
                    help="Path to shasum file (default: checksums/LATEST.sha256)")
    ap.add_argument("--version", default=None,
                    help="Version label for manifest (e.g., v3.5.2). If omitted, tries to infer from filename.")
    ap.add_argument("--out", default=None,
                    help="Output path (default: manifests/release-<version>.json)")
    args = ap.parse_args()

    chk = (REPO / args.checksums).resolve()
    if not chk.exists():
        print(f"[error] checksum file not found: {chk}", file=sys.stderr)
        sys.exit(1)

    # infer version
    version = args.version
    if not version:
        name = chk.name  # e.g., LATEST.sha256 or RELEASE-v3.5.2.sha256
        if name.startswith("RELEASE-") and name.endswith(".sha256"):
            version = name[len("RELEASE-"):-len(".sha256")]
        else:
            version = "latest"

    files = parse_shasum(chk)
    if not files:
        print(f"[error] no entries parsed from {chk}", file=sys.stderr)
        sys.exit(1)

    manifest = {
        "version": version,
        "source": str(chk.relative_to(REPO)),
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files": files
    }

    out = args.out
    if not out:
        out = f"manifests/release-{version}.json"
    outp = (REPO / out).resolve()
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[ok] wrote {outp.relative_to(REPO)} with {len(files)} entries")

if __name__ == "__main__":
    main()
