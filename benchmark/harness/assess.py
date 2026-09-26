"""One point-in-time assessment of one company, as the benchmark reads it.

Everything A2 measures comes through here, so the failure cohort and the
survivor panel are assessed by identical code. If they were assessed by two
functions the comparison would be between the functions as much as between the
companies (CLAUDE.md rule 13).
"""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from pit import filter_payload                               # noqa: E402

from credit_risk import pipeline                              # noqa: E402

SEVERITIES = ("Low", "Medium", "High")


def load_payload(path) -> dict:
    return json.loads(pathlib.Path(path).read_text())["content"]


def assess(raw: dict, cutoff: str) -> dict:
    """The engine's view of one company as of `cutoff`, and nothing else.

    Returns the latest scoreable period at that cutoff. `None` grade means the
    engine produced no score at all — which is a result, not a missing value,
    and the caller must not treat it as neutral.
    """
    pit = filter_payload(raw, cutoff)
    (_sel, mapping, composites, integrity, metrics, trends, scores,
     _stress) = pipeline.analyse(pit)

    if not scores:
        return {
            "scored": False, "period_end": None, "grade": None,
            "grade_uncapped": None, "total_score": None,
            "categories_scored": 0, "capped": None, "cap_binding": None,
            "metric_values": sum(1 for m in metrics.metrics
                                 if m.data_status == "CALCULATED"),
            "warnings": 0, "escalated": 0, "high_severity": 0,
            "warning_indicators": [], "deteriorating": [],
            "periods_available": len({c.end for c in mapping.concepts}),
        }

    last = max(scores, key=lambda s: s.period_end)
    end = last.period_end
    warnings = [w for w in trends.warnings if w.period_end == end]
    deteriorating = sorted({t.metric for t in trends.trends
                            if t.period_end == end
                            and t.verdict == "Deteriorating"})
    return {
        "scored": True,
        "period_end": end,
        "grade": last.grade,
        "grade_uncapped": last.grade_uncapped,
        "total_score": round(last.total_score, 2),
        "categories_scored": last.categories_available,
        "capped": bool(last.grade_capped),
        "cap_binding": bool(last.cap_binding),
        "metric_values": sum(1 for m in metrics.metrics
                             if m.data_status == "CALCULATED"
                             and m.end == end),
        "warnings": len(warnings),
        "escalated": sum(1 for w in warnings if w.escalated),
        "high_severity": sum(1 for w in warnings if w.severity == "High"),
        "warning_indicators": sorted(w.indicator for w in warnings),
        "deteriorating": deteriorating,
        "periods_available": len({c.end for c in mapping.concepts}),
        "integrity_fail_periods": sorted(
            {r.period_end for r in integrity.results if r.outcome == "FAIL"}),
    }
