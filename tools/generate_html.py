#!/usr/bin/env python3
from pathlib import Path
import markdown

root = Path("sources/transcripts")
style = '<link rel="stylesheet" href="../../assets/style.css">'

for md_file in root.rglob("*.md"):
    html_file = md_file.with_suffix(".html")
    text = md_file.read_text(encoding="utf-8")
    body = markdown.markdown(text, extensions=["tables", "fenced_code"])
    html = f"<!doctype html><html><head>{style}<meta charset='utf-8'></head><body>{body}</body></html>"
    html_file.write_text(html, encoding="utf-8")
    print(f"Generated {html_file}")
