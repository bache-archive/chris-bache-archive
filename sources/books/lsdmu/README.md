# LSDMU Segmentation Registry

**Work ID:** `lsdmu` — *LSD and the Mind of the Universe: Diamonds from Heaven*  
**Author:** Christopher M. Bache  
**Source Type:** Book (Inner Traditions, 2019)

---

## Canonical ID Grammar
`lsdmu:(fm|cNN|apxNN|bm):sNN[:pNNN]`

- `fm` = front matter  
- `cNN` = chapter (01–12)  
- `apxNN` = appendices  
- `bm` = back matter  
- `sNN` = section number within that chapter or division  
  - `s00` → **headnote or opening passage** for the chapter (unnamed text preceding the first titled section)  
  - `s01+` → sequential, titled sections  
- `pNNN` (optional) = paragraph identifier for fine-grained citation or future alignment work

Example:  
- Section: `lsdmu:c07:s05`  
- Paragraph: `lsdmu:c07:s05:p012`

---

## Headnotes
Each major chapter (except Chapter 3) contains an introductory or “lead-in” passage before the first titled section.  
These are represented as distinct structural segments:

```json
{
  "seg_id": "lsdmu:c05:s00",
  "chapter": 5,
  "section": 0,
  "title": "",
  "role": "headnote",
  "ui_label": "Opening"
}

The "title" field remains blank because the printed book provides no explicit heading.
This preserves structural fidelity while enabling display systems to mark or style these as “Opening” sections.

⸻

Registry vs Alignment
	•	Registry → edition-neutral, permanent (lsdmu/section-registry.json)
	•	Alignments → edition-specific, flexible (alignments/lsdmu/*.json)

Never embed page numbers, timecodes, or other edition-dependent metadata in the registry itself.

⸻

Citing

Canonical form:

lsdmu:c07:s05

With edition cue:

lsdmu:c07:s05 (Inner Traditions 2019 HC, pp. 153–156)


⸻

Copyright

This registry and its alignments contain structural metadata only—no copyrighted text or derivative content.
