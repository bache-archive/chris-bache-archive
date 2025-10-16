#!/usr/bin/env python3
"""
Generate an HTML session index for LSDMU by merging:
  - sources/transcripts/lsdmu/lsdmu.session-registry.json
  - sources/transcripts/lsdmu/lsdmu.session-dates.json

Outputs:
  - sources/transcripts/lsdmu/SESSIONS.html

Usage:
  python3 tools/generate_sessions_html.py
"""

import json
import sys
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "sources" / "transcripts" / "lsdmu"

REGISTRY_PATH = SRC_DIR / "lsdmu.session-registry.json"
DATES_PATH    = SRC_DIR / "lsdmu.session-dates.json"
OUTPUT_HTML   = SRC_DIR / "SESSIONS.html"

TOTAL_SESSIONS = 73

# Display groups (ordered)
GROUPS = [
    ("Chapter 2 — Crossing the Boundary of Birth and Death (Sessions 1–10)",      list(range(1, 11))),
    ("Chapters 4–5 — The Ocean of Suffering / Deep Time and the Soul (11–17)",    list(range(11, 18))),
    ("Chapter 6 — Initiation into the Universe (Sessions 18–24)",                 list(range(18, 25))),
    ("Chapter 7 — The Greater Real of Archetypal Reality (Sessions 25–35)",       list(range(25, 36))),
    ("Chapter 8 — A Benediction of Blessings (Sessions 36–43)",                   list(range(36, 44))),
    ("Chapter 10 — Diamond Luminosity (Sessions 44–69)",                           list(range(44, 70))),
    ("Chapter 11 — Final Vision (Sessions 70–73)",                                 list(range(70, 74))),
]

# Cross-listed sessions discussed in Chapter 9
CH9_CROSSLIST = [22, 23, 24, 28, 29, 31, 39, 43, 47, 55]


def load_json(path: Path):
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Missing file: {path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: JSON parse error in {path}: {e}", file=sys.stderr)
        sys.exit(1)


def build_session_map(registry, dates):
    """ Merge title/chapters with dates into a map {session_number: {...}} """
    reg_by_num = {r["session"]: r for r in registry}
    dates_by_num = {d["session"]: d for d in dates}

    merged = {}
    for s in range(1, TOTAL_SESSIONS + 1):
        r = reg_by_num.get(s)
        d = dates_by_num.get(s)
        if not r:
            print(f"WARNING: session {s} missing in registry", file=sys.stderr)
            r = {"session": s, "id": f"lsdmu:session:s{s:03d}", "title": None, "chapters": []}
        if not d:
            print(f"WARNING: session {s} missing in dates", file=sys.stderr)
            d = {"session": s, "date": None, "precision": "unknown"}

        merged[s] = {
            "session": s,
            "id": r.get("id", f"lsdmu:session:s{s:03d}"),
            "title": r.get("title"),
            "chapters": r.get("chapters", []),
            "date": d.get("date"),
            "precision": d.get("precision", "unknown"),
            "original_label": d.get("original_label"),
            "note": d.get("note"),
        }
    return merged


def fmt_date(entry):
    """ Human facing date respecting precision/labels. """
    date = entry["date"]
    precision = (entry["precision"] or "").lower()
    label = entry.get("original_label")

    if precision == "season" and label:
        # Show the label; keep ISO proxy silently for sort
        return f"{date}  <em>({label})</em>"
    return date or "—"


def sort_key_for_session(entry):
    """ Sort sessions within a group by ISO date if available, else by session number. """
    date = entry.get("date")
    if date:
        try:
            return (0, datetime.fromisoformat(date))
        except ValueError:
            pass
    return (1, entry["session"])


def render_html(merged):
    css = """
    <style>
      :root { color-scheme: light dark; }
      body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin: 2rem; line-height: 1.5; }
      h1 { font-size: 1.8rem; margin-bottom: 0.25rem; }
      h2 { margin-top: 2rem; font-size: 1.2rem; }
      .meta { color: #666; margin-bottom: 1.25rem; }
      table { width: 100%; border-collapse: collapse; margin-top: 0.75rem; }
      th, td { border-bottom: 1px solid #ddd; padding: 0.5rem 0.25rem; vertical-align: top; }
      th { text-align: left; font-weight: 600; }
      .sid { width: 4ch; }
      .title { width: 55%; }
      .date { width: 25%; }
      .chapters { width: 20%; color: #555; }
      code.badge { background: #f2f2f2; padding: 0.15rem 0.35rem; border-radius: 0.4rem; font-size: 0.85em; }
      .note { color: #555; font-size: 0.95em; }
    </style>
    """

    head = f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LSDMU — Session Registry (1–73)</title>
{css}
<body>
  <h1>LSDMU — Session Registry (1–73)</h1>
  <div class="meta">Author: Christopher M. Bache · Work ID: <code class="badge">lsdmu</code></div>
  <p class="note">
    Sessions are the atomic units of <em>LSD and the Mind of the Universe</em>. Dates are taken from the book’s appendix.
    Session S53 is labeled “Fall 1995”; we use a season-precision ISO proxy for sorting while preserving the label.
  </p>
"""

    parts = [head]

    # Render main chapter blocks
    for group_label, session_list in GROUPS:
        rows = [merged[s] for s in session_list if s in merged]
        rows.sort(key=sort_key_for_session)
        parts.append(f"<h2>{group_label}</h2>")
        parts.append("<table>")
        parts.append("<tr><th class='sid'>S#</th><th class='title'>Title</th><th class='date'>Date</th><th class='chapters'>Chapters</th></tr>")
        for e in rows:
            title = e["title"] if e["title"] else "—"
            date_html = fmt_date(e)
            ch = ", ".join(str(c) for c in e.get("chapters", [])) or "—"
            parts.append(f"<tr><td class='sid'>{e['session']}</td><td class='title'>{title}</td><td class='date'>{date_html}</td><td class='chapters'>{ch}</td></tr>")
        parts.append("</table>")

    # Render Chapter 9 cross-list
    parts.append("<h2>Cross-Listed in Chapter 9 — The Birth of the Future Human</h2>")
    parts.append("<p class='note'>Chapter 9 synthesizes these sessions in the Future Human arc.</p>")
    rows = [merged[s] for s in CH9_CROSSLIST if s in merged]
    rows.sort(key=lambda e: e["session"])
    parts.append("<table>")
    parts.append("<tr><th class='sid'>S#</th><th class='title'>Title</th><th class='date'>Date</th></tr>")
    for e in rows:
        title = e["title"] if e["title"] else "—"
        date_html = fmt_date(e)
        parts.append(f"<tr><td class='sid'>{e['session']}</td><td class='title'>{title}</td><td class='date'>{date_html}</td></tr>")
    parts.append("</table>")

    parts.append("</body></html>")
    return "\n".join(parts)


def main():
    registry = load_json(REGISTRY_PATH)
    dates = load_json(DATES_PATH)

    # Basic validations
    reg_nums = sorted({r["session"] for r in registry})
    date_nums = sorted({d["session"] for d in dates})

    if len(reg_nums) != TOTAL_SESSIONS:
        print(f"WARNING: registry has {len(reg_nums)} sessions; expected {TOTAL_SESSIONS}", file=sys.stderr)
    if len(date_nums) != TOTAL_SESSIONS:
        print(f"WARNING: dates file has {len(date_nums)} sessions; expected {TOTAL_SESSIONS}", file=sys.stderr)

    missing_in_dates = [n for n in reg_nums if n not in date_nums]
    missing_in_registry = [n for n in date_nums if n not in reg_nums]
    if missing_in_dates:
        print(f"WARNING: sessions missing dates: {missing_in_dates}", file=sys.stderr)
    if missing_in_registry:
        print(f"WARNING: sessions missing in registry: {missing_in_registry}", file=sys.stderr)

    merged = build_session_map(registry, dates)

    # Report blanks
    missing_titles = [s for s, e in merged.items() if not e["title"]]
    if missing_titles:
        print(f"INFO: sessions missing titles (can be filled later): {missing_titles}", file=sys.stderr)

    # Write HTML
    html = render_html(merged)
    OUTPUT_HTML.write_text(html, encoding="utf-8")
    print(f"Wrote {OUTPUT_HTML.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
