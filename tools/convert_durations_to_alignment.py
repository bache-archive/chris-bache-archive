#!/usr/bin/env python3
"""
Builds audiobook alignment for Chris Bache's
'LSD and the Mind of the Universe: Diamonds from Heaven'

Input: ordered list of (label, duration) from the audiobook track listing.
Output: alignments/lsdmu/audiobook-2019.json with cumulative start/end timecodes.

Notes
- We treat the provided times as DURATIONS for each listed item.
- Items that do not correspond to a canonical print 'seg_id' (e.g., Opening Credits,
  chapter headings, Foreword, Acknowledgments, End Credits) are kept with `seg_id=None`
  but retain their label for traceability.
- Canonical seg_ids follow the registry in sources/transcripts/lsdmu/lsdmu.section-registry.json
- You can safely refine seg_id mappings later without recomputing times; the times are derived from order+durations.

Run:
    python tools/build_lsdmu_audiobook_alignment.py
"""
import json
import os
from datetime import timedelta

# ---------- Helper functions ----------

def parse_hms(s: str) -> int:
    """
    Parse 'MM:SS' or 'HH:MM:SS' into total seconds (int).
    """
    parts = s.strip().split(":")
    if len(parts) == 2:
        m, sec = parts
        return int(m) * 60 + int(sec)
    elif len(parts) == 3:
        h, m, sec = parts
        return int(h) * 3600 + int(m) * 60 + int(sec)
    else:
        raise ValueError(f"Unrecognized time format: {s}")

def fmt_hms(total_seconds: int) -> str:
    """
    Format seconds into 'HH:MM:SS' (zero-padded).
    """
    td = timedelta(seconds=total_seconds)
    # timedelta's str() yields H:MM:SS by default; normalize to HH:MM:SS
    # even for durations >= 24h (not expected here)
    hours = total_seconds // 3600
    remainder = total_seconds % 3600
    minutes = remainder // 60
    seconds = remainder % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

# ---------- Source data (exact order as provided) ----------

# Each tuple is (label, duration_str)
# IMPORTANT: These are DURATIONS for each item, not absolute starts.
ITEMS = [
    ("Opening Credits", "00:17"),
    ("Note to the Reader", "00:29"),
    ("Dedication", "00:18"),
    ("Epigraph", "00:48"),
    ("Acknowledgments", "01:56"),
    ("Foreword by Ervin Laszlo", "06:18"),
    ("Introduction: 73 Days", "16:58"),

    ("Chapter One: The Path of Temporary Immersion", "01:55"),
    ("The Therapeutic Protocol", "06:39"),
    ("In a Philosopher’s Hands", "02:59"),
    ("LSD Sessions as a Path of Spiritual Awakening", "07:57"),
    ("Low-Dose vs. High-Dose Sessions", "12:59"),
    ("LSD Sessions as a Journey of Cosmic Exploration", "09:03"),
    ("Two Phases of a Session", "03:53"),
    ("The Craft of Remembering", "08:28"),
    ("Defining the Conversation", "07:23"),
    ("The Participatory Dynamics of Disclosure", "03:55"),
    ("Platforms of Experience", "10:12"),
    ("Calling Down Heaven", "04:41"),
    ("The Suffering of Death and Rebirth", "11:01"),

    ("Chapter Two: Crossing the Boundary of Birth and Death", "06:05"),
    ("The Welcoming", "09:55"),
    ("The Perinatal Domain", "13:44"),
    ("Ego-Death", "14:39"),
    ("Addendum: The Perinatal Level of Consciousness", "10:57"),

    ("Chapter Three: A Session Day", "22:47"),

    ("Chapter Four: The Ocean of Suffering", "05:58"),
    ("The Ocean of Suffering", "09:41"),
    ("The Riddle of the Ocean of Suffering", "06:51"),
    ("On the Eve of Stopping", "05:55"),

    ("Chapter Five: Deep Time and the Soul", "08:18"),
    ("My Life as a Completed Whole", "06:29"),
    ("The Great Oak and the Hillside of Karma", "05:40"),
    ("Rooted in Time", "04:20"),
    ("Reincarnation and the Soul", "09:44"),
    ("Stepping-Stones", "07:56"),
    ("Stopping My Sessions", "02:33"),
    ("Addendum: Other Instances of Future-Seeing", "15:55"),

    ("Chapter Six: Initiation into the Universe", "01:26:28"),
    ("Expanding the Narrative—Who Is the Patient?", "17:16"),
    ("Why Did the Suffering End?", "02:19"),

    ("Chapter Seven: The Greater Real of Archetypal Reality", "07:45"),
    ("Entering Archetypal Reality", "07:54"),
    ("The Living Forces of Archetypal Reality", "06:25"),
    ("The Tissue of Our Collective Being", "07:27"),
    ("A Note on the “Gods” of the Subtle Level", "03:58"),
    ("Session 28", "13:31"),
    ("The Cycle of Purification", "11:36"),
    ("Reincarnation and Collective Purification", "09:35"),
    ("A Note on Learning How to Learn in Psychedelic States", "04:21"),
    ("A Flash of “God”", "06:04"),
    ("Addendum: Plato, Jung, and Archetypes", "05:34"),

    ("Chapter Eight: A Benediction of Blessings", "58:11"),
    ("Reflections", "44:51"),

    ("Chapter Nine: The Birth of the Future Human", "12:20"),
    ("The Visions of Awakening", "23:09"),
    ("The Great Awakening", "19:16"),
    ("The Nonlinear Dynamics of Awakening", "10:42"),
    ("What Form Will the Future Human Take?", "10:38"),
    ("Another Voice: Bede Griffiths", "04:45"),

    ("Chapter Ten: Diamond Luminosity", "28:22"),
    ("The Hunger to Return", "04:12"),
    ("New Insights into the Psychedelic Process", "27:15"),
    ("Vajrayana Buddhist Practice", "14:17"),
    ("The Pivot", "19:55"),
    ("The Transparency of Embodied Presence", "16:02"),

    ("Chapter Eleven: Final Vision", "27:21"),
    ("The Good-Bye Sessions", "24:54"),
    ("Why I Stopped My Sessions", "06:24"),

    ("Chapter Twelve: Coming off the Mountain", "11:00"),
    ("The Deep Sadness", "15:45"),
    ("The Sickness of Silence", "13:36"),
    ("Entering the Sweet Valley", "06:37"),

    ("Appendix I: What Dies and Is Reborn?", "22:02"),
    ("Appendix II: Pushing the Limits of Astrological Correspondence", "02:26"),
    ("End Credits", "00:44"),
]

# ---------- Map audiobook labels -> canonical seg_ids (where possible) ----------

LABEL_TO_SEGID = {
    # Front matter (registry has: Title Page, Dedication, Epigraph, Preface, Introduction)
    # Audiobook-only items (Opening Credits, Note to the Reader, Acknowledgments, Foreword) have no seg_id.
    "Dedication": "lsdmu:fm:s02",
    "Epigraph": "lsdmu:fm:s03",
    "Introduction: 73 Days": "lsdmu:fm:s05",

    # Chapter 1
    "The Therapeutic Protocol": "lsdmu:c01:s01",
    "In a Philosopher’s Hands": "lsdmu:c01:s02",
    "LSD Sessions as a Path of Spiritual Awakening": "lsdmu:c01:s03",
    "Low-Dose vs. High-Dose Sessions": "lsdmu:c01:s04",
    "LSD Sessions as a Journey of Cosmic Exploration": "lsdmu:c01:s05",
    "Two Phases of a Session": "lsdmu:c01:s06",
    "The Craft of Remembering": "lsdmu:c01:s07",
    "Defining the Conversation": "lsdmu:c01:s08",
    "The Participatory Dynamics of Disclosure": "lsdmu:c01:s09",
    "Platforms of Experience": "lsdmu:c01:s10",
    "Calling Down Heaven": "lsdmu:c01:s11",
    "The Suffering of Death and Rebirth": "lsdmu:c01:s12",

    # Chapter 2
    "The Welcoming": "lsdmu:c02:s01",
    "The Perinatal Domain": "lsdmu:c02:s02",
    "Ego-Death": "lsdmu:c02:s03",
    "Addendum: The Perinatal Level of Consciousness": "lsdmu:c02:s04",

    # Chapter 3 (continuous)
    "Chapter Three: A Session Day": "lsdmu:c03:s00",

    # Chapter 4
    "The Ocean of Suffering": "lsdmu:c04:s01",
    "The Riddle of the Ocean of Suffering": "lsdmu:c04:s02",
    "On the Eve of Stopping": "lsdmu:c04:s03",

    # Chapter 5
    "My Life as a Completed Whole": "lsdmu:c05:s01",
    "The Great Oak and the Hillside of Karma": "lsdmu:c05:s02",
    "Rooted in Time": "lsdmu:c05:s03",
    "Reincarnation and the Soul": "lsdmu:c05:s04",
    "Stepping-Stones": "lsdmu:c05:s05",
    "Stopping My Sessions": "lsdmu:c05:s06",
    "Addendum: Other Instances of Future-Seeing": "lsdmu:c05:s07",

    # Chapter 6
    "Expanding the Narrative—Who Is the Patient?": "lsdmu:c06:s01",
    "Why Did the Suffering End?": "lsdmu:c06:s02",

    # Chapter 7
    "Entering Archetypal Reality": "lsdmu:c07:s01",
    "The Living Forces of Archetypal Reality": "lsdmu:c07:s02",
    "The Tissue of Our Collective Being": "lsdmu:c07:s03",
    "A Note on the “Gods” of the Subtle Level": "lsdmu:c07:s04",
    "Session 28": "lsdmu:c07:s05",
    "The Cycle of Purification": "lsdmu:c07:s06",
    "Reincarnation and Collective Purification": "lsdmu:c07:s07",
    "A Note on Learning How to Learn in Psychedelic States": "lsdmu:c07:s08",
    "A Flash of “God”": "lsdmu:c07:s09",
    # Audiobook-only: "Addendum: Plato, Jung, and Archetypes" (not in print registry)

    # Chapter 8
    "Reflections": "lsdmu:c08:s01",

    # Chapter 9
    "The Visions of Awakening": "lsdmu:c09:s01",
    "The Great Awakening": "lsdmu:c09:s02",
    "The Nonlinear Dynamics of Awakening": "lsdmu:c09:s03",
    "What Form Will the Future Human Take?": "lsdmu:c09:s04",
    "Another Voice: Bede Griffiths": "lsdmu:c09:s05",

    # Chapter 10
    "The Hunger to Return": "lsdmu:c10:s01",
    "New Insights into the Psychedelic Process": "lsdmu:c10:s02",
    "Vajrayana Buddhist Practice": "lsdmu:c10:s03",
    "The Pivot": "lsdmu:c10:s04",
    "The Transparency of Embodied Presence": "lsdmu:c10:s05",

    # Chapter 11
    "The Good-Bye Sessions": "lsdmu:c11:s01",
    "Why I Stopped My Sessions": "lsdmu:c11:s02",

    # Chapter 12
    "The Deep Sadness": "lsdmu:c12:s01",
    "The Sickness of Silence": "lsdmu:c12:s02",
    "Entering the Sweet Valley": "lsdmu:c12:s03",

    # Appendices
    "Appendix I: What Dies and Is Reborn?": "lsdmu:apx01:s01",
    "Appendix II: Pushing the Limits of Astrological Correspondence": "lsdmu:apx02:s01",
}

# Labels that are intentionally "auxiliary" (no seg_id in print registry)
AUXILIARY_LABELS = {
    "Opening Credits",
    "Note to the Reader",
    "Acknowledgments",
    "Foreword by Ervin Laszlo",
    "Chapter One: The Path of Temporary Immersion",
    "Chapter Two: Crossing the Boundary of Birth and Death",
    # "Chapter Three: A Session Day" is mapped to c03:s00 above (continuous chapter)
    "Chapter Four: The Ocean of Suffering",
    "Chapter Five: Deep Time and the Soul",
    "Chapter Six: Initiation into the Universe",
    "Chapter Seven: The Greater Real of Archetypal Reality",
    "Chapter Eight: A Benediction of Blessings",
    "Chapter Nine: The Birth of the Future Human",
    "Chapter Ten: Diamond Luminosity",
    "Chapter Eleven: Final Vision",
    "Chapter Twelve: Coming off the Mountain",
    "Addendum: Plato, Jung, and Archetypes",  # audiobook-only addendum
    "End Credits",
}

# ---------- Compute cumulative start/end ----------

entries = []
t = 0  # cumulative seconds
for label, duration in ITEMS:
    dur_sec = parse_hms(duration)
    start = t
    end = t + dur_sec
    t = end

    seg_id = LABEL_TO_SEGID.get(label)  # None for auxiliary labels or unmapped
    entry = {
        # Keep both the human label and seg_id (if any)
        "label": label,
        "seg_id": seg_id,
        "start": fmt_hms(start),
        "end": fmt_hms(end),
        "duration": fmt_hms(dur_sec)
    }
    if label in AUXILIARY_LABELS and seg_id is None:
        entry["auxiliary"] = True
    entries.append(entry)

# ---------- Output JSON ----------

out_dir = os.path.join("alignments", "lsdmu")
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "audiobook-2019.json")

payload = {
    "edition_id": "audiobook-2019",
    "source": "Audiobook edition, 2019 (distributed via Audible and other platforms)",
    "timecodes": entries,
    "notes": (
        "Start/end computed from ordered durations supplied by user. "
        "Items marked auxiliary=True are audiobook-only (credits, chapter headers, foreword, acknowledgments, addendum, etc.) "
        "and do not have canonical print seg_ids."
    )
}

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)

print(f"Wrote {out_path} with {len(entries)} entries. Total runtime: {fmt_hms(sum(parse_hms(d) for _, d in ITEMS))}")
