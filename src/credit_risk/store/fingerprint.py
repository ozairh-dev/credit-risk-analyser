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

The composites config file does not exist yet (Task 9 creates it); until then
the methodology's documented defaults are fingerprinted, so the value is
stable and meaningful from the first stored row.
"""

import hashlib
import json

from credit_risk import config

# Allowlist: (config file stem, key) -> documented default from
# docs/credit-methodology.md "Composite concepts".
COMPOSITE_DEFAULTS = {
    "include_operating_leases": True,   # D6
    "include_st_investments": True,
}
COMPOSITE_CONFIG_FILE = "composites"


def composite_config_values() -> dict:
    """Resolved values of the fingerprinted toggles."""
    try:
        loaded = config.load(COMPOSITE_CONFIG_FILE) or {}
    except FileNotFoundError:
        loaded = {}
    return {key: loaded.get(key, default) for key, default in COMPOSITE_DEFAULTS.items()}


def config_fingerprint(values: dict | None = None) -> str:
    """Stable short hash of the fingerprinted config values."""
    if values is None:
        values = composite_config_values()
    canonical = json.dumps(values, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]
