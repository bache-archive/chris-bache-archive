#!/usr/bin/env python3
import argparse, json, os, shutil, sys, hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] if __file__ else Path(".")
INDEX = ROOT/"index.json"
AUDIO_DIR = ROOT/"downloads"/"audio"

def sha256(path, block=1024*1024):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(block)
            if not b: break
            h.update(b)
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser(description="Normalize audio file names to slug-based mp3 paths and update index.json")
    ap.add_argument("--apply", action="store_true", help="Perform file moves and write index.json (otherwise dry-run)")
    ap.add_argument("--hash-check", action="store_true", help="If both src and dest exist, only replace dest if identical by SHA256; otherwise skip")
    args = ap.parse_args()

    if not INDEX.exists():
        print(f"ERROR: {INDEX} not found", file=sys.stderr); sys.exit(2)
    if not AUDIO_DIR.exists():
        print(f"ERROR: {AUDIO_DIR} not found", file=sys.stderr); sys.exit(2)

    data = json.loads(INDEX.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        print("ERROR: index.json is not a top-level array", file=sys.stderr); sys.exit(2)

    planned_moves = []
    fixes_only = 0
    conflicts = []
    missing_src = []
    changed_records = 0

    # Collect desired destinations to detect multiple items mapping to same slug
    slug_to_items = {}
    for i, item in enumerate(data):
        if not isinstance(item, dict): continue
        slug = item.get("slug")
        media = item.get("media") or {}
        audio = media.get("audio")
        if not slug: continue
        dest = AUDIO_DIR/f"{slug}.mp3"
        slug_to_items.setdefault(slug, []).append(i)

    # Flag slugs that appear multiple times
    dup_slugs = [s for s, idxs in slug_to_items.items() if len(idxs)>1]
    if dup_slugs:
        print("WARNING: Duplicate slugs detected (these items share the same target file and will be skipped):")
        for s in dup_slugs:
            print(f"  - {s}  (items: {slug_to_items[s]})")
        print()

    for i, item in enumerate(data):
        if not isinstance(item, dict): continue
        slug = item.get("slug")
        media = item.get("media") or {}
        audio = media.get("audio")
        if not slug: continue
        dest = AUDIO_DIR/f"{slug}.mp3"

        # Skip items with duplicate slug to avoid clobbering
        if slug in dup_slugs:
            continue

        if audio is None:
            # no audio path declared; just point to canonical (doesn't create file)
            media["audio"] = str(dest.as_posix())
            item["media"] = media
            changed_records += 1
            continue

        src = ROOT/audio if isinstance(audio := Path(audio), str) else (ROOT/audio if not Path(audio).is_absolute() else Path(audio))
        # Normalize relative path
        if not src.is_absolute():
            src = (ROOT/Path(audio)).resolve()
        # Canonical dest
        dest = dest.resolve()

        # Already correct?
        if Path(media["audio"]) == Path(dest.relative_to(ROOT)).as_posix() or Path(media["audio"]) == dest:
            # Ensure file exists; if not, we just keep the pointer (might be added later)
            continue

        # If src equals dest (string-wise different but same location), just set pointer
        if src == dest:
            media["audio"] = str(dest.relative_to(ROOT).as_posix())
            item["media"] = media
            changed_records += 1
            continue

        # If src missing but dest exists, just repoint
        if (not src.exists()) and dest.exists():
            media["audio"] = str(dest.relative_to(ROOT).as_posix())
            item["media"] = media
            changed_records += 1
            continue

        # If src missing and dest missing -> record missing
        if not src.exists():
            missing_src.append((i, slug, str(src)))
            # Still repoint to canonical so later downloads land in the right place
            media["audio"] = str(dest.relative_to(ROOT).as_posix())
            item["media"] = media
            changed_records += 1
            continue

        # If dest exists already
        if dest.exists():
            if args.hash_check:
                try:
                    h_src = sha256(src)
                    h_dst = sha256(dest)
                except Exception as e:
                    conflicts.append((i, slug, str(src), str(dest), f"hash_error:{e}"))
                    continue
                if h_src == h_dst:
                    # Same content; we can delete src and keep dest
                    if args.apply:
                        try:
                            src.unlink()
                        except Exception as e:
                            conflicts.append((i, slug, str(src), str(dest), f"unlink_error:{e}"))
                            continue
                    media["audio"] = str(dest.relative_to(ROOT).as_posix())
                    item["media"] = media
                    changed_records += 1
                else:
                    conflicts.append((i, slug, str(src), str(dest), "content_differs"))
            else:
                # Don’t overwrite; treat as conflict
                conflicts.append((i, slug, str(src), str(dest), "dest_exists"))
            continue

        # Plan a move (src → dest)
        planned_moves.append((i, slug, src, dest))

    # Report plan
    print(f"Planned file moves: {len(planned_moves)}")
    for _, slug, src, dest in planned_moves[:25]:
        print(f"  mv {src}  ->  {dest}")
    if len(planned_moves) > 25:
        print(f"  ... (+{len(planned_moves)-25} more)")

    if missing_src:
        print(f"\nMissing source files referenced in index.json: {len(missing_src)}")
        for i, slug, src in missing_src[:25]:
            print(f"  [{i}] slug={slug}  src={src}")
        if len(missing_src) > 25:
            print(f"  ... (+{len(missing_src)-25} more)")

    if conflicts:
        print(f"\nConflicts (skipped): {len(conflicts)}")
        for i, slug, src, dest, reason in conflicts[:25]:
            print(f"  [{i}] slug={slug}  src={src}  dest={dest}  reason={reason}")
        if len(conflicts) > 25:
            print(f"  ... (+{len(conflicts)-25} more)")

    # Apply?
    if args.apply:
        # Ensure destination parent exists
        AUDIO_DIR.mkdir(parents=True, exist_ok=True)

        # Move files
        for _, slug, src, dest in planned_moves:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))

        # Update all media.audio to canonical relative path
        for item in data:
            if not isinstance(item, dict): continue
            slug = item.get("slug")
            if not slug: continue
            media = item.get("media") or {}
            media["audio"] = f"downloads/audio/{slug}.mp3"
            item["media"] = media

        # Backup and write index.json
        backup = INDEX.with_suffix(".json.bak")
        shutil.copy2(INDEX, backup)
        INDEX.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\nAPPLIED: moved {len(planned_moves)} files, updated index.json, backup at {backup}")
    else:
        print("\nDry-run only. Re-run with --apply to perform moves and rewrite index.json.")

if __name__ == "__main__":
    main()
