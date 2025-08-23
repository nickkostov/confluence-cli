from __future__ import annotations
import click
from ..utils.config import load_config, debug_dump_config

@click.group(name="config")
def config_group():
    """Inspect and diagnose configuration."""
    pass

@config_group.command(name="show")
@click.option("--config", "config_path", type=click.Path(dir_okay=True), required=False, help="Config path or directory")
@click.option("--profile", default="default", show_default=True)
def show_config(config_path, profile):
    """Print the merged config (redacted) and where it was loaded from."""
    cfg = load_config(config_path, profile)
    redacted = debug_dump_config(cfg)
    click.echo_via_pager(click.style("=== Confluence CLI config (redacted) ===\n", fg="cyan"))
    click.echo_via_pager(f"Source: {redacted.get('_meta',{}).get('source')}")
    click.echo_via_pager(f"Path  : {redacted.get('_meta',{}).get('config_path')}")
    # pretty print TOML-ish
    import json
    click.echo_via_pager(json.dumps(redacted, indent=2, ensure_ascii=False))

@config_group.command(name="doctor")
@click.option("--config", "config_path", type=click.Path(dir_okay=True), required=False)
@click.option("--profile", default="default", show_default=True)
def config_doctor(config_path, profile):
    """Validate required keys and LLM settings."""
    cfg = load_config(config_path, profile)
    errs = []
    for key in ("base_url", "pat"):
        if not cfg.get(key):
            errs.append(f"Missing required key: {key}")
    llm = cfg.get("llm") or {}
    provider = (llm.get("provider") or "").strip().lower()
    if provider not in ("ollama", "openai_compat", ""):
        errs.append(f"llm.provider invalid: {provider!r}")
    elif provider == "ollama":
        if not llm.get("model"):
            errs.append("llm.model is required for provider=ollama")
    elif provider == "openai_compat":
        for k in ("api_base", "api_key", "model"):
            if not llm.get(k):
                errs.append(f"llm.{k} is required for provider=openai_compat")

    if errs:
        click.echo(click.style("Config issues found:", fg="red"))
        for e in errs:
            click.echo(f" - {e}")
        click.echo("\nRun: confluence config show")
        raise SystemExit(2)

    click.echo(click.style("Config OK ✅", fg="green"))
    click.echo(f"Loaded from: {cfg.get('_meta',{}).get('config_path')}")
