#!/usr/bin/env python3
import argparse
import os
import sys
import internetarchive

AUDIO_ID = "chris-bache-archive-audio"
VIDEO_ID = "chris-bache-archive-video"

AUDIO_META = {
    "title": "Chris Bache Archive — Audio (2009–2025)",
    "creator": "Christopher M. Bache",
    "description": ("Complete MP3 audio recordings preserved for the Chris Bache Archive. "
                    "Transcripts and metadata are maintained in versioned releases at GitHub and Zenodo."),
    "subject": "psychedelics; consciousness; LSD; reincarnation; philosophy; archive",
    "licenseurl": "http://creativecommons.org/publicdomain/zero/1.0/",
    "collection": "opensource_audio",
    "mediatype": "audio",
}
VIDEO_META = {
    "title": "Chris Bache Archive — Video (2009–2025)",
    "creator": "Christopher M. Bache",
    "description": ("Complete MP4 video recordings preserved for the Chris Bache Archive. "
                    "Transcripts and metadata are maintained in versioned releases at GitHub and Zenodo."),
    "subject": "psychedelics; consciousness; LSD; reincarnation; philosophy; archive",
    "licenseurl": "http://creativecommons.org/publicdomain/zero/1.0/",
    "collection": "opensource_movies",
    "mediatype": "movies",
}

def get_args():
    p = argparse.ArgumentParser(description="Sync local media to Internet Archive (resume-safe, with retries).")
    p.add_argument("--mode", choices=["audio", "video"], required=True,
                   help="Which media set to upload (controls identifier, mediatype, and collection).")
    p.add_argument("--dir", required=True, help="Local directory containing the media files.")
    p.add_argument("--derive", action="store_true",
                   help="After upload, trigger derivation to build web players.")
    p.add_argument("--retries", type=int, default=20, help="Retry attempts for failed parts/requests.")
    return p.parse_args()

def choose_ext_and_meta(mode):
    if mode == "audio":
        return (".mp3", AUDIO_ID, AUDIO_META)
    else:
        return (".mp4", VIDEO_ID, VIDEO_META)

def list_remote_filenames(identifier, ext):
    item = internetarchive.get_item(identifier)
    remote = set()
    try:
        for f in item.files or []:
            name = f.get("name") or ""
            if name.lower().endswith(ext):
                remote.add(os.path.basename(name))
    except Exception:
        remote = set()
    return remote

def list_local_filenames(folder, ext):
    return set(f for f in os.listdir(folder)
               if f.lower().endswith(ext) and os.path.isfile(os.path.join(folder, f)))

def trigger_derivation(identifier):
    item = internetarchive.get_item(identifier)
    desc = (item.metadata or {}).get("description", "")
    nudged = (desc + " ").rstrip()
    item.modify_metadata({"description": nudged})

def main():
    args = get_args()
    ext, identifier, meta = choose_ext_and_meta(args.mode)

    folder = os.path.abspath(args.dir)
    if not os.path.isdir(folder):
        print(f"✖ Not a directory: {folder}", file=sys.stderr)
        sys.exit(1)

    local = list_local_filenames(folder, ext)
    if not local:
        print(f"✖ No *{ext} files found in {folder}", file=sys.stderr)
        sys.exit(1)

    print(f"→ Target item: {identifier}")
    print(f"→ Scanning Internet Archive for existing {ext} files…")
    remote = list_remote_filenames(identifier, ext)
    missing = sorted(local - remote)

    if not missing:
        print("✅ All local files are already present on Internet Archive.")
        if args.derive:
            print("→ Triggering derivation (players)…")
            trigger_derivation(identifier)
            print("✓ Derivation nudged.")
        return

    print(f"→ Found {len(missing)} missing file(s). Uploading with retries={args.retries}…")
    file_paths = [os.path.join(folder, f) for f in missing]

    results = internetarchive.upload(
        identifier,
        file_paths,
        metadata=meta,
        retries=args.retries,
        queue_derive=False
    )

    ok, fail = 0, 0
    for item in results:
        resp, path = None, None
        if isinstance(item, tuple):
            if len(item) == 2:
                resp, path = item
            elif len(item) == 1:
                resp = item[0]
        else:
            resp = item

        if resp is not None and hasattr(resp, "status_code"):
            status = resp.status_code
            if 200 <= status < 300:
                name = os.path.basename(path) if path else "(unknown)"
                print(f"✅ Uploaded: {name}")
                ok += 1
            else:
                name = os.path.basename(path) if path else "(unknown)"
                print(f"⚠️ Failed:   {name} (HTTP {status})")
                fail += 1
        else:
            print(f"⚠️ Unexpected upload result: {item}")

    remote_after = list_remote_filenames(identifier, ext)
    still_missing = sorted(local - remote_after)
    if still_missing:
        print(f"\n⚠️ Still missing {len(still_missing)} file(s):")
        for f in still_missing:
            print(f"  - {f}")
    else:
        print("\n🎉 Sync complete: local and remote match.")

    if args.derive and not still_missing:
        print("→ Triggering derivation (players)…")
        trigger_derivation(identifier)
        print("✓ Derivation nudged.")

if __name__ == "__main__":
    main()