"""Configuration utilities for running all stages with a YAML file."""

from __future__ import annotations

from pathlib import Path

import yaml


def load_config(config_path: str | Path) -> dict:
    config_file = Path(config_path)
    with config_file.open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, dict):
        raise ValueError(f"Config must be a mapping: {config_file}")
    return config
