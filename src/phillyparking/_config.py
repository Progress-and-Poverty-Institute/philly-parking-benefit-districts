"""Central configuration loader.

Single source of truth for parameters. All modules consume YAML from `config/`
through `load_config(name)`. Tests can override paths via `PHILLYPARKING_CONFIG_DIR`.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


def project_root() -> Path:
    """Return the repository root.

    Resolves by walking up from this file until a `pyproject.toml` is found,
    or from `PHILLYPARKING_PROJECT_ROOT` if set.
    """
    env = os.environ.get("PHILLYPARKING_PROJECT_ROOT")
    if env:
        return Path(env).resolve()
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError("Could not locate project root (no pyproject.toml found).")


def config_dir() -> Path:
    env = os.environ.get("PHILLYPARKING_CONFIG_DIR")
    return Path(env).resolve() if env else project_root() / "config"


def data_dir() -> Path:
    env = os.environ.get("PHILLYPARKING_DATA_DIR")
    return Path(env).resolve() if env else project_root() / "data"


def outputs_dir() -> Path:
    env = os.environ.get("PHILLYPARKING_OUTPUTS_DIR")
    return Path(env).resolve() if env else project_root() / "outputs"


@lru_cache(maxsize=None)
def load_config(name: str) -> dict[str, Any]:
    """Load a YAML config file by stem (e.g. 'zones', 'pricing_rules')."""
    path = config_dir() / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)
