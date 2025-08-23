# src/utils/render.py
from __future__ import annotations

from typing import Optional
import re

from markdownify import markdownify as html_to_md
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel


def html_to_markdown(html: str) -> str:
    """
    Convert Confluence rendered HTML to Markdown for terminal display.

    Notes:
    - Keep options simple; markdownify raises if both 'strip' and 'convert' are passed.
    - If conversion fails, fall back to a very safe HTML tag stripper that preserves
      basic line breaks for common block elements.
    """
    try:
        md = html_to_md(
            html,
            heading_style="ATX",
            code_language_detection=True,
            bullets="*",
        )
        return md.strip()
    except Exception:
        # Safe fallback: remove tags, keep basic structure via line breaks
        text = re.sub(r"(?i)</(p|div|h[1-6]|li|br|tr)>", "\n", html)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        return text


def render_markdown_paged(markdown_text: str, title: Optional[str] = None) -> None:
    """
    Page the Markdown content in the terminal with a header panel.
    Uses Rich's pager so long docs are scrollable.
    """
    console = Console()
    with console.pager(styles=True):
        if title:
            console.print(Panel.fit(f"[bold]{title}[/bold]"))
        console.print(Markdown(markdown_text, code_theme="monokai"))
