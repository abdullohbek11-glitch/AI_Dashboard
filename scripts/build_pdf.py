"""Markdown -> PDF through headless Chrome.
usage: python3 build_pdf.py <workdir> <src.md> <dst.pdf> [<src2.md> <dst2.pdf> ...]
Needs the `markdown` package on PYTHONPATH and Google Chrome installed."""
import re
import subprocess
import sys
from pathlib import Path

import markdown

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CSS = """
@page { size: A4; margin: 20mm 16mm 18mm 16mm;
  @top-left { content: string(doctitle); font: 8pt Helvetica, Arial, sans-serif; color: #888; }
  @bottom-right { content: counter(page) " / " counter(pages); font: 8pt Helvetica, Arial, sans-serif; color: #888; } }
body { font: 10pt/1.5 -apple-system, Helvetica, Arial, sans-serif; color: #222; }
h1 { string-set: doctitle content(); font-size: 20pt; border-bottom: 3px solid #e8731a; padding-bottom: 6px; }
h2 { font-size: 14pt; margin-top: 22px; border-bottom: 1px solid #ddd; padding-bottom: 3px; }
h3 { font-size: 11.5pt; margin-top: 16px; }
code { font: 8.6pt Menlo, monospace; background: #f4f4f4; padding: 1px 3px; border-radius: 3px; }
pre { background: #f6f6f6; border-left: 3px solid #e8731a; padding: 8px 10px; white-space: pre-wrap; word-break: break-word; page-break-inside: avoid; }
pre code { background: none; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 9pt; }
th, td { border: 1px solid #ccc; padding: 4px 6px; vertical-align: top; text-align: left; }
th { background: #f0f0f0; }
tr { page-break-inside: avoid; }
blockquote { margin: 8px 0; padding: 4px 12px; border-left: 3px solid #e8731a; background: #fff7f0; color: #444; }
hr { border: 0; border-top: 1px solid #ddd; margin: 14px 0; }
"""


def build(work: Path, src: Path, dst: Path):
    text = src.read_text(encoding="utf-8")
    text = re.sub(r"([^\n])\n((?:\d+\.|[-*]) )", r"\1\n\n\2", text)  # a list needs a blank line before it
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    html = work / (dst.stem + ".html")
    html.write_text(f"<!doctype html><meta charset='utf-8'><style>{CSS}</style>{body}", encoding="utf-8")
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={dst}", html.as_uri()], check=True, capture_output=True)
    print("built", dst)


if __name__ == "__main__":
    work = Path(sys.argv[1])
    pairs = sys.argv[2:]
    for i in range(0, len(pairs), 2):
        build(work, Path(pairs[i]), Path(pairs[i + 1]))
