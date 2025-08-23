from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


try:
    import tomllib  # Python 3.11+
except Exception:  # pragma: no cover
    tomllib = None  # type: ignore


CONFIG_DIR = Path.home() / ".config" / "confluence-cli"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "config.toml"


def get_default_config_path() -> Path:
    return DEFAULT_CONFIG_PATH


def _toml_dump(data: Dict[str, Dict[str, Any]]) -> str:
    lines: list[str] = []
    for section, values in data.items():
        lines.append(f"[{section}]")
        for k, v in values.items():
            if isinstance(v, bool):
                sval = "true" if v else "false"
            elif isinstance(v, (int, float)):
                sval = str(v)
            elif v is None:
                sval = '""'
            else:
                sval = str(v).replace('"', '\\"')
                sval = f"\"{sval}\""
            lines.append(f"{k} = {sval}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def load_config(config_path: str | None, profile: str = "default") -> dict[str, Any]:
    cfg: dict[str, Any] = {}
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not path.exists() or not tomllib:
        return cfg
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        if profile in data:
            cfg.update(data.get(profile, {}))
        elif "default" in data:
            cfg.update(data.get("default", {}))
    except Exception:
        return {}
    return cfg


def save_config(config_path: str | Path, profile: str, updates: Dict[str, Any], *, replace_profile: bool = False) -> None:
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    existing: Dict[str, Dict[str, Any]] = {}
    if path.exists() and tomllib:
        try:
            existing = tomllib.loads(path.read_text(encoding="utf-8"))  # type: ignore
        except Exception:
            existing = {}

    if replace_profile:
        existing[profile] = dict(updates)
    else:
        current = existing.get(profile, {})
        current.update(updates)
        existing[profile] = current

    if "default" not in existing:
        existing.setdefault("default", {})

    path.write_text(_toml_dump(existing), encoding="utf-8")


def resolve_required(key: str, value: Any, cfg: dict) -> Any:
    if value is not None and value != "":
        return value
    if key in cfg and cfg[key] not in (None, ""):
        return cfg[key]
    raise SystemExit(f"Missing required option: {key}")


def resolve_space_key(space_key: Any, cfg: dict) -> str:
    """
    Prefer explicit --space-key; otherwise fall back to profile's default_space_key.
    """
    if space_key not in (None, ""):
        return str(space_key)
    if "space_key" in cfg and cfg["space_key"] not in (None, ""):
        # legacy support if someone kept 'space_key' in config
        return str(cfg["space_key"])
    if "default_space_key" in cfg and cfg["default_space_key"] not in (None, ""):
        return str(cfg["default_space_key"])
    raise SystemExit("Missing required option: space_key (no --space-key and no default_space_key in config)")
