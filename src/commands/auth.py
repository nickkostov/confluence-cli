from __future__ import annotations

import click

from ..utils.config import (
    load_config,
    save_config,
    get_default_config_path,
)
from ..utils.log import info, success, warn


@click.group(name="auth")
def auth_group():
    """Authentication & configuration commands."""
    pass


@auth_group.command(name="login")
@click.option("--base-url", help="Confluence base URL (e.g. https://your-domain.atlassian.net/wiki)")
@click.option("--pat", help="Personal Access Token / API token")
@click.option("--default-space-key", help="Default space key used by commands when --space-key is omitted")
# LLM options (optional)
@click.option("--llm-provider", type=click.Choice(["ollama", "openai_compat"]), help="Self-hosted LLM provider")
@click.option("--model", help="Model name (e.g. 'mistral:latest' for Ollama or 'mistral-7b-instruct' for OpenAI-comp)")
@click.option("--ollama-base", help="Ollama base URL (default http://localhost:11434)")
@click.option("--api-base", help="OpenAI-compatible API base (e.g. http://localhost:8000/v1)")
@click.option("--api-key", help="API key for OpenAI-compatible provider")
@click.option("--configure-llm", is_flag=True, help="Interactively prompt for missing LLM settings")
@click.option(
    "--config",
    "config_path",
    type=click.Path(dir_okay=True, path_type=str),
    help="Path to config file or directory (default: ~/.config/confluence-cli/config.toml)",
)
@click.option("--profile", default="default", show_default=True, help="Profile section to write")
def auth_login(
    base_url: str | None,
    pat: str | None,
    default_space_key: str | None,
    llm_provider: str | None,
    model: str | None,
    ollama_base: str | None,
    api_base: str | None,
    api_key: str | None,
    configure_llm: bool,
    config_path: str | None,
    profile: str,
):
    """
    Store credentials and (optionally) LLM settings in the config profile.
    Writes to ~/.config/confluence-cli/config.toml by default.
    """
    # load (so we can show current values when prompting)
    current = load_config(config_path, profile)

    # ---- Core Confluence settings ----
    updates: dict[str, str] = {}

    if not base_url:
        base_url = click.prompt(
            "Confluence base URL",
            default=current.get("base_url") or "",
            show_default=bool(current.get("base_url")),
        )
    if not pat:
        pat = click.prompt(
            "API token (PAT)",
            default=current.get("pat") or "",
            show_default=False,
            hide_input=True,
        )
    if default_space_key is None:
        default_space_key = click.prompt(
            "Default space key",
            default=current.get("default_space_key") or "",
            show_default=bool(current.get("default_space_key")),
        )

    if base_url:
        updates["base_url"] = base_url
    if pat:
        updates["pat"] = pat
    if default_space_key:
        updates["default_space_key"] = default_space_key

    # ---- LLM settings (optional) ----
    # If any LLM flag was given or --configure-llm is set, we go through this block.
    wants_llm = any([llm_provider, model, ollama_base, api_base, api_key, configure_llm])
    if wants_llm:
        llm_provider = llm_provider or click.prompt(
            "LLM provider",
            type=click.Choice(["ollama", "openai_compat"]),
            default=current.get("llm_provider") or "ollama",
            show_default=True,
        )

        if llm_provider == "ollama":
            model = model or click.prompt(
                "Ollama model",
                default=current.get("model") or "mistral:latest",
                show_default=True,
            )
            ollama_base = ollama_base or click.prompt(
                "Ollama base URL",
                default=current.get("ollama_base") or "http://localhost:11434",
                show_default=True,
            )
            updates["llm_provider"] = "ollama"
            updates["model"] = model
            updates["ollama_base"] = ollama_base

            # Clear any OpenAI-comp keys if present previously (optional; harmless if left)
            updates.setdefault("api_base", current.get("api_base") or "")
            updates.setdefault("api_key", current.get("api_key") or "")

        else:  # openai_compat
            api_base = api_base or click.prompt(
                "OpenAI-compatible API base",
                default=current.get("api_base") or "http://localhost:8000/v1",
                show_default=True,
            )
            api_key = api_key or click.prompt(
                "API key",
                default=current.get("api_key") or "",
                show_default=False,
                hide_input=True,
            )
            model = model or click.prompt(
                "Model name",
                default=current.get("model") or "mistral-7b-instruct",
                show_default=True,
            )
            updates["llm_provider"] = "openai_compat"
            updates["api_base"] = api_base
            updates["api_key"] = api_key
            updates["model"] = model

            # Clear any Ollama key if present previously (optional)
            updates.setdefault("ollama_base", current.get("ollama_base") or "")

    # ---- Save ----
    target_path = config_path or str(get_default_config_path())
    save_config(target_path, profile, updates, replace_profile=False)

    # ---- Print summary (redacted) ----
    info(None, f"Saved profile [{profile}] to {target_path}")
    redacted = {
        k: ("***" if k in {"pat", "api_key"} and v else v)
        for k, v in updates.items()
    }
    for k, v in redacted.items():
        click.echo(f"  {k} = {v}")

    success(None, "Done.")
