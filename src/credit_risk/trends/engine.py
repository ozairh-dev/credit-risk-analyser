"""Trend classification and early warnings (Phase 7).

Every rule here is sequence-based, which is the hazard D43 exists to name. The
rule is applied **per trended metric, to that metric's own series**:

    eligibility (D40)  a period is a link in M's chain only if M resolves there
    window     (D36)   every consecutive gap in the window must sit inside
                       continuity_window_days

Both, per rule, on the series that rule actually reads — not on "the period" in
general, and not once for all seven. D43 is the record of what happens when the
second half is skipped because the first was cited.

Trends run BEFORE scoring: the ebitda_margin_trend component consumes a verdict
from here.
"""

from dataclasses import dataclass, field
from datetime import date

from credit_risk import config

IMPROVING = "Improving"
STABLE = "Stable"
DETERIORATING = "Deteriorating"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

MIN_PERIODS = 3     # the methodology's stated minimum

# Which direction is bad, per trended series. `source` says which layer the
# series comes from, because trends read metrics, composites and one reported
# concept — and eligibility is decided on the series itself.
RISING_IS_BAD = "rising"
FALLING_IS_BAD = "falling"

TRENDED = {
    "net_debt_to_ebitda":          (RISING_IS_BAD, "metric"),
    "ebit_interest_cover":         (FALLING_IS_BAD, "metric"),
    "ebitda_margin":               (FALLING_IS_BAD, "metric"),
    "revenue_growth":              (FALLING_IS_BAD, "metric"),
    "cash_to_current_liabilities": (FALLING_IS_BAD, "metric"),
    "fcf":                         (FALLING_IS_BAD, "composite"),
    "total_debt":                  (RISING_IS_BAD, "composite"),
}

# Materiality key names differ from the series name in one case.
MATERIALITY_KEY = {"revenue_growth": "revenue_growth_drop"}


@dataclass
class Trend:
    metric: str
    period_end: str
    verdict: str
    change_1y: float | None = None
    change_over_window: float | None = None
    window: tuple = ()          # the period ends actually used
    reason: str | None = None   # why INSUFFICIENT_DATA


@dataclass
class Warning_:
    indicator: str
    period_end: str
    base_severity: str
    severity: str
    current_value: float | None = None
    previous_value: float | None = None
    change: float | None = None
    threshold: float | None = None
    evidence_concepts: list = field(default_factory=list)
    escalated: bool = False
    escalation_reason: str | None = None
    warnings_in_period: int | None = None


@dataclass
class TrendReport:
    trends: list       # every (metric, period) pair, verdict included
    warnings: list


def _eligible_window(series_ends, index, window_days):
    """The MIN_PERIODS ending at `index`, or None if not a valid window.

    `series_ends` holds only periods where THIS metric resolves (D40's filter
    applied to this rule's series). The window test then rejects a run that is
    eligible but not contiguous in time (D36).
    """
    if index + 1 < MIN_PERIODS:
        return None
    window = series_ends[index - MIN_PERIODS + 1: index + 1]
    low, high = window_days
    for earlier, later in zip(window, window[1:]):
        gap = (date.fromisoformat(later) - date.fromisoformat(earlier)).days
        if not (low <= gap <= high):
            return None
    return window


def _material(metric, change, base, materiality, relative):
    """Is `change` material? Relative metrics need a non-zero base.

    Returns (material, threshold) or (None, threshold) when a relative change
    has a zero base — an undefined proportion, refused rather than computed
    (D34's shape).
    """
    threshold = materiality[MATERIALITY_KEY.get(metric, metric)]
    if metric in relative:
        if base == 0:
            return None, threshold
        return abs(change) / abs(base) >= threshold, threshold
    return abs(change) >= threshold, threshold


def classify(metric, values, materiality, relative):
    """Improving / Stable / Deteriorating for one window of MIN_PERIODS values.

    `values` runs oldest -> latest.
    """
    direction, _ = TRENDED[metric]
    worse = 1 if direction == RISING_IS_BAD else -1
    latest, prior, oldest = values[-1], values[-2], values[0]
    change_1y = latest - prior
    change_window = latest - oldest

    m1, threshold = _material(metric, change_1y, prior, materiality, relative)
    mw, _ = _material(metric, change_window, oldest, materiality, relative)
    if m1 is None or mw is None:
        return INSUFFICIENT_DATA, change_1y, change_window, threshold

    # strict: a flat year breaks monotonicity — a stalled series is not
    # "each year worse than the last" (D49)
    steps = [b - a for a, b in zip(values, values[1:])]
    monotonic_worse = all(s * worse > 0 for s in steps)
    monotonic_better = all(s * worse < 0 for s in steps)

    # revenue_growth carries an absolute clause the other six do not: negative
    # growth is bad regardless of the direction of travel (D49)
    if metric == "revenue_growth" and latest < 0:
        return DETERIORATING, change_1y, change_window, threshold

    if (m1 and change_1y * worse > 0) or (mw and change_window * worse > 0
                                          and monotonic_worse):
        return DETERIORATING, change_1y, change_window, threshold
    if (m1 and change_1y * worse < 0) or (mw and change_window * worse < 0
                                          and monotonic_better):
        return IMPROVING, change_1y, change_window, threshold
    return STABLE, change_1y, change_window, threshold


def compute_trends(series, all_period_ends, thresholds=None, window_days=None):
    """A verdict for every (trended metric, period) pair.

    `series` maps metric -> {period_end: value}, holding only resolved values —
    which is what makes the eligibility filter fall out per rule rather than
    needing a separate pass.
    """
    thresholds = thresholds or config.thresholds()
    window_days = window_days or config.integrity()["continuity_window_days"]
    materiality = thresholds["trend_materiality"]
    relative = set(materiality.get("relative", ()))

    trends = []
    for metric in TRENDED:
        resolved = series.get(metric, {})
        ends = sorted(resolved)                       # D40: this metric's own chain
        for period_end in all_period_ends:
            if period_end not in resolved:
                trends.append(Trend(metric, period_end, INSUFFICIENT_DATA,
                                    reason=f"{metric} does not resolve"))
                continue
            window = _eligible_window(ends, ends.index(period_end), window_days)
            if window is None:
                trends.append(Trend(
                    metric, period_end, INSUFFICIENT_DATA,
                    reason=f"fewer than {MIN_PERIODS} consecutive periods"))
                continue
            verdict, d1, dw, _ = classify(
                metric, [resolved[e] for e in window], materiality, relative)
            reason = (f"{metric} base period is zero"
                      if verdict == INSUFFICIENT_DATA else None)
            trends.append(Trend(metric, period_end, verdict, d1, dw,
                                tuple(window), reason))
    return trends


# ---------------------------------------------------------------------------
# early warnings

SEVERITIES = ("Low", "Medium", "High")

# indicator -> (trended metric or None, base severity)
TREND_WARNINGS = {
    "leverage_deterioration": ("net_debt_to_ebitda", "Medium"),
    "coverage_deterioration": ("ebit_interest_cover", "Medium"),
    "cash_flow_deterioration": ("fcf", "Medium"),
    "margin_deterioration": ("ebitda_margin", "Low"),
    "revenue_deterioration": ("revenue_growth", "Low"),
    "liquidity_deterioration": ("cash_to_current_liabilities", "Medium"),
    "debt_increase": ("total_debt", "Low"),
}

# indicator -> (series, comparison, threshold, base severity)
LEVEL_WARNINGS = {
    "negative_fcf": ("fcf", "<", 0.0, "Medium"),
    "negative_ebitda": ("ebitda", "<=", 0.0, "High"),
    "negative_equity": ("equity", "<=", 0.0, "High"),
    "coverage_below_2x": ("ebit_interest_cover", "<", 2.0, "High"),
}


def _escalate(severity):
    index = SEVERITIES.index(severity)
    return SEVERITIES[min(index + 1, len(SEVERITIES) - 1)]


def detect_warnings(trends, series, period_ends, inputs=None, thresholds=None):
    """The eleven indicators, with the escalation rule applied per period."""
    thresholds = thresholds or config.thresholds()
    escalation_count = thresholds["warning_escalation_count"]
    inputs = inputs or {}
    by_period = {}
    for t in trends:
        by_period.setdefault(t.period_end, {})[t.metric] = t

    warnings = []
    for period_end in period_ends:
        fired = []
        for indicator, (metric, base) in TREND_WARNINGS.items():
            trend = by_period.get(period_end, {}).get(metric)
            if trend is None or trend.verdict != DETERIORATING:
                continue
            values = series.get(metric, {})
            prior = (values.get(trend.window[-2])
                     if len(trend.window) >= 2 else None)
            fired.append(Warning_(
                indicator=indicator, period_end=period_end, base_severity=base,
                severity=base, current_value=values.get(period_end),
                previous_value=prior, change=trend.change_1y,
                threshold=thresholds["trend_materiality"][
                    MATERIALITY_KEY.get(metric, metric)],
                evidence_concepts=inputs.get(metric, []),
            ))
        for indicator, (name, op, limit, base) in LEVEL_WARNINGS.items():
            value = series.get(name, {}).get(period_end)
            if value is None:
                continue
            if (value < limit) if op == "<" else (value <= limit):
                fired.append(Warning_(
                    indicator=indicator, period_end=period_end,
                    base_severity=base, severity=base, current_value=value,
                    threshold=limit, evidence_concepts=inputs.get(name, []),
                ))

        if len(fired) >= escalation_count:
            reason = (f"{len(fired)} warnings fired in this period, at or above "
                      f"the escalation threshold of {escalation_count}")
            for w in fired:
                w.severity = _escalate(w.base_severity)
                w.escalated = True
                w.escalation_reason = reason
                w.warnings_in_period = len(fired)
        else:
            for w in fired:
                w.warnings_in_period = len(fired) or None
        warnings.extend(fired)
    return warnings


def analyse_trends(mapping, composites, metrics_report, thresholds=None,
                   window_days=None) -> TrendReport:
    """Trends and warnings for one company.

    Assembles the three layers trends read from — metrics, composites and the
    one reported concept (`equity`) the negative-equity warning needs — then
    applies the per-rule eligibility and window tests.
    """
    series: dict = {}
    for c in mapping.concepts:
        series.setdefault(c.concept, {})[c.end] = c.value
    for c in composites:
        if c.data_status == "CALCULATED":
            series.setdefault(c.concept, {})[c.end] = c.value
    for m in metrics_report.metrics:
        if m.data_status == "CALCULATED":
            series.setdefault(m.metric, {})[m.end] = m.value

    # evidence bottoms out in concepts: a metric's warning cites the concepts
    # that fed it, reachable through metric_inputs (D51)
    inputs: dict = {}
    for m in metrics_report.metrics:
        if m.data_status == "CALCULATED" and m.inputs:
            inputs.setdefault(m.metric, []).extend(
                name for name, _ in m.inputs)
    for name in ("fcf", "total_debt", "ebitda", "equity"):
        inputs.setdefault(name, [name])

    period_ends = sorted({m.end for m in metrics_report.metrics})
    trends = compute_trends(series, period_ends, thresholds, window_days)
    warnings = detect_warnings(trends, series, period_ends, inputs, thresholds)
    return TrendReport(trends=trends, warnings=warnings)


def verdicts_by_period(report: TrendReport) -> dict:
    """(period_end, metric) -> verdict, the shape scoring consumes."""
    return {(t.period_end, t.metric): t.verdict for t in report.trends}
