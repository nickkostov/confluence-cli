import click

from .utils.config import load_config
from .commands.create_document import create_document
from .commands.update_document import update_document
from .commands.convert_only import convert_only
from .commands.auth import auth_group
from .commands.browse import browse_group


@click.group()
@click.option("--config", "config_path", type=click.Path(exists=False), help="Path to config TOML")
@click.option("--profile", default="default", help="Config profile name")
@click.option("--verbose/--no-verbose", default=False)
@click.option("--quiet/--no-quiet", default=False)
@click.option("--json/--no-json", "json_mode", default=False)
@click.pass_context
def cli(ctx, config_path, profile, verbose, quiet, json_mode):
    """Confluence CLI"""
    cfg = load_config(config_path, profile)
    ctx.ensure_object(dict)
    ctx.obj.update({
        "config": cfg,
        "verbose": verbose,
        "quiet": quiet,
        "json": json_mode,
    })


# Subcommands
cli.add_command(auth_group)
cli.add_command(create_document)
cli.add_command(update_document)
cli.add_command(convert_only)
cli.add_command(browse_group)


if __name__ == "__main__":
    cli()
