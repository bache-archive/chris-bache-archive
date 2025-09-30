# Chris Bache Archive (2014 – 2025)

## Purpose
This archive safeguards—and makes searchable—the **public talks, interviews, and reflections of philosopher-author Christopher M. Bache** recorded between 2014 and 2025.

It now preserves three parallel layers of the record:
- **Edited transcripts** — textual record, cleaned for clarity and citation.  
- **Raw captions** — direct machine output (YouTube auto-captions).  
- **Diarized transcripts** — Otter.ai exports with automated speaker attribution.  
- **Original media** — MP4 video and MP3 audio, downloadable via script or Zenodo/Internet Archive bundles.  

The goal is to maintain an **open, structured archive** so that Chris’s voice and insights remain accessible for future generations of seekers, scholars, and technologies.

---

## Current Status (v2.1 — September 2025)
- **Transcripts:** 59 edited transcripts in `sources/`.
- **Captions:** 59 matching raw caption files in `sources/captions/`.
- **Diarist:** Otter.ai diarized `.txt` files in `sources/diarist/`.
- **Index:** `index.json` maps all entries with metadata.
- **Media:** MP4 video + MP3 audio now preserved for nearly all items.
- **Automation:** `download_media.sh` script fetches audio/video using `yt-dlp` with Chrome cookies and geo-bypass flags.
- **Archival mirrors:** Media bundles deposited to Zenodo (DOI) and Internet Archive for permanence.

---

## Folder Map

chris-bache-archive/
├── sources/              ← curated transcript sources
│   ├── transcripts/      ← human-edited transcripts (.md)
│   ├── captions/         ← raw caption files (aligned 1:1)
│   └── diarist/          ← Otter.ai diarized transcripts (.txt)
├── downloads/            ← local-only media (gitignored)
│   ├── video/            ← MP4 video files
│   └── audio/            ← MP3 audio files
├── index.json            ← metadata index
├── download_media.sh     ← automation script
└── README.md             ← this file

---

## Naming Convention
- **Format:** `YYYY-MM-DD-title-slug` (base name used for transcript, caption, audio, video, diarist).  
- Example:

2023-03-16-collective-shadow-work-and-turning-toward-our-pain.md
2023-03-16-collective-shadow-work-and-turning-toward-our-pain.txt
2023-03-16-collective-shadow-work-and-turning-toward-our-pain.mp3
2023-03-16-collective-shadow-work-and-turning-toward-our-pain.mp4

- Rules:
  - Use the original publication/recording date.  
  - Lowercase with hyphens, no spaces or punctuation.  
  - Filenames normalized (e.g., removed `prof.` period).  

---

## How to Use

### Fetch media locally
```bash
brew install jq yt-dlp
./download_media.sh

    •    Video will be saved in downloads/video/
    •    Audio will be saved in downloads/audio/

Download official media bundle
    •    Zenodo DOI: https://doi.org/10.5281/zenodo.17228650 ← replace with v2.1 DOI after publish
    •    Internet Archive: link coming soon

Each bundle includes:
    •    audio/ and video/ directories
    •    checksums.sha256 for integrity verification

⸻

Citation

If you use this archive in research or writing, please cite the Zenodo record:

bache-archive. (2025). bache-archive/chris-bache-archive: v2.1 — Media download automation & archive hygiene (v2.1) [Software]. Zenodo. https://doi.org/10.5281/zenodo.17228650

⸻

Licensing
    •    Source recordings remain © their original creators (e.g., Chris Bache, interview hosts, publishers).
    •    Curated transcripts, metadata, indexing, and scripts are dedicated to the public domain under the CC0 1.0 Universal (Public Domain Dedication).
    •    This means you may copy, modify, distribute, and use this material for any purpose, without permission or attribution.
    •    Media is mirrored here for preservation and educational use; rights-holders may request removal by emailing: bache-archive@tuta.com

⸻

Contact

Maintainer: Chris Bache Archive (pseudonymous)
📧 bache-archive@tuta.com

⸻

May these transcripts and recordings help illuminate the visions Christopher Bache has carried back for the Future Human.

