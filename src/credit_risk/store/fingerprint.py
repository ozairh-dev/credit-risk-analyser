"""Config fingerprints for append-with-history rows (D18).

A CALCULATED value is not config-independent: `total_debt` changes with
`include_operating_leases` (D6) and `net_debt` with `include_st_investments`,
while the underlying facts are unchanged. Each concepts/metrics row therefore
records a fingerprint of the config values that fed it, so a number that moved
for a settings reason can be told apart from one that moved for a filing
reason.

**What goes into the fingerprint:** only the toggles that change a computed
value — the allowlist below — never the whole config file. Band edges, weights
and grade boundaries are deliberately excluded: they change *scores*, not
concept or metric values, and scores already keep their own history.

Phase 6 must therefore write its OWN fingerprint function over thresholds.yaml
rather than calling this one: the two scopes are disjoint by design, and reusing
this function for scores would fingerprint them against config that cannot
affect them while ignoring the config that can (D18).

The *names* below are an allowlist (which settings affect a value — a code-level
judgement). The *values* come only from config/composites.yaml: CLAUDE.md rule 6
puts them in config, so a missing key raises rather than falling back to a
constant here (D28).
"""

import hashlib
import json

from credit_risk import config

# Config keys whose values change a computed concept or metric value.
# component_aggregate_tolerance joined at Task 9 (D26's noted dependency): it
# changes whether total_debt computes at all, so a row computed under one
# tolerance is not comparable to one computed under another.
FINGERPRINTED_KEYS = (
    "include_operating_leases",
    "include_st_investments",
    "component_aggregate_tolerance",
)
COMPOSITE_CONFIG_FILE = "composites"


def composite_config_values() -> dict:
    """Resolved values of the fingerprinted toggles, read from config.

    Raises KeyError if the config file omits one: silently substituting a
    default would make the fingerprint describe settings the file does not
    contain, and would put a financial-composition default back in code
    (CLAUDE.md rules 3 and 6).
    """
    loaded = config.load(COMPOSITE_CONFIG_FILE) or {}
    missing = [key for key in FINGERPRINTED_KEYS if key not in loaded]
    if missing:
        raise KeyError(
            f"config/{COMPOSITE_CONFIG_FILE}.yaml is missing required "
            f"composite settings: {', '.join(missing)}"
        )
    return {key: loaded[key] for key in FINGERPRINTED_KEYS}


def config_fingerprint(values: dict | None = None) -> str:
    """Stable short hash of the fingerprinted config values."""
    if values is None:
        values = composite_config_values()
    canonical = json.dumps(values, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]
