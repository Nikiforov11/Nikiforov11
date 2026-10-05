"""Export a conversation as one self-contained HTML file: questions,
answers, interactive charts and the tool calls behind each answer.
Open it in any browser or send it to someone."""
from __future__ import annotations

import html
import json
import re
from datetime import datetime

from data_layer.store import Request
from tools.charts import build_figure

STYLE = """
body { font-family: 'IBM Plex Sans', system-ui, sans-serif; color: #1D2B24; background: #FBFCFA;
       max-width: 860px; margin: 2.5rem auto; padding: 0 1.25rem; line-height: 1.55; }
h1, h2 { font-family: 'IBM Plex Serif', Georgia, serif; font-weight: 600; }
h1 { font-size: 1.9rem; margin-bottom: .2rem; }
h2 { font-size: 1.2rem; margin: 2.4rem 0 .6rem; padding-top: 1.2rem; border-top: 1px solid #D5DED8; }
.meta { color: #5B6B62; font-size: .9rem; }
.answer { font-size: 1rem; }
details { margin-top: .8rem; color: #5B6B62; font-size: .88rem; }
pre { background: #EEF3EF; padding: .6rem; overflow-x: auto; font-size: .8rem; }
.error { color: #9B2C2C; }
"""


def markdown_to_html(text: str) -> str:
    """Just enough Markdown for model answers: paragraphs, bullets, bold, italics."""
    blocks, items = [], []
    for line in html.escape(text).splitlines():
        line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
        line = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<em>\1</em>", line)
        bullet = re.match(r"^\s*[-*•]\s+(.*)", line)
        if bullet:
            items.append(f"<li>{bullet.group(1)}</li>")
            continue
        if items:
            blocks.append("<ul>" + "".join(items) + "</ul>")
            items = []
        if line.strip():
            blocks.append(f"<p>{line}</p>")
    if items:
        blocks.append("<ul>" + "".join(items) + "</ul>")
    return "\n".join(blocks)


def build_report(requests: list[Request], dataset_name: str, title: str = "Sales analysis") -> str:
    parts = [f"<h1>{html.escape(title)}</h1>",
             f"<p class='meta'>Dataset: {html.escape(dataset_name)}. "
             f"Exported {datetime.now():%Y-%m-%d %H:%M}.</p>"]
    first_chart = True
    for r in requests:
        parts.append(f"<h2>{html.escape(r.question)}</h2>")
        if r.status != "done" or not r.result:
            parts.append(f"<p class='error'>No answer ({html.escape(r.status)}).</p>")
            continue
        parts.append(f"<div class='answer'>{markdown_to_html(r.result['answer'])}</div>")
        for chart in r.result.get("charts", []):
            parts.append(build_figure(chart).to_html(
                full_html=False, include_plotlyjs="cdn" if first_chart else False))
            first_chart = False
        calls = r.result.get("tool_calls", [])
        if calls:
            listing = "\n".join(f"{c['name']}({json.dumps(c['args'], ensure_ascii=False)})"
                                + ("" if c["ok"] else f"  -> error: {c['error']}") for c in calls)
            parts.append(f"<details><summary>How this was calculated</summary>"
                         f"<pre>{html.escape(listing)}</pre></details>")
    body = "\n".join(parts)
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width, initial-scale=1'>"
            f"<title>{html.escape(title)}</title>"
            f"<link href='https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&"
            f"family=IBM+Plex+Serif:wght@600&display=swap' rel='stylesheet'>"
            f"<style>{STYLE}</style></head><body>{body}</body></html>")
