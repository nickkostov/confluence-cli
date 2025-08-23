# src/commands/create_document.py
from __future__ import annotations

import json
import webbrowser
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
@click.option('--no-date', is_flag=True, help='Do not append " - YYYY-MM-DD" to the title')
@click.option('--input-md-file', type=click.Path(exists=True), required=True,
              help='Input Markdown file')
@click.option('--html-file', required=True, type=str, help='Output HTML file path')
@click.option('--pandoc-args', default='', help='Extra args passed to pandoc')
# New, unified duplicate handling strategy:
@click.option('--if-exists',
              type=click.Choice(['fail', 'open', 'update', 'suffix'], case_sensitive=False),
              default='fail', show_default=True,
              help='What to do when a same-title page exists under the same parent/space.')
# Back-compat flag; if used → treated like --if-exists update
@click.option('--update-if-exists/--no-update-if-exists', default=False,
              help='[DEPRECATED] Update page if same title exists (equivalent to --if-exists update)')
@click.option('--label', 'labels', multiple=True, help='Add a label (use multiple times)')
@click.option('--minor-edit/--no-minor-edit', default=False)
@click.option('--notify-watchers/--no-notify-watchers', default=True)
@click.option('--dry-run/--no-dry-run', default=False)
@click.option('--timeout', type=int, default=15)
@click.option('--retries', type=int, default=3)
@click.pass_context
def create_document(ctx, pat, base_url, space_key, parent_page_id, page_title, no_date,
                    input_md_file, html_file, pandoc_args, if_exists, update_if_exists,
                    labels, minor_edit, notify_watchers, dry_run, timeout, retries):
    """
    Convert Markdown to HTML and create/update a Confluence page — with clear, quiet handling
    when the same document already exists.
    """
    cfg = ctx.obj.get("config", {})

    base_url = resolve_required("base_url", base_url, cfg)
    space_key = resolve_space_key(space_key, cfg)
    pat = resolve_required("pat", pat, cfg)
    parent_id = parent_page_id or cfg.get("parent_page_id")  # optional

    # Back-compat: --update-if-exists overrides --if-exists if set
    if update_if_exists and (if_exists is None or if_exists == 'fail'):
        if_exists = 'update'

    # Build final title
    run_date = date.today()
    base_title = page_title if no_date else f"{page_title} - {run_date}"
    final_title = base_title

    # Convert markdown -> HTML
    info(ctx, f"Converting: {input_md_file} → {html_file} (pandoc)")
    html_out = Path(html_file)
    html_out.parent.mkdir(parents=True, exist_ok=True)
    convert_md_to_html(input_md_file, html_out, pandoc_args=pandoc_args)

    html_content = html_out.read_text(encoding='utf-8')
    info(ctx, f"Computed title: {final_title}")

    client = ConfluenceClient(
        base_url=base_url,
        pat=pat,
        timeout=timeout,
        retries=retries,
        verbose=ctx.obj.get("verbose", False),
    )

    # Dry-run summary (no API calls)
    result = {
        "action": None,
        "title": final_title,
        "space": space_key,
        "parent_id": str(parent_id) if parent_id else None,
        "labels": list(labels) if labels else [],
        "minor_edit": bool(minor_edit),
        "notify_watchers": bool(notify_watchers),
        "strategy": if_exists,
    }
    if dry_run:
        warn(ctx, "DRY-RUN: Skipping API calls. Would create or update page:")
        click.echo(json.dumps(result, indent=2))
        return

    # --- Duplicate check (quiet & clear) ---
    existing = client.find_page_by_title(
        final_title,
        space_key,
        parent_id=str(parent_id) if parent_id else None
    )

    if existing:
        # Clean, minimal message (no clutter)
        eid = existing.get("id")
        link = client.page_link(existing)
        where = f"space {space_key}" if not parent_id else f"parent {parent_id}"
        warn(ctx, f"A page with this title already exists in {where}: {final_title} [id:{eid}]")
        if link:
            click.echo(f"Open existing: {link}")

        strategy = (if_exists or "fail").lower()
        if strategy == "fail":
            raise SystemExit(2)

        if strategy == "open":
            if link:
                webbrowser.open(link)
            raise SystemExit(0)

        if strategy == "update":
            page_json = client.update_page(
                page_id=eid,
                body_html=html_content,
                title=final_title,
                minor_edit=minor_edit,
                notify_watchers=notify_watchers,
            )
            # Labels on update (best-effort)
            if labels:
                try:
                    client.add_labels(page_json.get("id"), list(labels))
                except Exception as e:
                    warn(ctx, f"Failed to add labels: {e}")

            success(ctx, f"Done: update → page id {page_json.get('id')}\n{client.page_link(page_json)}")
            if ctx.obj.get("json"):
                out = {"result": {**result, "action": "update"}, "page": page_json}
                click.echo(json.dumps(out, indent=2))
            return

        if strategy == "suffix":
            # Try Title (2..20) until free
            MAX = 20
            for i in range(2, MAX + 1):
                candidate = f"{base_title} ({i})"
                found = client.find_page_by_title(
                    candidate, space_key,
                    parent_id=str(parent_id) if parent_id else None
                )
                if found:
                    continue
                page_json = client.create_page(
                    title=candidate,
                    space_key=space_key,
                    parent_id=str(parent_id) if parent_id else None,
                    body_html=html_content,
                    notify_watchers=notify_watchers,
                )
                # Labels on create
                if labels:
                    try:
                        client.add_labels(page_json.get("id"), list(labels))
                    except Exception as e:
                        warn(ctx, f"Failed to add labels: {e}")

                success(ctx, f"Done: create → page id {page_json.get('id')}\n{client.page_link(page_json)}")
                if ctx.obj.get("json"):
                    out = {"result": {**result, "action": "create", "title": candidate}, "page": page_json}
                    click.echo(json.dumps(out, indent=2))
                return
            warn(ctx, f"Could not find a free suffix after {MAX} attempts; aborting.")
            raise SystemExit(2)

        # Shouldn’t happen (Click validates), but guard anyway
        raise SystemExit(2)

    # --- Normal create (no duplicate) ---
    page_json = client.create_page(
        title=final_title,
        space_key=space_key,
        parent_id=str(parent_id) if parent_id else None,
        body_html=html_content,
        notify_watchers=notify_watchers,
    )

    # Labels on create
    if labels:
        try:
            client.add_labels(page_json.get("id"), list(labels))
        except Exception as e:
            warn(ctx, f"Failed to add labels: {e}")

    # Safeguard: if ID missing, show raw response only if --json is set
    if not page_json or "id" not in page_json:
        warn(ctx, "Response did not include an 'id'.")
        if ctx.obj.get("json"):
            click.echo(json.dumps(page_json, indent=2))
        return

    success(ctx, f"Done: create → page id {page_json.get('id')} \n{client.page_link(page_json)}")
    if ctx.obj.get("json"):
        out = {"result": {**result, "action": "create"}, "page": page_json}
        click.echo(json.dumps(out, indent=2))
