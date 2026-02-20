"""Configuration loader for validator."""

from __future__ import annotations

from pathlib import Path

import yaml


def load_config() -> dict:
    """Load validator configuration from YAML file.

    :returns: Configuration dictionary
    :raises FileNotFoundError: If config.yaml does not exist
    """
    path = Path(__file__).parent / "config.yaml"
    if not path.exists():
        template_path = Path(__file__).parent / "config.yaml.template"
        msg = f"Config not found: {path}\n  cp {template_path} {path}"
        raise FileNotFoundError(msg)

    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)
