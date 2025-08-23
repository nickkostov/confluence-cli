import json
from datetime import date
from pathlib import Path

import click

from ..converters.markdown import convert_md_to_html
from ..confluence.client import ConfluenceClient
from ..utils.log import info, success, warn
from ..utils.config import resolve_required, resolve_space_key


@click.command(name="create")
@click.option('--pat', envvar='CONFLUENCE_PAT', help='Confluence Personal Access Token')
@click.option('--base-url', envvar='CONFLUENCE_BASE_URL',
              help='Base URL, e.g., https://org.atlassian.net/wiki')
@click.option('--space-key', envvar='CONFLUENCE_SPACE_KEY',
              help='Space key (overrides default_space_key from config)')
@click.option('--parent-page-id', type=int, envvar='CONFLUENCE_PARENT_ID',
              help='Optional parent page ID (omit to create at space root)')
@click.option('--page-title', required=True, help='Title prefix for the Confluence page')
@click.option('--input-md-file', type=click.Path(exists=True), required=True,
              help='Input Markdown file')
@click.option('--html-file', required=True, type=str, help='Output HTML file path')
@click.option('--pandoc-args', default='', help='Extra args passed to pandoc')
@click.option('--update-if-exists/--no-update-if-exists', default=False,
              help='Update page if same title exists under the same parent')
@click.option('--label', 'labels', multiple=True, help='Add a label (use multiple times)')
@click.option('--minor-edit/--no-minor-edit', default=False)
@click.option('--notify-watchers/--no-notify-watchers', default=True)
@click.option('--dry-run/--no-dry-run', default=False)
@click.option('--timeout', type=int, default=15)
@click.option('--retries', type=int, default=3)
@click.pass_context
def create_document(ctx, pat, base_url, space_key, parent_page_id, page_title,
                    input_md_file, html_file, pandoc_args, update_if_exists,
                    labels, minor_edit, notify_watchers, dry_run, timeout, retries):
    """Convert Markdown to HTML and create/update a Confluence page."""
    cfg = ctx.obj.get("config", {})

    base_url = resolve_required("base_url", base_url, cfg)
    space_key = resolve_space_key(space_key, cfg)
    pat = resolve_required("pat", pat, cfg)
    parent_id = parent_page_id or cfg.get("parent_page_id")  # optional

    # Convert markdown -> HTML
    info(ctx, f"Converting: {input_md_file} → {html_file} (pandoc)")
    html_out = Path(html_file)
    html_out.parent.mkdir(parents=True, exist_ok=True)
    convert_md_to_html(input_md_file, html_out, pandoc_args=pandoc_args)

    html_content = html_out.read_text(encoding='utf-8')
    run_date = date.today()
    document_name = f"{page_title} - {run_date}"
    info(ctx, f"Computed title: {document_name}")

    client = ConfluenceClient(
        base_url=base_url,
        pat=pat,
        timeout=timeout,
        retries=retries,
        verbose=ctx.obj.get("verbose", False),
    )

    result = {
        "action": None,
        "title": document_name,
        "space": space_key,
        "parent_id": str(parent_id) if parent_id else None,
        "labels": list(labels) if labels else [],
        "minor_edit": bool(minor_edit),
        "notify_watchers": bool(notify_watchers),
    }

    if dry_run:
        warn(ctx, "DRY-RUN: Skipping API calls. Would create or update page as below.")
        click.echo(json.dumps(result, indent=2))
        return

    # Create or update
    if update_if_exists:
        existing = client.find_page_by_title(document_name, space_key,
                                             parent_id=str(parent_id) if parent_id else None)
        if existing:
            result["action"] = "update"
            page_id = existing["id"]
            page_json = client.update_page(
                page_id=page_id,
                body_html=html_content,
                title=document_name,
                minor_edit=minor_edit,
                notify_watchers=notify_watchers,
            )
        else:
            result["action"] = "create"
            page_json = client.create_page(
                title=document_name,
                space_key=space_key,
                parent_id=str(parent_id) if parent_id else None,
                body_html=html_content,
                notify_watchers=notify_watchers,
            )
    else:
        result["action"] = "create"
        page_json = client.create_page(
            title=document_name,
            space_key=space_key,
            parent_id=str(parent_id) if parent_id else None,
            body_html=html_content,
            notify_watchers=notify_watchers,
        )

    # Labels
    if labels:
        try:
            client.add_labels(page_json.get("id"), list(labels))
        except Exception as e:
            warn(ctx, f"Failed to add labels: {e}")

    # Safeguard: if ID missing, show raw response
    if not page_json or "id" not in page_json:
        warn(ctx, "Response did not include an 'id'. Printing raw response for debugging:")
        click.echo(json.dumps(page_json, indent=2))
        return

    success(ctx, f"Done: {result['action']} → page id {page_json.get('id')} \n{client.page_link(page_json)}")

    if ctx.obj.get("json"):
        out = {"result": result, "page": page_json}
        click.echo(json.dumps(out, indent=2))
