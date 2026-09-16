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
    """Concept -> ordered candidate tags.

    Settings keys in tag_map.yaml (D69's disagreement tolerance and refuse
    list) are filtered out here: every caller treats this as a pure
    concept-to-tags mapping, and the concept count is pinned by test.
    """
    return {k: v for k, v in load("tag_map").items() if isinstance(v, list)
            and v and isinstance(v[0], str) and k != "refuse_on_candidate_disagreement"}


def tag_map_settings() -> dict:
    """The non-concept settings in tag_map.yaml (D69)."""
    loaded = load("tag_map")
    return {
        "candidate_disagreement_tolerance":
            loaded.get("candidate_disagreement_tolerance", 0.05),
        "refuse_on_candidate_disagreement":
            tuple(loaded.get("refuse_on_candidate_disagreement", ())),
    }


def ingestion() -> dict:
    return load("ingestion")


def integrity() -> dict:
    return load("integrity")
