"""Loads the YAML configuration files.

Thresholds, weights, stress parameters and the XBRL tag map all live in
config/*.yaml so they can be changed without touching code (CLAUDE.md rule 6).
"""

from functools import lru_cache
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"
RAW_DIR = PROJECT_ROOT / "data" / "raw"


@lru_cache
def load(name: str) -> dict:
    """Load config/<name>.yaml. Cached, so edits need a restart."""
    path = CONFIG_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Missing config file: {path}")
    with path.open() as fh:
        return yaml.safe_load(fh)


def thresholds() -> dict:
    return load("thresholds")


def stress() -> dict:
    return load("stress")


def tag_map() -> dict:
    return load("tag_map")
