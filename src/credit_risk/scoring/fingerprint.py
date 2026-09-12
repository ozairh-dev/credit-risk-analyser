"""Score fingerprint (Phase 6, D45).

Deliberately its own function over `config/thresholds.yaml`, disjoint from
`store.fingerprint.config_fingerprint` which covers `composites.yaml`. The two
scopes do not overlap and must not be merged:

- band edges, weights and grade boundaries move **scores**, never a concept or
  metric value;
- `include_operating_leases`, `include_st_investments` and
  `component_aggregate_tolerance` move **values**, and are already fingerprinted
  where those values are stored.

Reusing the composite fingerprint here would tie score history to config that
cannot affect a score while ignoring the config that can — the misreading D18's
scope note exists to prevent.

The values come only from config (CLAUDE.md rule 6); a missing key raises rather
than defaulting, for the same reason D28 gives.
"""

import hashlib
import json

from credit_risk import config

# Config keys whose values change a score. `trend_materiality` and
# `warning_escalation_count` are deliberately absent: they change trends and
# warnings, not scores, and including them would orphan score history on every
# Phase 7 tuning.
FINGERPRINTED_KEYS = (
    "weights",
    "bands",
    "grades",
    "max_grade_by_categories_scored",
    # a verdict-to-points mapping moves scores, so it belongs here rather than
    # with the trend settings it sits beside in config (D50). The boundary is
    # "does this move a score", not "does this look trend-shaped".
    "trend_points",
)


def score_config_values(thresholds: dict | None = None) -> dict:
    """Resolved values of the score-affecting settings, read from config."""
    loaded = thresholds if thresholds is not None else config.thresholds()
    missing = [key for key in FINGERPRINTED_KEYS if key not in loaded]
    if missing:
        raise KeyError(
            "config/thresholds.yaml is missing required scoring settings: "
            + ", ".join(missing)
        )
    return {key: loaded[key] for key in FINGERPRINTED_KEYS}


def score_fingerprint(values: dict | None = None) -> str:
    """Stable short hash of the score-affecting config values."""
    if values is None:
        values = score_config_values()
    canonical = json.dumps(values, sort_keys=True, separators=(",", ":"),
                           default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]
