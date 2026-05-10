from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


class StockConfigLoader(yaml.SafeLoader):
    """YAML loader that keeps ticker-like words such as ON as strings."""


StockConfigLoader.yaml_implicit_resolvers = {
    key: [
        (tag, regexp)
        for tag, regexp in resolvers
        if tag != "tag:yaml.org,2002:bool"
    ]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load the YAML project configuration."""
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    with path.open("r", encoding="utf-8") as handle:
        return yaml.load(handle, Loader=StockConfigLoader) or {}


def as_bool(value: Any, default: bool = False) -> bool:
    """Parse booleans from config values after disabling YAML bool coercion."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise ValueError(f"Expected a boolean config value, got {value!r}")


def deep_update(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    """Return a recursive copy of base updated with updates."""
    result = deepcopy(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_update(result[key], value)
        else:
            result[key] = value
    return result


def project_path(path_value: str | Path) -> Path:
    """Resolve a config path relative to the repository root."""
    path = Path(path_value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def ensure_parent_dir(path_value: str | Path) -> Path:
    path = project_path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def ensure_dir(path_value: str | Path) -> Path:
    path = project_path(path_value)
    path.mkdir(parents=True, exist_ok=True)
    return path
