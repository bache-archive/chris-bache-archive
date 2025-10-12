#!/usr/bin/env python3
import hashlib, json, os, sys
from datetime import datetime

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MANIFESTS_DIR = os.path.join(REPO_ROOT, "manifests")
LOG_PATH = os.path.join(REPO_ROOT, "checksums", "FIXITY_LOG.md")

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def main():
    manifests = [os.path.join(MANIFESTS_DIR, p) for p in os.listdir(MANIFESTS_DIR) if p.endswith(".json")]
    if not manifests:
        print("No manifests found; run tools/build_manifests.py first.", file=sys.stderr)
        sys.exit(1)

    total = 0
    mismatches = []
    missing = []

    for mpath in sorted(manifests):
        try:
            with open(mpath, "r", encoding="utf-8") as f:
                man = json.load(f)
        except Exception as e:
            mismatches.append((mpath, f"manifest parse error: {e}"))
            continue

        for entry in man.get("files", []):
            rel = entry.get("path")
            expect = entry.get("sha256")
            if not rel or not expect:
                mismatches.append((mpath, f"bad entry: {entry}"))
                continue
            abspath = os.path.join(REPO_ROOT, rel)
            if not os.path.isfile(abspath):
                missing.append(rel)
                continue
            got = sha256_file(abspath)
            total += 1
            if got.lower() != expect.lower():
                mismatches.append((rel, f"expected {expect[:12]}..., got {got[:12]}..."))

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_PATH, "a", encoding="utf-8") as log:
        if not mismatches and not missing:
            log.write(f"{timestamp}  Verified {total} files — all hashes match.\n")
        else:
            log.write(f"{timestamp}  Verified {total} files — {len(mismatches)} mismatches, {len(missing)} missing.\n")
            if mismatches:
                log.write("  Mismatches:\n")
                for rel, msg in mismatches[:50]:
                    log.write(f"    - {rel}: {msg}\n")
                if len(mismatches) > 50:
                    log.write(f"    (+{len(mismatches)-50} more)\n")
            if missing:
                log.write("  Missing files:\n")
                for rel in missing[:50]:
                    log.write(f"    - {rel}\n")
                if len(missing) > 50:
                    log.write(f"    (+{len(missing)-50} more)\n")

    print(f"Checked {total} files. See checksums/FIXITY_LOG.md for details.")
    if mismatches or missing:
        sys.exit(2)

if __name__ == "__main__":
    main()
