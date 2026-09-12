"""Trend and warning fingerprint (Phase 7, D52).

Disjoint from the score fingerprint by the same argument D38 makes for
integrity thresholds: these settings change **which warnings fire**, not what a
score is. A warning that stopped firing because a threshold moved must be
distinguishable from one that stopped because the company improved, and only a
fingerprint stored on the warning row can tell them apart.

`trend_points` is deliberately NOT here — it moves scores, so it belongs to the
score fingerprint (D45/D50). The boundary is "does this move a score", not
"does this live in thresholds.yaml".
"""

import hashlib
import json

from credit_risk import config

FINGERPRINTED_KEYS = ("trend_materiality", "warning_escalation_count")


def trend_config_values(thresholds: dict | None = None) -> dict:
    loaded = thresholds if thresholds is not None else config.thresholds()
    missing = [key for key in FINGERPRINTED_KEYS if key not in loaded]
    if missing:
        raise KeyError(
            "config/thresholds.yaml is missing required trend settings: "
            + ", ".join(missing)
        )
    return {key: loaded[key] for key in FINGERPRINTED_KEYS}


def trend_fingerprint(values: dict | None = None) -> str:
    if values is None:
        values = trend_config_values()
    canonical = json.dumps(values, sort_keys=True, separators=(",", ":"),
                           default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]
