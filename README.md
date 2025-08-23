# Confluence CLI

A fast, developer‑friendly CLI for creating and browsing Confluence pages — with an interactive TUI, in‑terminal page viewer, and sensible defaults.

---

## Table of Contents
- [Installation](#installation)
- [Requirements](#requirements)
- [Configuration](#configuration)
- [Quick Start](#quick-start)
- [Commands](#commands)
  - [auth login](#auth-login)
  - [create](#create)
  - [browse list](#browse-list)
  - [browse children](#browse-children)
  - [browse tree](#browse-tree)
  - [browse search](#browse-search)
  - [browse open](#browse-open)
  - [browse view](#browse-view)
  - [browse interactive](#browse-interactive)
- [Interactive Keybindings](#interactive-keybindings)
- [Environment Variables](#environment-variables)
- [Developer API (Python)](#developer-api-python)
- [Troubleshooting](#troubleshooting)

---

## Installation

```bash
# from your project root
pip install -e .
```

If you change dependencies:
```bash
pip install -e . --upgrade
```

---

## Requirements

- **Python** 3.9+ (tested on 3.12)
- **Pandoc** (only required for `confluence create`)
  - macOS: `brew install pandoc`
  - Ubuntu/Debian: `sudo apt-get install pandoc`
  - Windows: https://pandoc.org/installing.html

---

## Configuration

The CLI looks for credentials and defaults in either **env vars** or a simple config file.

### Config file (recommended)
Create `~/.confluence-cli/config.toml`:

```toml
base_url = "https://your-domain.atlassian.net/wiki"
pat = "your_api_token_here"
default_space_key = "ENG"
```

### Or set env vars
See [Environment Variables](#environment-variables).

---

## Quick Start

```bash
# 1) Log in once (writes ~/.confluence-cli/config.toml)
confluence auth login   --base-url "https://your-domain.atlassian.net/wiki"   --pat "your_api_token_here"   --default-space-key "ENG"

# 2) Create a page from Markdown (uses pandoc)
confluence create   --page-title "CLI Upload Test"   --input-md-file sample.md   --html-file out.html   --space-key ENG

# 3) Browse a space as a tree (from the homepage)
confluence browse tree --space-key ENG

# 4) Launch interactive browser (arrow keys to navigate)
confluence browse interactive --space-key ENG

# 5) View a page in-terminal (rendered)
confluence browse view --title "Runbook - PagerDuty" --space-key ENG
```

---

## Commands

### `auth login`
Configure the CLI once; stores values in `~/.confluence-cli/config.toml`.

```bash
confluence auth login   --base-url "https://your-domain.atlassian.net/wiki"   --pat "your_api_token_here"   --default-space-key "ENG"
```

**Options**
- `--base-url` (required): Your Confluence base URL (cloud or DC).
- `--pat` (required): Personal Access Token / API token.
- `--default-space-key` (optional): Default space to use if `--space-key` not provided elsewhere.

---

### `create`
Convert Markdown → HTML via pandoc and create a Confluence page.

```bash
confluence create   --page-title "Release Notes"   --input-md-file release.md   --html-file release.html   --space-key ENG
```

**Common options**
- `--page-title` (required): Page title prefix; actual title gets ` - YYYY-MM-DD` appended.
- `--input-md-file` (required): Markdown source file.
- `--html-file` (required): Output HTML file path (temporary artifact to upload).
- `--space-key` (optional): Overrides `default_space_key` from config.
- `--parent-page-id` (optional): If set, creates the page under this parent. If omitted, page is created at the space root (under homepage where applicable).

> Requires `pandoc` in your PATH.

---

### `browse list`
Flat list of current (non‑archived) pages in a space.

```bash
confluence browse list --space-key ENG --limit 25 --start 0 --title-contains "runbook"
```

**Options**
- `--space-key` Use a specific space (falls back to config default).
- `--limit` Page size (max 100).
- `--start` Offset for pagination.
- `--title-contains` Client‑side contains filter on the title.
- `--open` Open first result in browser.

---

### `browse children`
List direct children of a page (non‑archived).

```bash
confluence browse children --page-id 123456789 --limit 50
```

**Options**
- `--page-id` (required) Parent page ID.
- `--limit`, `--start`, `--open` similar to `browse list`.

---

### `browse tree`
Print the **full page tree** of a space, starting from its **homepage**.

```bash
confluence browse tree --space-key ENG --> Works
# Limit to first two levels:
confluence browse tree --space-key ENG --max-depth 2 --> Works
```

**Options**
- `--space-key` (required)
- `--max-depth` Limit recursion depth (`0` = unlimited).

---

### `browse search`
Search via **CQL** or simple full‑text query (auto‑converted to CQL). Filters to **status=current** by default.

```bash
# Full CQL
confluence browse search --cql 'type=page AND space=ENG ORDER BY lastmodified DESC'

# Simple text query (auto CQL: type=page AND status=current AND space=ENG)
confluence browse search --query "incident runbook" --space-key ENG
```

**Options**
- `--cql` Raw CQL (wins over `--query`).
- `--query` Full‑text query (becomes CQL with `status=current`).
- `--space-key` Optional for `--query`; uses config default if set.
- `--limit`, `--start`, `--open` as above.

---

### `browse open`
Open a page in the browser by **ID** or resolve by **title + space**.

```bash
# by id
confluence browse open --page-id 123456789

# by title
confluence browse open --title "Incident Runbook" --space-key ENG
```

---

### `browse view`
Render a page **inside your terminal** using a clean Confluence export view → Markdown conversion.

```bash
# by id
confluence browse view --page-id 123456789

# by title
confluence browse view --title "Incident Runbook" --space-key ENG --> works
```

**Options**
- `--export / --no-export` Choose `body.export_view` (default, cleaner HTML) vs `body.view`.

---

### `browse interactive`
A full‑screen, keyboard‑driven browser and reader.

```bash
confluence browse interactive --space-key ENG
```

- Starts at the space **homepage**.
- Navigate with arrow keys; press **`v`** to view the selected page in your terminal.
- Press **Enter** to open the selected page in your web browser.

See [Interactive Keybindings](#interactive-keybindings).

---

## Interactive Keybindings

Inside `confluence browse interactive`:

- **↑/↓** — Move selection  
- **→** — Drill into children of the selected page  
- **←** — Go back (up the stack)  
- **Enter** — Open selected page in browser  
- **v** — View selected page in terminal (rendered)  
- **/** — Search within current space (status=current)  
- **s** — Switch space (lands on that space’s homepage) --> Not working
- **g** — Go to a page by ID  --> Not working
- **n / p** — Next / Previous page (pagination)  
- **[ / ]** — Decrease / Increase page size (page length)  --> Not working
- **r** — Refresh  
- **q** — Quit

---

## Environment Variables

You can set these instead of (or in addition to) the config file:

```bash
export CONFLUENCE_BASE_URL="https://your-domain.atlassian.net/wiki"
export CONFLUENCE_PAT="your_api_token_here"
export CONFLUENCE_SPACE_KEY="ENG"   # used as default space if no --space-key
```

Flags always override env/config when provided.

---

## Developer API (Python)

For scripting/embedding, key public methods on `ConfluenceClient`:

```python
# src/confluence/client.py
ConfluenceClient(base_url: str, pat: str, timeout=15, retries=3, backoff=0.5, verbose=False)

# Links
page_link(page_json: dict) -> str

# Space / homepage
get_space_homepage(space_key: str) -> Optional[str]

# CRUD / content
create_page(title: str, space_key: str, body_html: str, parent_id: Optional[str] = None,
            notify_watchers: bool = True) -> dict
get_page(page_id: str) -> dict
get_page_rendered_html(page_id: str, export: bool = True) -> str   # body.export_view / body.view

# Find / list
find_page_by_title(title: str, space_key: str, parent_id: Optional[str] = None) -> Optional[dict]
list_pages_in_space(space_key: str, limit: int = 25, start: int = 0,
                    title_contains: Optional[str] = None) -> list[dict]   # flat
list_children(page_id: str, limit: int = 25, start: int = 0) -> list[dict]
list_all_children(page_id: str) -> list[dict]  # paginated fetch of all direct children
search_cql(cql: str, limit: int = 25, start: int = 0) -> list[dict]
```

Utilities:
- `src/utils/render.py`  
  - `html_to_markdown(html: str) -> str` — Convert Confluence HTML to Markdown.
  - `render_markdown_paged(markdown_text: str, title: Optional[str]) -> None` — Page Markdown nicely in terminal.

---

## Troubleshooting

**Pandoc not found**
```
src.converters.markdown.PandocNotFound: pandoc not found on PATH. Install pandoc and retry.
```
Install pandoc and ensure it’s in your PATH:
```bash
brew install pandoc   # macOS
sudo apt-get install pandoc   # Ubuntu/Debian
```

**SSO redirect / unexpected HTML in API response**
- Ensure `--base-url` points to the **Confluence base** (e.g., `/wiki` for Atlassian Cloud).  
- Example: `https://your-domain.atlassian.net/wiki` (not just the root domain).

**Interactive: “asyncio.run() cannot be called from a running event loop”**
- We avoid modal dialogs inside the running TUI. Errors/notifications are shown in the footer instead. Update to the latest code if you see this.

**Interactive: NameError about `app.invalidate()`**
- Fixed by deferring invalidate until after `Application` is created; ensure you’re on the latest code (`app_holder` pattern).

**Rich Panel API mismatch (`Panel.fit(..., expand=...)`)**
- Newer `rich` versions don’t accept `expand` on `Panel.fit`. The current code uses a compatible call.

**Markdownify error (“either strip or convert, not both”)**
- We now pass a minimal option set; if conversion fails, a safe HTML‑to‑text fallback runs.

---

## License

MIT (or your preferred license — update this section).
