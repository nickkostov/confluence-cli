# src/commands/browse.py
from __future__ import annotations

import webbrowser
from typing import Optional, List, Dict, Any

import click

from ..confluence.client import ConfluenceClient
from ..utils.config import resolve_required, resolve_space_key
from ..utils.log import info, warn
from ..utils.render import html_to_markdown, render_markdown_paged

# --- prompt_toolkit for interactive mode ---
from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import TextArea, Frame
from prompt_toolkit.shortcuts import input_dialog


@click.group(name="browse")
def browse_group():
    """Browse Confluence pages: list, search, children, open, tree, view, interactive."""
    pass


# ---------------- non-interactive commands ----------------

@browse_group.command(name="list")
@click.option('--space-key', envvar='CONFLUENCE_SPACE_KEY',
              help='Space key (overrides default_space_key from config)')
@click.option('--limit', type=int, default=25, help='Number of results (max 100)')
@click.option('--start', type=int, default=0, help='Pagination start offset')
@click.option('--title-contains', default=None, help='Filter: title contains this string')
@click.option('--open', 'open_first', is_flag=True, help='Open the first result in your browser')
@click.option('--base-url', envvar='CONFLUENCE_BASE_URL', help='Base URL')
@click.option('--pat', envvar='CONFLUENCE_PAT', help='PAT / API token')
@click.pass_context
def list_pages(ctx, space_key, limit, start, title_contains, open_first, base_url, pat):
    """List current (non-archived) pages in a space (flat list)."""
    cfg = ctx.obj.get("config", {})
    base_url = resolve_required("base_url", base_url, cfg)
    pat = resolve_required("pat", pat, cfg)
    space_key = resolve_space_key(space_key, cfg)

    client = ConfluenceClient(base_url=base_url, pat=pat,
                              verbose=ctx.obj.get("verbose", False))
    results = client.list_pages_in_space(space_key=space_key, limit=limit, start=start,
                                         title_contains=title_contains)

    if not results:
        warn(ctx, "No pages found.")
        return

    _print_results(results, start)
    if open_first and results:
        link = client.page_link(results[0])
        if link:
            info(ctx, f"Opening: {link}")
            webbrowser.open(link)


@browse_group.command(name="children")
@click.option('--page-id', required=True, help='Parent page id')
@click.option('--limit', type=int, default=25)
@click.option('--start', type=int, default=0)
@click.option('--open', 'open_first', is_flag=True)
@click.option('--base-url', envvar='CONFLUENCE_BASE_URL', help='Base URL')
@click.option('--pat', envvar='CONFLUENCE_PAT', help='PAT / API token')
@click.pass_context
def list_children(ctx, page_id, limit, start, open_first, base_url, pat):
    """List current (non-archived) child pages of a given page id."""
    cfg = ctx.obj.get("config", {})
    base_url = resolve_required("base_url", base_url, cfg)
    pat = resolve_required("pat", pat, cfg)

    client = ConfluenceClient(base_url=base_url, pat=pat,
                              verbose=ctx.obj.get("verbose", False))
    results = client.list_children(page_id=str(page_id), limit=limit, start=start)

    if not results:
        warn(ctx, "No children found.")
        return

    _print_results(results, start)
    if open_first and results:
        link = client.page_link(results[0])
        if link:
            info(ctx, f"Opening: {link}")
            webbrowser.open(link)


@browse_group.command(name="tree")
@click.option('--space-key', required=True, help='Space key to print the full tree from homepage')
@click.option('--max-depth', type=int, default=0,
              help='Max depth (0 = unlimited)')
@click.option('--base-url', envvar='CONFLUENCE_BASE_URL', help='Base URL')
@click.option('--pat', envvar='CONFLUENCE_PAT', help='PAT / API token')
@click.pass_context
def tree(ctx, space_key, max_depth, base_url, pat):
    """Print the full page tree of a space, starting at its homepage."""
    cfg = ctx.obj.get("config", {})
    base_url = resolve_required("base_url", base_url, cfg)
    pat = resolve_required("pat", pat, cfg)
    space = resolve_space_key(space_key, cfg)  # allows default if provided

    client = ConfluenceClient(base_url=base_url, pat=pat,
                              verbose=ctx.obj.get("verbose", False))

    home_id = client.get_space_homepage(space)
    if not home_id:
        raise click.UsageError(f"Space '{space}' has no homepage (or not accessible).")

    root = client.get_page(home_id)
    click.secho(f"{root.get('title', '(untitled)')}  [id:{home_id}]  (homepage)", fg="cyan")

    # DFS print
    _print_tree(client, parent_id=home_id, depth=1, max_depth=max_depth)


@browse_group.command(name="search")
@click.option('--cql', required=False,
              help='Custom CQL (e.g., "type=page AND space=SPACE ORDER BY lastmodified DESC")')
@click.option('--query', required=False, help='Simple fulltext; will be converted to CQL')
@click.option('--space-key', envvar='CONFLUENCE_SPACE_KEY',
              help='Limit to a space (used with --query)')
@click.option('--limit', type=int, default=25)
@click.option('--start', type=int, default=0)
@click.option('--open', 'open_first', is_flag=True)
@click.option('--base-url', envvar='CONFLUENCE_BASE_URL', help='Base URL')
@click.option('--pat', envvar='CONFLUENCE_PAT', help='PAT / API token')
@click.pass_context
def search(ctx, cql, query, space_key, limit, start, open_first, base_url, pat):
    """Search pages via CQL or a simple query (converted to CQL) — current (non-archived) only."""
    if not cql and not query:
        raise click.UsageError("Provide either --cql or --query")

    cfg = ctx.obj.get("config", {})
    base_url = resolve_required("base_url", base_url, cfg)
    pat = resolve_required("pat", pat, cfg)

    # Build CQL with status=current when using simple query
    if query and not cql:
        cql_parts = [f'text~"{query}"', "type=page", "status=current"]
        if space_key or cfg.get("default_space_key"):
            space = resolve_space_key(space_key, cfg)
            cql_parts.append(f"space={space}")
        cql = " AND ".join(cql_parts) + " ORDER BY lastmodified DESC"

    client = ConfluenceClient(base_url=base_url, pat=pat,
                              verbose=ctx.obj.get("verbose", False))
    results = client.search_cql(cql=cql, limit=limit, start=start)

    if not results:
        warn(ctx, "No results.")
        return

    _print_results(results, start)
    if open_first and results:
        link = client.page_link(results[0])
        if link:
            info(ctx, f"Opening: {link}")
            webbrowser.open(link)


@browse_group.command(name="open")
@click.option('--page-id', required=False, help='Open by page id')
@click.option('--title', required=False, help='Resolve by title (requires space key)')
@click.option('--space-key', envvar='CONFLUENCE_SPACE_KEY',
              help='Space key when resolving by title')
@click.option('--base-url', envvar='CONFLUENCE_BASE_URL', help='Base URL')
@click.option('--pat', envvar='CONFLUENCE_PAT', help='PAT / API token')
@click.pass_context
def open_page(ctx, page_id: Optional[str], title: Optional[str], space_key: Optional[str],
              base_url: Optional[str], pat: Optional[str]):
    """Open a page in your default browser by id or by title."""
    cfg = ctx.obj.get("config", {})
    base_url = resolve_required("base_url", base_url, cfg)
    pat = resolve_required("pat", pat, cfg)

    client = ConfluenceClient(base_url=base_url, pat=pat,
                              verbose=ctx.obj.get("verbose", False))

    if not page_id:
        if not title:
            raise click.UsageError("Provide --page-id or --title (with --space-key or default)")
        space = resolve_space_key(space_key, cfg)
        found = client.find_page_by_title(title=title, space_key=space, parent_id=None)
        if not found:
            raise click.UsageError("Page not found by title/space")
        page_id = found["id"]
        link = client.page_link(found)
    else:
        page = client.get_page(page_id)
        link = client.page_link(page)

    if not link:
        warn(ctx, "Could not build a web link from the API response.")
        click.echo(f"Page ID: {page_id}")
        return

    info(ctx, f"Opening: {link}")
    webbrowser.open(link)


@browse_group.command(name="view")
@click.option('--page-id', required=False, help='View by page id')
@click.option('--title', required=False, help='Resolve by title (requires space key)')
@click.option('--space-key', envvar='CONFLUENCE_SPACE_KEY', help='Space key when resolving by title')
@click.option('--export/--no-export', default=True, help='Use body.export_view (cleaner HTML) instead of body.view')
@click.option('--base-url', envvar='CONFLUENCE_BASE_URL', help='Base URL')
@click.option('--pat', envvar='CONFLUENCE_PAT', help='PAT / API token')
@click.pass_context
def view_page(ctx, page_id: Optional[str], title: Optional[str], space_key: Optional[str],
              export: bool, base_url: Optional[str], pat: Optional[str]):
    """Render a Confluence page inside the terminal."""
    cfg = ctx.obj.get("config", {})
    base_url = resolve_required("base_url", base_url, cfg)
    pat = resolve_required("pat", pat, cfg)

    client = ConfluenceClient(base_url=base_url, pat=pat,
                              verbose=ctx.obj.get("verbose", False))

    title_text = ""
    if not page_id:
        if not title:
            raise click.UsageError("Provide --page-id or --title (with --space-key or default)")
        space = resolve_space_key(space_key, cfg)
        found = client.find_page_by_title(title=title, space_key=space, parent_id=None)
        if not found:
            raise click.UsageError("Page not found by title/space")
        page_id = found["id"]
        title_text = found.get("title", title)
    else:
        meta = client.get_page(page_id)
        title_text = meta.get("title", "")

    html = client.get_page_rendered_html(page_id, export=export)
    if not html:
        warn(ctx, "No rendered content returned by API.")
        return

    md = html_to_markdown(html)
    render_markdown_paged(md, title=title_text or page_id)


# ---------------- interactive mode (homepage-first + viewer) ----------------

@browse_group.command(name="interactive")
@click.option('--space-key', envvar='CONFLUENCE_SPACE_KEY',
              help='Start in this space (defaults to profile default; can be changed in-app with "s")')
@click.option('--base-url', envvar='CONFLUENCE_BASE_URL', help='Base URL')
@click.option('--pat', envvar='CONFLUENCE_PAT', help='PAT / API token')
@click.pass_context
def interactive(ctx, space_key, base_url, pat):
    """
    Interactive browser (arrow keys):
      ↑/↓  Move selection
      →    Drill into children
      ←    Go back
      Enter Open in browser
      v    View in terminal (render)
      /    Search (type and press Enter)
      s    Switch space (lands on the space HOMEPAGE)
      g    Go to page by ID
      n/p  Next/Prev page
      [ ]  Decrease/Increase page size
      r    Refresh
      q    Quit
    """
    cfg = ctx.obj.get("config", {})
    base_url = resolve_required("base_url", base_url, cfg)
    pat = resolve_required("pat", pat, cfg)

    client = ConfluenceClient(base_url=base_url, pat=pat,
                              verbose=ctx.obj.get("verbose", False))

    # ---- State ----
    current_space = resolve_space_key(space_key, cfg) if (space_key or cfg.get("default_space_key")) else None
    mode: str = "children"       # page-centric tree view
    arg: Optional[str] = None    # current page id
    page_size = 25
    start = 0
    items: List[Dict[str, Any]] = []
    index = 0
    stack: List[tuple[str, Optional[str], int, int]] = []  # (mode, arg, start, index)
    status_msg = ""
    header_title = ""
    app_holder: Dict[str, Any] = {"app": None}  # <-- holds the Application instance after creation

    def status(txt: str):
        nonlocal status_msg
        status_msg = txt
        footer_control.text = [("class:footer", status_msg)]
        # safe invalidate only if app is created
        app = app_holder.get("app")
        if app is not None:
            app.invalidate()

    def goto_space(space: str):
        nonlocal current_space, arg, header_title, mode, start, index
        current_space = space
        home = client.get_space_homepage(current_space)
        if not home:
            header_title = f"Space {current_space} (no homepage)"
            arg = None
            items.clear()
            status("No homepage available for this space.")
            return
        root = client.get_page(home)
        header_title = f"{root.get('title','(homepage)')}  [id:{home}]  (homepage)"
        mode, arg, start, index = "children", str(home), 0, 0
        load()

    def load():
        nonlocal items
        if not arg:
            items = []
            status("Press 's' to select a space.")
            return
        try:
            items = client.list_children(page_id=str(arg), limit=page_size, start=start)
            status(f"Children of {arg}  •  start={start}  •  size={page_size}  •  {len(items)} items")
        except Exception as e:
            items = []
            status(f"Error: {e}")

    # ---- UI rendering ----
    def render_list() -> List[tuple[str, str]]:
        rows: List[tuple[str, str]] = []
        if header_title:
            rows.append(("class:heading", f"{header_title}\n"))
        if not items:
            rows.append(("class:dim", "No results"))
            return rows
        for i, it in enumerate(items):
            title = it.get("title", "").replace("\n", " ")
            pid = it.get("id", "")
            prefix = "➤ " if i == index else "  "
            style = "class:selected" if i == index else ""
            rows.append((style, f"{prefix}{i+1+start:>3}. {title}  [id:{pid}]\n"))
        return rows

    list_control = FormattedTextControl(text=render_list)
    list_window = Window(content=list_control, wrap_lines=False, always_hide_cursor=True)

    help_text = TextArea(
        text=(
            "↑/↓ move • Enter open • v view • → children • ← back • / search • s space(homepage) • g goto id • "
            "n/p next/prev • [ ] size • r refresh • q quit"
        ),
        style="class:help",
        height=1,
        read_only=True,
    )

    footer_control = FormattedTextControl(text=[("class:footer", "")])
    footer_window = Window(content=footer_control, height=1)

    root_container = HSplit([help_text, Frame(list_window, title="Confluence Browser"), footer_window])
    layout = Layout(root_container)

    style = Style.from_dict({
        "selected": "reverse",
        "help": "fg:#888888",
        "footer": "fg:#00afff",
        "dim": "fg:#666666",
        "heading": "bold",
    })

    kb = KeyBindings()

    @kb.add("q")
    def _(event):
        event.app.exit()

    @kb.add("up")
    def _(event):
        nonlocal index
        if items:
            index = max(0, index - 1)

    @kb.add("down")
    def _(event):
        nonlocal index
        if items:
            index = min(len(items) - 1, index + 1)

    @kb.add("enter")
    def _(event):
        if not items:
            status("No item selected.")
            return
        pid = str(items[index].get("id"))
        page = client.get_page(pid)
        link = client.page_link(page)
        if link:
            webbrowser.open(link)
            status(f"Opened {pid}")
        else:
            status("Could not build link")

    @kb.add("v")
    def _(event):
        # View selected page in terminal
        if not items:
            status("No item selected.")
            return
        pid = str(items[index].get("id"))
        try:
            meta = client.get_page(pid)
            title = meta.get("title", "")
            html = client.get_page_rendered_html(pid, export=True)
            if not html:
                status("No rendered content.")
                return
            md = html_to_markdown(html)
        except Exception as e:
            status(f"View error: {e}")
            return
        # Exit fullscreen and pass content back to caller to render with Rich pager
        event.app.exit(result=("view", title, md))

    @kb.add("right")
    def _(event):
        nonlocal mode, arg, start, index, header_title
        if not items:
            return
        pid = str(items[index].get("id"))
        stack.append((mode, arg, start, index))
        parent = client.get_page(pid)
        header_title = f"{parent.get('title','')}  [id:{pid}]"
        mode, arg, start, index = "children", pid, 0, 0
        load()

    @kb.add("left")
    def _(event):
        nonlocal mode, arg, start, index, header_title
        if not stack:
            status("Top level")
            return
        mode, arg, start, index = stack.pop()
        if arg:
            parent = client.get_page(str(arg))
            header_title = f"{parent.get('title','')}  [id:{arg}]"
        load()

    @kb.add("/")
    def _(event):
        # Search within current space (status=current).
        nonlocal start, index
        if not current_space:
            status("Select a space first (press 's').")
            return
        q = input_dialog(title="Search", text="Enter query:").run()
        if not q or not q.strip():
            return
        cql_parts = [f'text~"{q.strip()}"', "type=page", "status=current", f"space={current_space}"]
        cql = " AND ".join(cql_parts) + " ORDER BY lastmodified DESC"
        try:
            results = client.search_cql(cql=cql, limit=page_size, start=0)
        except Exception as e:
            status(f"Search error: {e}")
            return
        nonlocal items
        items = results or []
        start = 0
        index = 0
        status(f"Search in {current_space}: '{q.strip()}' • {len(items)} items")

    @kb.add("s")
    def _(event):
        sp = input_dialog(title="Space", text="Enter space key:").run()
        if sp is None or sp.strip() == "":
            return
        stack.clear()
        goto_space(sp.strip())

    @kb.add("g")
    def _(event):
        pid = input_dialog(title="Go to Page ID", text="Enter page id:").run()
        if not pid:
            return
        try:
            page = client.get_page(pid)
        except Exception as e:
            status(f"Go to error: {e}")
            return
        nonlocal arg, start, index, header_title
        arg = str(pid)
        header_title = f"{page.get('title','')}  [id:{pid}]"
        start = 0
        index = 0
        load()

    @kb.add("n")
    def _(event):
        nonlocal start, index
        start += page_size
        index = 0
        load()

    @kb.add("p")
    def _(event):
        nonlocal start, index
        start = max(0, start - page_size)
        index = 0
        load()

    @kb.add("[")
    def _(event):
        nonlocal page_size, start, index
        page_size = max(5, page_size - 5)
        start = 0
        index = 0
        load()

    @kb.add("]")
    def _(event):
        nonlocal page_size, start, index
        page_size = min(100, page_size + 5)
        start = 0
        index = 0
        load()

    @kb.add("r")
    def _(event):
        load()

    # initial view
    header_title = ""
    if current_space:
        home = client.get_space_homepage(current_space)
        if home:
            root = client.get_page(home)
            header_title = f"{root.get('title','(homepage)')}  [id:{home}]  (homepage)"
            mode, arg, start, index = "children", str(home), 0, 0
            load()
        else:
            status("Press 's' to select a space (loads its homepage).")
    else:
        status("Press 's' to select a space (loads its homepage).")

    app = Application(layout=layout, key_bindings=kb, style=style, full_screen=True)
    app_holder["app"] = app  # <-- set the instance so status() can invalidate later
    result = app.run()

    # If the user pressed 'v', render the page in the terminal after leaving the TUI
    if isinstance(result, tuple) and result and result[0] == "view":
        _, title, md = result
        render_markdown_paged(md, title=title)


# ---------------- helpers ----------------

def _print_results(items: List[Dict], start: int = 0):
    for i, r in enumerate(items, start=1 + start):
        title = r.get("title", "")
        pid = r.get("id", "")
        click.echo(f"{i:>3}. {title}  [id:{pid}]")


def _print_tree(client: ConfluenceClient, *, parent_id: str, depth: int, max_depth: int):
    """
    Depth-first print of the page tree from a given parent.
    max_depth = 0 means unlimited depth.
    """
    children = client.list_all_children(page_id=parent_id)
    for c in children:
        title = c.get("title", "(untitled)")
        pid = c.get("id", "")
        click.echo(f"{'  ' * depth}• {title}  [id:{pid}]")
        if max_depth == 0 or depth < max_depth:
            _print_tree(client, parent_id=str(pid), depth=depth + 1, max_depth=max_depth)
