import click


def _should_print(ctx, level: str) -> bool:
    quiet = ctx.obj.get("quiet") if ctx and ctx.obj else False
    if quiet:
        return False
    return True


def info(ctx, msg: str):
    if _should_print(ctx, "info"):
        click.secho(msg, fg="cyan")


def warn(ctx, msg: str):
    if _should_print(ctx, "warn"):
        click.secho(msg, fg="yellow")


def error(ctx, msg: str):
    click.secho(msg, fg="red")


def success(ctx, msg: str):
    if _should_print(ctx, "success"):
        click.secho(msg, fg="green")
