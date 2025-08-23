from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
import shlex


class PandocNotFound(RuntimeError):
    pass


def _ensure_pandoc():
    if not shutil.which("pandoc"):
        raise PandocNotFound("pandoc not found on PATH. Install pandoc and retry.")


def convert_md_to_html(input_md: str | Path, html_out: str | Path, pandoc_args: str = "") -> Path:
    """Convert Markdown to HTML using pandoc. Returns output path."""
    _ensure_pandoc()
    input_md = Path(input_md)
    html_out = Path(html_out)
    args = ["pandoc", str(input_md), "-f", "gfm", "-t", "html", "-o", str(html_out)]
    if pandoc_args:
        args.extend(shlex.split(pandoc_args))
    try:
        subprocess.run(args, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"pandoc failed: {e}")
    if not html_out.exists():
        raise RuntimeError(f"Expected output not found: {html_out}")
    return html_out
