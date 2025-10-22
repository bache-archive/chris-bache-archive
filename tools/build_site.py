#!/usr/bin/env python3
from pathlib import Path
import argparse, os
import markdown

def convert_tree(src: Path, dst_root: Path, site_base: str, stylesheet: str):
    if not src.exists():
        return
    for md in src.rglob("*.md"):
        rel = md.relative_to(src)                     # keep same structure
        out_html = (dst_root / rel).with_suffix(".html")
        out_html.parent.mkdir(parents=True, exist_ok=True)
        text = md.read_text(encoding="utf-8")
        body = markdown.markdown(text, extensions=["tables", "fenced_code"])
        # Use absolute, repo-scoped stylesheet so links work at any depth
        style_href = f"{site_base.rstrip('/')}/{stylesheet.lstrip('/')}"
        html = (
            "<!doctype html><html><head>"
            f"<meta charset='utf-8'><link rel='stylesheet' href='{style_href}'>"
            "</head><body>"
            f"{body}"
            "</body></html>"
        )
        out_html.write_text(html, encoding="utf-8")
        print(f"Generated {out_html}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="build/site", help="Output dir")
    ap.add_argument("--site-base", default="/chris-bache-archive", help="Repo base path on GitHub Pages")
    ap.add_argument("--stylesheet", default="assets/style.css", help="Path to CSS within repo")
    args = ap.parse_args()

    repo = Path(__file__).resolve().parents[1]
    out  = (repo / args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    # Build both content trees
    convert_tree(repo / "docs/educational", out / "docs/educational", args.site_base, args.stylesheet)
    convert_tree(repo / "sources/transcripts", out / "sources/transcripts", args.site_base, args.stylesheet)
    convert_tree(repo / "sources/captions", out / "sources/captions", args.site_base, args.stylesheet)

    # Copy static assets you reference (so Pages can serve them)
    assets_src = repo / "assets"
    assets_dst = out / "assets"
    if assets_src.exists():
        os.system(f'rsync -a --delete "{assets_src}/" "{assets_dst}/"')

if __name__ == "__main__":
    main()
