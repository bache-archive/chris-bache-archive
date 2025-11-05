# LSDMU Segmentation Registry

**Work ID:** `lsdmu` — *LSD and the Mind of the Universe: Diamonds from Heaven*  
**Author:** Christopher M. Bache  
**Source Type:** Book (Inner Traditions, 2019)

---

## Canonical ID Grammar
`lsdmu:(fm|cNN|apxNN|bm):sNN[:pNNN]`

- `fm` = front matter, `cNN` = chapter 01–12, `apxNN` = appendices, `bm` = back matter  
- `sNN` = section number (`s00` marks a continuous chapter)  
- `pNNN` (optional) = paragraph ID for future fine-grained citation  

Example:  
- Section: `lsdmu:c07:s05`  
- Paragraph: `lsdmu:c07:s05:p012`

---

## Registry vs Alignment
- **Registry** → edition-neutral, permanent (`lsdmu.section-registry.json`)  
- **Alignments** → edition-specific, flexible (`/alignments/lsdmu/*.json`)  

Never embed page numbers or timecodes in the registry IDs.

---

## Citing
Canonical: `lsdmu:c07:s05`  
With edition cue: `lsdmu:c07:s05 (Inner Traditions 2019 HC, pp. 153–156)`

---

## Copyright
This registry and its alignments include only structural metadata, no copyrighted text.
