# src/commands/author.py
from __future__ import annotations

import os
from datetime import date
from typing import Dict, Any, Optional

import click

from ..utils.config import resolve_required, resolve_space_key
from ..confluence.client import ConfluenceClient
from ..utils.log import info, warn
from ..prompts import authoring
from ..llm.base import BaseLLM
from ..llm.openai_compat import OpenAICompatLLM
from ..llm.ollama import OllamaLLM


def _editor_edit(initial_text: str, filename_hint: str = "draft.md") -> str:
    """Open $EDITOR with initial_text; return edited text (or initial if editor was closed without save)."""
    edited = click.edit(initial_text, extension=os.path.splitext(filename_hint)[1] or ".md")
    return edited if edited is not None else initial_text


def _pick_llm_from_cfg(cfg: Dict[str, Any]) -> BaseLLM:
    """
    Read LLM settings from the profile dict returned by your load_config().
    Supports either nested table (cfg['llm']) or flat keys (cfg['llm_provider'], etc.).
    """
    # Nested table form: [<profile>.llm]
    llm = cfg.get("llm") if isinstance(cfg.get("llm"), dict) else {}

    # Flat keys fallback
    provider = (llm.get("provider") or cfg.get("llm_provider") or "").strip().lower()

    if not provider:
        raise click.UsageError(
            "No LLM configured. Use --no-llm, or add either:\n\n"
            "[<profile>.llm]\nprovider = 'ollama'\nmodel = 'mistral:latest'\nollama_base = 'http://localhost:11434'\n\n"
            "OR\n\n"
            "[<profile>.llm]\nprovider = 'openai_compat'\napi_base = 'http://localhost:8000/v1'\napi_key = '...'\nmodel = 'mistral-7b-instruct'\n\n"
            "Flat keys also supported inside the profile: llm_provider, model, ollama_base / api_base, api_key."
        )

    if provider == "ollama":
        base = (llm.get("ollama_base") or cfg.get("ollama_base") or "http://localhost:11434").strip()
        model = (llm.get("model") or cfg.get("model") or "mistral:latest").strip()
        if not model:
            raise click.UsageError("For provider=ollama, 'model' is required (e.g., 'mistral:latest').")
        return OllamaLLM(base_url=base, model=model)

    if provider == "openai_compat":
        api_base = (llm.get("api_base") or cfg.get("api_base") or "").strip()
        api_key = (llm.get("api_key") or cfg.get("api_key") or "").strip()
        model = (llm.get("model") or cfg.get("model") or "").strip()
        missing = [k for k, v in [("api_base", api_base), ("api_key", api_key), ("model", model)] if not v]
        if missing:
            raise click.UsageError(f"provider=openai_compat requires: {', '.join(missing)}")
        return OpenAICompatLLM(api_base=api_base, api_key=api_key, model=model)

    raise click.UsageError("Unknown llm.provider. Use 'openai_compat' or 'ollama'.")


@click.command(name="author")
@click.option('--space-key', envvar='CONFLUENCE_SPACE_KEY', help='Space key (overrides config default)')
@click.option('--parent-page-id', type=str, default=None, help='Optional parent page id')
@click.option('--title', default=None, help='Document title (if omitted, you will be asked)')
@click.option('--audience', default=None, help='Who is this for? e.g. SREs, backend devs, everyone')
@click.option('--purpose', default=None, help='What should readers achieve?')
@click.option('--tone', default="practical, concise", help='Style/tone to guide the model')
@click.option('--no-llm', is_flag=True, help='Skip LLM; open a blank template in $EDITOR')
@click.pass_context
def author(ctx, space_key, parent_page_id, title, audience, purpose, tone, no_llm):
    """
    Guided authoring: ask a few questions, optionally generate outline/draft via a self-hosted LLM,
    let you edit in $EDITOR, then publish to Confluence.
    """
    # Root CLI put the active profile dict in ctx.obj["config"]
    cfg: Dict[str, Any] = (ctx.obj or {}).get("config", {})

    base_url = resolve_required("base_url", None, cfg)
    pat = resolve_required("pat", None, cfg)
    space_key = resolve_space_key(space_key, cfg)

    # Gather meta
    if not title:
        title = click.prompt("Document title", type=str)
    if not audience:
        audience = click.prompt("Audience (e.g., SREs, Backend devs, Everyone)", type=str)
    if not purpose:
        purpose = click.prompt("Purpose (what should readers achieve?)", type=str)

    # Step 1: Outline
    if no_llm:
        outline_md = f"# Outline for: {title}\n\n- Section 1\n- Section 2\n- Section 3\n"
    else:
        llm = _pick_llm_from_cfg(cfg)
        sys = {"role": "system", "content": authoring.SYSTEM}
        usr = {"role": "user", "content": authoring.OUTLINE_PROMPT.format(
            title=title, audience=audience, purpose=purpose, tone=tone)}
        outline_md = llm.chat([sys, usr])
    click.echo("\n--- Outline (edit in your editor) ---")
    outline_md = _editor_edit(outline_md, filename_hint="outline.md")

    # Step 2: Draft the full doc
    if no_llm:
        full_md = f"# {title}\n\n## Introduction\n\n...\n\n## Details\n\n...\n"
    else:
        llm = _pick_llm_from_cfg(cfg)
        sys = {"role": "system", "content": authoring.SYSTEM}
        usr = {"role": "user", "content": authoring.DRAFT_PROMPT.format(
            title=title, audience=audience, purpose=purpose, tone=tone, outline=outline_md)}
        full_md = llm.chat([sys, usr])

    click.echo("\n--- Draft (edit in your editor) ---")
    full_md = _editor_edit(full_md, filename_hint="draft.md")

    # Step 3: Confirm & publish
    click.echo("\nReady to publish this Markdown to Confluence.")
    click.echo(f"Space: {space_key}")
    if parent_page_id:
        click.echo(f"Parent page id: {parent_page_id}")
    if not click.confirm("Publish now?", default=True):
        click.echo("Aborted (draft not published).")
        _save_local_draft(title, full_md)
        return

    html = _md_to_html(full_md)
    run_date = date.today()
    document_name = f"{title} - {run_date}"

    client = ConfluenceClient(base_url=base_url, pat=pat, verbose=(ctx.obj or {}).get("verbose", False))
    resp = client.create_page(
        title=document_name,
        space_key=space_key,
        body_html=html,
        parent_id=parent_page_id,
    )

    page_id = resp.get("id")
    if not page_id:
        warn(ctx, "Created but no page id returned; raw:\n" + str(resp))
    else:
        link = client.page_link(resp)
        info(ctx, f"Created page id {page_id}")
        if link:
            click.echo(f"Open: {link}")

    _save_local_draft(title, full_md)


def _md_to_html(markdown_text: str) -> str:
    """Prefer pandoc if available; otherwise use a lightweight converter."""
    import shutil
    if shutil.which("pandoc"):
        import subprocess, tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as mdfile:
            mdfile.write(markdown_text)
            mdfile.flush()
            html_tmp = mdfile.name.replace(".md", ".html")
        try:
            subprocess.run(["pandoc", mdfile.name, "-f", "markdown", "-t", "html", "-o", html_tmp], check=True)
            with open(html_tmp, "r", encoding="utf-8") as f:
                html = f.read()
        finally:
            try:
                os.remove(mdfile.name)
                os.remove(html_tmp)
            except Exception:
                pass
        return html
    else:
        import markdown
        return markdown.markdown(markdown_text, extensions=["fenced_code", "tables"])


def _save_local_draft(title: str, markdown_text: str):
    import pathlib, re
    home = pathlib.Path.home() / ".confluence-cli" / "drafts"
    home.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    path = home / f"{slug}.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(markdown_text)
    click.echo(f"Saved draft: {path}")
