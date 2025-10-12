#!/usr/bin/env python3
import hashlib, json, os, re, sys
from datetime import date

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RELEASE = os.environ.get("RELEASE", "v2.4")
CHECKSUMS_PATH = os.path.join(REPO_ROOT, "checksums", f"RELEASE-{RELEASE}.sha256")
MANIFESTS_DIR = os.path.join(REPO_ROOT, "manifests")
TOOLS_CFG = os.path.join(REPO_ROOT, "tools", "tool_versions.json")

INCLUDE_DIRS = ["sources", "downloads"]  # extend later if needed

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def guess_id_from_path(relpath):
    # Prefer a stable, date-led slug (YYYY-MM-DD-... without extension)
    base = os.path.basename(relpath)
    stem, _ = os.path.splitext(base)
    # If it starts with a date, keep the whole stem (common naming in this repo)
    if re.match(r"^\d{4}-\d{2}-\d{2}", stem):
        return stem
    # Otherwise fall back to directory + stem
    parts = relpath.split(os.sep)
    if len(parts) >= 2:
        return f"{parts[-2]}-{stem}"
    return stem

def extract_recorded_date(id_):
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", id_)
    return m.group(1) if m else ""

def load_tools():
    try:
        with open(TOOLS_CFG, "r") as f:
            cfg = json.load(f)
        return [f"{k} {v}" for k, v in cfg.items()]
    except Exception:
        return []

def main():
    files = []
    for root_dir in INCLUDE_DIRS:
        abs_root = os.path.join(REPO_ROOT, root_dir)
        if not os.path.isdir(abs_root):
            continue
        for r, _dirs, fns in os.walk(abs_root):
            # skip generated & meta dirs
            if any(skip in r for skip in (os.sep+".git", os.sep+"manifests", os.sep+"checksums", os.sep+"tools")):
                continue
            for fn in fns:
                # skip obvious non-content files
                if fn.startswith("."):
                    continue
                relpath = os.path.relpath(os.path.join(r, fn), REPO_ROOT)
                # ignore index pages and repo docs here
                if relpath.startswith(("README.md","index.html","index.md","LICENSE")):
                    continue
                files.append(relpath)

    if not files:
        print("No source/download files found. Populate sources/ and downloads/ first.", file=sys.stderr)
        sys.exit(1)

    # Compute hashes and group by id
    groups = {}
    release_lines = []
    for rel in sorted(files):
        abspath = os.path.join(REPO_ROOT, rel)
        if not os.path.isfile(abspath):
            continue
        digest = sha256_file(abspath)
        release_lines.append(f"{digest}  {rel}")
        id_ = guess_id_from_path(rel)
        groups.setdefault(id_, {"id": id_, "files": []})
        groups[id_]["files"].append({"path": rel, "sha256": digest})

    tools_list = load_tools()
    captured = date.today().isoformat()

    # Write per-item manifests
    os.makedirs(MANIFESTS_DIR, exist_ok=True)
    for id_, obj in groups.items():
        obj["captured_at"] = captured
        obj["license"] = "CC0-1.0"
        obj["recorded_date"] = extract_recorded_date(id_)
        if tools_list:
            obj["tools"] = tools_list
        manifest_path = os.path.join(MANIFESTS_DIR, f"{id_}.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)

    # Write/overwrite release checksum file
    os.makedirs(os.path.dirname(CHECKSUMS_PATH), exist_ok=True)
    with open(CHECKSUMS_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(release_lines) + ("\n" if release_lines else ""))

    print(f"Manifests written: {len(groups)}")
    print(f"Release checksum: checksums/RELEASE-{RELEASE}.sha256 ({len(release_lines)} files)")

if __name__ == "__main__":
    main()
