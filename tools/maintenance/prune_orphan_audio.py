#!/usr/bin/env python3
"""
Prune orphan .mp3 files in downloads/audio/ that are not referenced by index.json.

Rules:
- Keep anything that appears in any item's media.audio.
- Also keep the canonical slug path downloads/audio/<slug>.mp3 for any item with a slug.
- Never touch downloads/audio/_slugalias/ or any subdirs.
- Dry-run by default. Use --apply to actually delete.
- Optional: --move-to PATH to move orphans into a quarantine folder instead of deleting.
- Optional: --git to remove with `git rm` when files are tracked (falls back to unlink if not).

Usage:
  python3 tools/maintenance/prune_orphan_audio.py            # dry-run
  python3 tools/maintenance/prune_orphan_audio.py --apply    # delete
  python3 tools/maintenance/prune_orphan_audio.py --apply --move-to backups/orphan-audio-YYYYmmdd
  python3 tools/maintenance/prune_orphan_audio.py --apply --git
"""
import argparse, json, os, shutil, subprocess, sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "index.json"
AUDIO_DIR = ROOT / "downloads" / "audio"
ALIAS_DIR = AUDIO_DIR / "_slugalias"

def is_git_tracked(p: Path) -> bool:
    try:
        subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(p.relative_to(ROOT))],
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
        )
        return True
    except subprocess.CalledProcessError:
        return False

def git_rm(p: Path):
    subprocess.run(["git", "rm", "-f", str(p.relative_to(ROOT))], cwd=ROOT, check=False)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Perform deletions/moves (otherwise dry-run)")
    ap.add_argument("--move-to", type=str, default="", help="Quarantine directory to move orphans into instead of delete")
    ap.add_argument("--git", action="store_true", help="Use `git rm` for tracked files")
    args = ap.parse_args()

    if not INDEX.exists():
        print(f"ERROR: {INDEX} not found", file=sys.stderr); sys.exit(2)
    if not AUDIO_DIR.exists():
        print(f"ERROR: {AUDIO_DIR} not found", file=sys.stderr); sys.exit(2)

    try:
        data = json.loads(INDEX.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"ERROR: cannot read index.json: {e}", file=sys.stderr); sys.exit(2)
    if not isinstance(data, list):
        print("ERROR: index.json must be a top-level array", file=sys.stderr); sys.exit(2)

    # Build allowlist
    allowed = set()
    for item in data:
        if not isinstance(item, dict): continue
        slug = item.get("slug")
        media = item.get("media") or {}
        audio = media.get("audio")
        if slug:
            allowed.add((AUDIO_DIR / f"{slug}.mp3").resolve())
        if audio:
            p = (ROOT / audio).resolve() if not os.path.isabs(audio) else Path(audio).resolve()
            allowed.add(p)

    # Collect candidate .mp3 files under downloads/audio (top-level only)
    candidates = []
    for p in AUDIO_DIR.glob("*.mp3"):
        if p.resolve() == (ALIAS_DIR / p.name).resolve():
            # Not relevant, but guard anyway
            continue
        candidates.append(p.resolve())

    # Determine orphans
    orphans = sorted(p for p in candidates if p not in allowed)

    print(f"Audio files found (top-level): {len(candidates)}")
    print(f"Referenced/whitelisted: {len(candidates) - len(orphans)}")
    print(f"Orphans (eligible for removal): {len(orphans)}")

    for p in orphans[:50]:
        print(f"  ORPHAN: {p.relative_to(ROOT)}")
    if len(orphans) > 50:
        print(f"  ... (+{len(orphans) - 50} more)")

    if not args.apply:
        print("\nDry-run only. Re-run with --apply to remove/move orphans.")
        return

    # Prepare quarantine dir if requested
    move_to = None
    if args.move_to:
        move_to = (ROOT / args.move_to).resolve()
        move_to.mkdir(parents=True, exist_ok=True)
        print(f"\nQuarantine: {move_to.relative_to(ROOT)}")

    removed, moved = 0, 0
    for p in orphans:
        try:
            if move_to:
                dest = move_to / p.name
                # Avoid overwrite: add suffix if necessary
                i = 1
                while dest.exists():
                    dest = move_to / f"{p.stem}__{i}{p.suffix}"
                    i += 1
                shutil.move(str(p), str(dest))
                moved += 1
            else:
                if args.git and is_git_tracked(p):
                    git_rm(p)
                else:
                    p.unlink(missing_ok=True)
                removed += 1
        except Exception as e:
            print(f"ERROR removing {p}: {e}", file=sys.stderr)

    if move_to:
        print(f"\nDONE: moved {moved} orphan files to {move_to.relative_to(ROOT)}")
    else:
        print(f"\nDONE: removed {removed} orphan files")

if __name__ == "__main__":
    main()
