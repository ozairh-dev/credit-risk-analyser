"""Stress policy fingerprint (Phase 8, D56).

Covers the POLICY keys of config/stress.yaml only. The per-run assumptions —
ebitda_mode, fixed_cost_share, floating_share and the resolved new_debt_rate —
are deliberately absent: they are columns on the stress run row.

**A value that varies per run is not a config version.** Fingerprinting one
would make two runs with different assumptions hash identically whenever the
file had not changed, which is D52's mechanism inverted: a fingerprint answers
"which policy produced this row", a per-run column answers "what did this run
assume". Conflating them loses both answers.

Disjoint from the composite (store/), score (scoring/) and trend (trends/)
fingerprints; a test asserts no key appears in two. File location is incidental
to the split — trend_points lives in thresholds.yaml and belongs to the score
scope, default_tax_rate lives here and belongs to this one. Blast radius is the
boundary.
"""

import hashlib
import json

from credit_risk import config

FINGERPRINTED_KEYS = (
    "presets",
    "sensitivity_grid",
    "default_tax_rate",
    "new_debt_rate_default",
    "new_debt_rate_band",
)


def stress_config_values(stress: dict | None = None) -> dict:
    loaded = stress if stress is not None else config.stress()
    missing = [key for key in FINGERPRINTED_KEYS if key not in loaded]
    if missing:
        raise KeyError(
            "config/stress.yaml is missing required stress settings: "
            + ", ".join(missing)
        )
    return {key: loaded[key] for key in FINGERPRINTED_KEYS}


def stress_fingerprint(values: dict | None = None) -> str:
    if values is None:
        values = stress_config_values()
    canonical = json.dumps(values, sort_keys=True, separators=(",", ":"),
                           default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]
