"""Scoring engine (Phase 6, docs/credit-methodology.md "Scoring").

Band lookup, category aggregation, grade assignment, the missing-data rules and
the explain output. Not trends (Phase 7), not stress (Phase 8).

The missing-data rules are where this phase's complexity lives, and they are
driven by D41's three reason kinds rather than merely recording them:

    EVIDENCE  scores 0 points and is COUNTED — negative EBITDA is a finding
    GAP       dropped from the mean; if it empties a category, the grade caps
    NEITHER   dropped; benign — an unlevered company is not penalised

Two further component states exist that no kind covers: a component whose
feature is not built yet (Phase 7's trend), and the distinction between a
category emptied by gaps and one emptied benignly. See D45.
"""

from bisect import bisect_right
from dataclasses import dataclass, field

from credit_risk import config
from credit_risk.metrics.ratios import reason_kind

# Component treatments (D45). Three of these existed when the table shipped.
SCORED = "scored"
EVIDENCE_ZERO = "evidence_zero"
DROPPED_GAP = "dropped_data_gap"
DROPPED_UNLEVERED = "dropped_unlevered"
NOT_YET_IMPLEMENTED = "not_yet_implemented"

# Why a category produced no score at all.
CAUSE_GAP = "data_gap"
CAUSE_UNLEVERED = "unlevered"
CAUSE_NOT_IMPLEMENTED = "not_yet_implemented"

CATEGORIES = {
    "leverage": ("net_debt_to_ebitda", "debt_to_capital"),
    "coverage": ("ebit_interest_cover",),
    "liquidity": ("current_ratio", "cash_to_current_liabilities"),
    "cash_flow": ("fcf_to_debt", "fcf_margin"),
    "business_performance": ("revenue_growth", "ebitda_margin_trend"),
}

# Components whose phase does not exist yet. Empty since Phase 7 landed — the
# trend component is now real. Kept rather than deleted: the mechanism is what
# lets a future component join the row shape before it can be scored, and its
# emptiness is the record that nothing is currently pending.
PENDING_COMPONENTS: frozenset = frozenset()

# Components scored from a trend verdict rather than a metric value (D50).
TREND_COMPONENTS = {"ebitda_margin_trend": "ebitda_margin"}


@dataclass
class Component:
    category: str
    metric: str
    value: float | None
    points: float | None
    treatment: str
    reason_code: str | None = None
    band_label: str | None = None
    trend: str | None = None    # the metric's trend verdict (Phase 7)


@dataclass
class Category:
    name: str
    weight: float
    points: float | None        # mean of counted components, 0-10
    contribution: float | None  # points/10 * weight, before rescaling
    components: list[Component] = field(default_factory=list)
    absent_cause: str | None = None


@dataclass
class Score:
    period_end: str
    total_score: float
    grade: int
    grade_uncapped: int
    categories_available: int
    grade_capped: bool
    cap_binding: bool
    categories: list[Category]
    config_fingerprint: str | None = None

    @property
    def absent(self) -> dict:
        """Absent category -> cause, for the explain output's cap line."""
        return {c.name: c.absent_cause for c in self.categories if c.absent_cause}


def band_points(metric: str, value: float, bands: dict) -> float:
    """Band lookup, 0-10.

    One implementation for both directions: at an edge the value takes the
    bucket to the edge's RIGHT, and direction lives entirely in the points
    array. Both documented tables resolve this way — net_debt_to_ebitda at
    exactly 1.0 scores 8 ("1.0-2.0x"), ebit_interest_cover at exactly 8.0
    scores 10 (">= 8.0x") — so no per-direction branching is needed, and the
    two tables serve as this function's fixtures.

    Net cash falls out without a special case: a negative value sits below the
    first edge and takes the top bucket.
    """
    band = bands[metric]
    return float(band["points"][bisect_right(band["edges"], value)])


def band_label(metric: str, value: float, bands: dict) -> str:
    """Human-readable band position, e.g. "band 3 of 6"."""
    band = bands[metric]
    index = bisect_right(band["edges"], value)
    return f"band {index + 1} of {len(band['points'])}"


def grade_for(total: float, grades: dict) -> int:
    """Half-open intervals on the config's lower bounds (D45b): [70, 85) is
    grade 2, so 84.9 is grade 2 and 85.0 is grade 1."""
    bound = max((int(k) for k in grades if int(k) <= total), default=None)
    if bound is None:
        raise ValueError(f"no grade band covers a score of {total}")
    return grades[bound]


def cap_for(categories_scored: int, cap_config: dict) -> int | None:
    """The worst grade a score on N categories may show, or None if uncapped.

    Graduated by N (D46): a 2-of-5 score must not present with the same
    authority as a 4-of-5 one. Keys are the highest N each entry covers.
    """
    applicable = [int(k) for k in cap_config if categories_scored <= int(k)]
    if not applicable:
        return None
    return cap_config[min(applicable)]


def _classify(category: str, metric: str, result, trends=None) -> Component:
    """One metric -> one component, under D45's five treatments."""
    if metric in PENDING_COMPONENTS:
        return Component(category, metric, None, None, NOT_YET_IMPLEMENTED)
    if metric in TREND_COMPONENTS:
        # a trend verdict, not a metric value: INSUFFICIENT_DATA is a data gap
        # rather than a verdict, so it drops and can cap (D50)
        verdict = (trends or {}).get(TREND_COMPONENTS[metric])
        if verdict is None or verdict == "INSUFFICIENT_DATA":
            return Component(category, metric, None, None, DROPPED_GAP,
                             reason_code="INSUFFICIENT_DATA", trend=verdict)
        return Component(category, metric, None, None, SCORED, trend=verdict)
    if result is None:
        # the metric was never produced for this period at all
        return Component(category, metric, None, None, DROPPED_GAP,
                         reason_code="MISSING_METRIC")
    if result.data_status == "CALCULATED":
        return Component(category, metric, result.value, None, SCORED)
    kind = reason_kind(result.reason_code)
    if kind == "EVIDENCE":
        # counted at zero, never dropped: this is the company's real condition
        return Component(category, metric, None, 0.0, EVIDENCE_ZERO,
                         reason_code=result.reason_code)
    if kind == "NEITHER":
        return Component(category, metric, None, None, DROPPED_UNLEVERED,
                         reason_code=result.reason_code)
    return Component(category, metric, None, None, DROPPED_GAP,
                     reason_code=result.reason_code)


def _score_category(name, metrics_by_name, weights, bands, trends=None,
                    trend_points=None) -> Category:
    weight = float(weights[name])
    components = [_classify(name, m, metrics_by_name.get(m), trends)
                  for m in CATEGORIES[name]]
    for c in components:
        # every component carries its own metric's verdict, not only the one
        # scored from a trend — the explain output promises a trend per
        # component, and a metric with no trend says INSUFFICIENT_DATA rather
        # than nothing
        if c.metric not in TREND_COMPONENTS:
            c.trend = (trends or {}).get(c.metric)
        if c.treatment != SCORED:
            continue
        if c.metric in TREND_COMPONENTS:
            c.points = float((trend_points or {})[c.trend])
            c.band_label = c.trend
        else:
            c.points = band_points(c.metric, c.value, bands)
            c.band_label = band_label(c.metric, c.value, bands)

    counted = [c for c in components
               if c.treatment in (SCORED, EVIDENCE_ZERO)]
    if counted:
        points = sum(c.points for c in counted) / len(counted)
        return Category(name, weight, points, points / 10 * weight, components)

    # Absent. The cause decides whether the grade caps (D45): a single
    # contributing gap means the category might have shown something, so
    # fail-safe caps; an all-benign absence does not.
    if any(c.treatment == DROPPED_GAP for c in components):
        cause = CAUSE_GAP
    elif any(c.treatment == DROPPED_UNLEVERED for c in components):
        cause = CAUSE_UNLEVERED
    else:
        cause = CAUSE_NOT_IMPLEMENTED
    return Category(name, weight, None, None, components, absent_cause=cause)


def score_period(period_end, metrics_by_name, thresholds=None,
                 fingerprint=None, trends=None) -> Score | None:
    """One period's score, or None when no category could be scored at all."""
    if thresholds is None:
        thresholds = config.thresholds()
    weights, bands, grades = (thresholds["weights"], thresholds["bands"],
                              thresholds["grades"])
    cap_config = thresholds["max_grade_by_categories_scored"]

    trend_points = thresholds["trend_points"]
    categories = [_score_category(name, metrics_by_name, weights, bands,
                                  trends, trend_points)
                  for name in CATEGORIES]
    scored = [c for c in categories if c.points is not None]
    if not scored:
        return None

    # One rescale, whatever the cause of an absence: the methodology's
    # "rescaled over the available categories" and "weight redistributed pro
    # rata" are the same arithmetic, and two mechanisms could drift (D45).
    available_weight = sum(c.weight for c in scored)
    total = sum(c.contribution for c in scored) / available_weight * 100
    uncapped = grade_for(total, grades)

    # Only a GAP-caused absence caps. NEITHER redistributes silently; a
    # not-yet-implemented component never empties a category on its own.
    caps = any(c.absent_cause == CAUSE_GAP for c in categories)
    cap = cap_for(len(scored), cap_config) if caps else None
    grade = max(uncapped, cap) if cap is not None else uncapped

    return Score(
        period_end=period_end, total_score=total, grade=grade,
        grade_uncapped=uncapped, categories_available=len(scored),
        grade_capped=cap is not None, cap_binding=grade != uncapped,
        categories=categories, config_fingerprint=fingerprint,
    )


def score_company(metrics_report, integrity_report, thresholds=None,
                  fingerprint=None, trend_report=None):
    """Every scoreable period. Integrity-FAIL periods get no score at all.

    A FAIL period is excluded from scoring until the underlying data is
    corrected and re-ingested (D45); v1 has no review path, so there is
    nothing to store for it.
    """
    failed = {r.period_end for r in integrity_report.results
              if r.outcome == "FAIL"}
    by_period = {}
    for m in metrics_report.metrics:
        by_period.setdefault(m.end, {})[m.metric] = m

    scores = []
    for end in sorted(by_period):
        if end in failed:
            continue
        trends = None
        if trend_report is not None:
            trends = {t.metric: t.verdict for t in trend_report.trends
                      if t.period_end == end}
        score = score_period(end, by_period[end], thresholds, fingerprint,
                             trends)
        if score is not None:
            scores.append(score)
    return scores


# ---------------------------------------------------------------------------
# explain output


def _cap_line(score: Score) -> str:
    """The line that must never be omitted.

    Capped grades are systematic rather than exceptional — four of five
    demonstration companies can never produce a five-category score — so a
    capped grade must never read as a judged one. Built from stored fields so
    a consumer cannot leave it out by accident.
    """
    if not score.grade_capped:
        return f"Grade {score.grade} (scored on all 5 categories)"
    absent = ", ".join(f"{name} [{cause}]"
                       for name, cause in sorted(score.absent.items()))
    binding = (f"capped; uncapped {score.grade_uncapped}"
               if score.cap_binding else "capped, not binding")
    return (f"Grade {score.grade} ({binding}; scored on "
            f"{score.categories_available} of 5 — missing: {absent})")


def explain(score: Score) -> dict:
    """The explain output the methodology requires for every score."""
    scored = [c for c in score.categories if c.points is not None]
    by_strength = sorted(scored, key=lambda c: c.points, reverse=True)
    # "strongest two, weakest two" assumes enough categories for the two lists
    # to be disjoint. On a thin score they are not — with 2 scored categories,
    # top-two and bottom-two are the same pair, and a category listed as both
    # strongest and weakest is nonsense. Take at most half each way.
    n_each = min(2, len(scored) // 2)

    drivers = []
    for c in scored:
        for comp in c.components:
            if comp.points is None:
                continue
            lost = (10 - comp.points) / 10 * c.weight / len(
                [x for x in c.components if x.points is not None])
            drivers.append((lost, c.name, comp))

    mitigants = [f"{comp.metric} (top band)"
                 for c in scored for comp in c.components
                 if comp.points == 10]

    return {
        "period_end": score.period_end,
        "headline": _cap_line(score),
        "total_score": round(score.total_score, 1),
        "grade": score.grade,
        "grade_uncapped": score.grade_uncapped,
        "categories_available": score.categories_available,
        "absent_categories": score.absent,
        "categories": [
            {
                "category": c.name, "weight": c.weight,
                "points": None if c.points is None else round(c.points, 2),
                "contribution": (None if c.contribution is None
                                 else round(c.contribution, 2)),
                "absent_cause": c.absent_cause,
                "components": [
                    {
                        "metric": comp.metric, "value": comp.value,
                        "band": comp.band_label, "points": comp.points,
                        "treatment": comp.treatment,
                        "reason_code": comp.reason_code,
                        "trend": comp.trend,
                    }
                    for comp in c.components
                ],
            }
            for c in score.categories
        ],
        "strongest": [c.name for c in by_strength[:n_each]],
        "weakest": ([c.name for c in reversed(by_strength[-n_each:])]
                    if n_each else []),
        "positive_mitigants": mitigants,
        "top_drivers": [
            {"category": cat, "metric": comp.metric,
             "points": comp.points, "points_lost": round(lost, 2)}
            for lost, cat, comp in sorted(drivers, key=lambda d: -d[0])[:3]
        ],
        "deteriorating_metrics": sorted(
            {comp.metric for c in score.categories for comp in c.components
             if comp.trend == "Deteriorating"}),
        "disclaimer": (
            "Internal analytical grade for this project. Not a credit rating; "
            "never mapped to S&P, Moody's, Fitch or any bank's internal scale."
        ),
    }
