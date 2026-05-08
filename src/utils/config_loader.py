from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load the YAML project configuration."""
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


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

