# src/cli.py
from __future__ import annotations

import click

from .utils.config import load_config
from .commands.auth import auth_group
from .commands.create_document import create_document
from .commands.update_document import update_document
from .commands.convert_only import convert_only
from .commands.browse import browse_group
from .commands.author import author


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--config",
    "config_path",
    type=click.Path(dir_okay=False, path_type=str),
    help="Path to config TOML (default: ~/.confluence-cli/config.toml)",
)
@click.option(
    "--profile",
    default="default",
    show_default=True,
    help="Config profile name in the TOML file",
)
@click.option(
    "--verbose/--no-verbose",
    default=False,
    show_default=True,
    help="Verbose logging",
)
@click.option(
    "--quiet/--no-quiet",
    default=False,
    show_default=True,
    help="Suppress non-error output",
)
@click.option(
    "--json/--no-json",
    "json_mode",
    default=False,
    show_default=True,
    help="Output in JSON where supported",
)
@click.version_option(package_name="confluence-cli", prog_name="confluence")
@click.pass_context
def cli(ctx: click.Context, config_path: str | None, profile: str,
        verbose: bool, quiet: bool, json_mode: bool):
    """
    Confluence CLI — create, browse, and author Confluence pages.
    """
    cfg = load_config(config_path, profile)

    # shared context for subcommands
    ctx.ensure_object(dict)
    ctx.obj.update(
        {
            "config": cfg,
            "verbose": verbose,
            "quiet": quiet,
            "json": json_mode,
            "profile": profile,
            "config_path": config_path,
        }
    )


# ---- Subcommands ----
cli.add_command(auth_group)        # confluence auth ...
cli.add_command(create_document)   # confluence create ...
cli.add_command(update_document)   # confluence update ...
cli.add_command(convert_only)      # confluence convert-only ...
cli.add_command(browse_group)      # confluence browse ...
cli.add_command(author)            # confluence author ...


if __name__ == "__main__":
    cli()
