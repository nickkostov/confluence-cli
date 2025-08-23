from __future__ import annotations

import getpass
from typing import Optional

import click

from ..utils.config import (
    load_config,
    save_config,
    get_default_config_path,
)


@click.group(name="auth")
def auth_group():
    """Authentication & config commands."""
    pass


@auth_group.command(name="login")
@click.option("--profile", default="default", help="Config profile to write")
@click.option("--config", "config_path", type=click.Path(), default=None, help="Config file path")
@click.option("--base-url", prompt=True, help="Confluence base URL (e.g., https://org.atlassian.net/wiki)")
@click.option("--default-space-key", prompt=True, help="Default space key (used when --space-key not passed)")
@click.option(
    "--parent-page-id",
    type=int,
    default=None,
    help="(Optional) Default parent page ID; if omitted, pages are created at the space root"
)
@click.option("--pat", default=None, help="Personal Access Token (omit to be prompted securely)")
def auth_login(
    profile: str,
    config_path: Optional[str],
    base_url: str,
    default_space_key: str,
    parent_page_id: Optional[int],
    pat: Optional[str],
):
    """
    Store credentials and defaults into your config profile.
    Parent page is optional; if not provided, pages will be created at the space root
    unless --parent-page-id is supplied per command.
    """
    if not pat:
        # Hidden input to avoid echo / history
        pat = getpass.getpass("Confluence Personal Access Token: ")

    config_file = config_path or get_default_config_path()
    updates = {
        "base_url": base_url,
        "default_space_key": default_space_key,
        "pat": pat,
    }
    if parent_page_id:
        updates["parent_page_id"] = int(parent_page_id)

    save_config(config_file, profile, updates)
    click.secho(f"✓ Saved profile '{profile}' to {config_file}", fg="green")


@auth_group.command(name="status")
@click.option("--profile", default="default", help="Profile to show")
@click.option("--config", "config_path", type=click.Path(), default=None, help="Config file path")
def auth_status(profile: str, config_path: Optional[str]):
    """Show the active configuration values (token redacted)."""
    cfg = load_config(config_path, profile)
    if not cfg:
        click.secho("No config found.", fg="yellow")
        click.echo(f"Expected at: {config_path or get_default_config_path()}")
        return

    redacted = dict(cfg)
    if "pat" in redacted and redacted["pat"]:
        token = str(redacted["pat"])
        redacted["pat"] = (token[:4] + "…" + token[-4:]) if len(token) > 8 else "********"

    click.secho(f"Profile: {profile}", fg="cyan")
    for k in ("base_url", "default_space_key", "parent_page_id", "pat"):
        if k in redacted:
            click.echo(f"{k}: {redacted[k]}")


@auth_group.command(name="logout")
@click.option("--profile", default="default", help="Profile to clear")
@click.option("--config", "config_path", type=click.Path(), default=None, help="Config file path")
def auth_logout(profile: str, config_path: Optional[str]):
    """Remove stored token from profile (keeps non-secret defaults)."""
    path = config_path or get_default_config_path()
    cfg = load_config(path, profile)
    if not cfg:
        click.secho("Nothing to do — no config found.", fg="yellow")
        return

    if "pat" in cfg:
        cfg["pat"] = ""
        save_config(path, profile, cfg, replace_profile=True)
        click.secho(f"✓ Removed PAT from profile '{profile}' at {path}", fg="green")
    else:
        click.secho("No PAT stored.", fg="yellow")
