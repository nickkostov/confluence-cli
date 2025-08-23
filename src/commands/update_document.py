import json
from pathlib import Path

import click

from ..converters.markdown import convert_md_to_html
from ..confluence.client import ConfluenceClient
from ..utils.log import info, success, warn
from ..utils.config import resolve_required, resolve_space_key


@click.command(name="update")
@click.option('--pat', envvar='CONFLUENCE_PAT', help='Confluence PAT')
@click.option('--base-url', envvar='CONFLUENCE_BASE_URL', help='Base URL (e.g., https://org.atlassian.net/wiki)')
@click.option('--page-id', help='Page ID to update (skip title resolution if provided)')
@click.option('--space-key', envvar='CONFLUENCE_SPACE_KEY',
              help='Space key (used when resolving by title; overrides default_space_key from config)')
@click.option('--title', help='Title to resolve (requires space key; parent optional to disambiguate)')
@click.option('--parent-page-id', envvar='CONFLUENCE_PARENT_ID', type=int,
              help='Optional parent to disambiguate title when multiple matches exist')
@click.option('--input-md-file', type=click.Path(exists=True), required=True, help='Input Markdown file')
@click.option('--html-file', required=True, type=str, help='Output HTML file path (generated before upload)')
@click.option('--pandoc-args', default='', help='Extra args passed to pandoc')
@click.option('--minor-edit/--no-minor-edit', default=True, help='Mark update as minor edit')
@click.option('--notify-watchers/--no-notify-watchers', default=True, help='Notify watchers on update')
@click.option('--dry-run/--no-dry-run', default=False)
@click.option('--timeout', type=int, default=15)
@click.option('--retries', type=int, default=3)
@click.pass_context
def update_document(ctx, pat, base_url, page_id, space_key, title, parent_page_id,
                    input_md_file, html_file, pandoc_args, minor_edit, notify_watchers,
                    dry_run, timeout, retries):
    """Update an existing Confluence page (by id, or resolve by title/space with optional parent)."""
    cfg = ctx.obj.get("config", {})

    base_url = resolve_required("base_url", base_url, cfg)
    pat = resolve_required("pat", pat, cfg)

    client = ConfluenceClient(
        base_url=base_url,
        pat=pat,
        timeout=timeout,
        retries=retries,
        verbose=ctx.obj.get("verbose", False),
    )

    # Resolve page id if not provided
    if not page_id:
        title = resolve_required("title", title, {})
        space_key = resolve_space_key(space_key, cfg)  # prefer explicit, else default from config
        parent_filter = str(parent_page_id) if parent_page_id else None
        found = client.find_page_by_title(title, space_key, parent_id=parent_filter)
        if not found:
            raise click.UsageError("Page not found by title/space/parent criteria")
        page_id = found["id"]

    info(ctx, f"Updating page {page_id}")

    if dry_run:
        warn(ctx, "DRY-RUN: Skipping conversion and API call")
        preview = {
            "action": "update",
            "page_id": page_id,
            "minor_edit": bool(minor_edit),
            "notify_watchers": bool(notify_watchers),
            "from_md": str(input_md_file),
            "to_html": str(html_file),
        }
        click.echo(json.dumps(preview, indent=2))
        return

    # Convert Markdown → HTML
    out_path = Path(html_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    convert_md_to_html(input_md_file, out_path, pandoc_args=pandoc_args)
    html_content = out_path.read_text(encoding='utf-8')

    # Perform update
    page_json = client.update_page(
        page_id=page_id,
        body_html=html_content,
        minor_edit=minor_edit,
        notify_watchers=notify_watchers,
    )

    success(ctx, f"Updated page id {page_json.get('id')} → {client.page_link(page_json)}")

    if ctx.obj.get("json"):
        click.echo(json.dumps(page_json, indent=2))
