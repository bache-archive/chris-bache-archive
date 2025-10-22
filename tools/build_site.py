#!/usr/bin/env python3
"""
tools/build_site.py  –  Build static HTML pages directly alongside Markdown sources
so GitHub Pages can serve URLs like:
  https://bache-archive.github.io/chris-bache-archive/docs/educational/<qid>/index.html
"""

from pathlib import Path
import argparse, os, markdown

def convert_tree(src: Path, site_base: str, stylesheet: str):
    """Convert every .md file under src/ into an adjacent .html file."""
    if not src.exists():
        return
    for md in src.rglob("*.md"):
        rel = md.relative_to(src)
        out_html = (src / rel).with_suffix(".html")
        out_html.parent.mkdir(parents=True, exist_ok=True)

        text = md.read_text(encoding="utf-8")
        body = markdown.markdown(text, extensions=["tables", "fenced_code"])

        # Use repo-relative stylesheet path so CSS loads correctly on Pages
        style_href = f"{site_base.rstrip('/')}/{stylesheet.lstrip('/')}"
        html = (
            "<!doctype html><html><head>"
            "<meta charset='utf-8'>"
            f"<link rel='stylesheet' href='{style_href}'>"
            "</head><body>"
            f"{body}"
            "</body></html>"
        )

        out_html.write_text(html, encoding="utf-8")
        print(f"[ok] Generated {out_html}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site-base", default="/chris-bache-archive",
                    help="Base path for GitHub Pages (used in stylesheet links)")
    ap.add_argument("--stylesheet", default="assets/style.css",
                    help="Path to CSS within repo")
    args = ap.parse_args()

    repo = Path(__file__).resolve().parents[1]

    # Convert Markdown in place for these content trees
    convert_tree(repo / "docs" / "educational", args.site_base, args.stylesheet)
    convert_tree(repo / "sources" / "transcripts", args.site_base, args.stylesheet)
    convert_tree(repo / "sources" / "captions", args.site_base, args.stylesheet)

    # Copy static assets (so Pages can serve them)
    assets_src = repo / "assets"
    if assets_src.exists():
        os.system(f'rsync -a --delete "{assets_src}/" "{assets_src}/"')

if __name__ == "__main__":
    main()