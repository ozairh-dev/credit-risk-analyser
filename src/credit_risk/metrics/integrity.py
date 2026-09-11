"""Integrity checks (Task 10, docs/credit-methodology.md "Integrity checks").

Runs after composites, because three checks read composite values. Each check
produces exactly one IntegrityResult per period with one of four outcomes:

    PASS  the comparison ran and held
    WARN  it ran and did not hold, but the methodology says do not reject
    FAIL  it ran and did not hold; the period is excluded from scoring
    SKIP  an input was UNAVAILABLE, so the comparison could not run

SKIP is first-class on purpose (D39): a company whose inputs never resolved
must not look as clean as one that genuinely passed. That is D9's
evidence-versus-gap split, and it is what makes witness coverage measurable.

Abnormal movement is the one check that does not live here as a stored result
— it is per-concept and warn-only, so it stays in data_quality_events under
D23's three codes (D37).
"""

from dataclasses import dataclass
from datetime import date

from credit_risk import config
from credit_risk.normalise.quality import DataQualityEvent

PASS, WARN, FAIL, SKIP = "PASS", "WARN", "FAIL", "SKIP"

# D23's 16 core concepts for the abnormal-movement check — not all 34.
CORE_CONCEPTS = (
    "total_debt", "net_debt", "ebitda", "fcf",
    "revenue", "ebit", "d_and_a", "interest_expense", "cash",
    "total_assets", "total_liabilities", "equity",
    "current_assets", "current_liabilities", "cfo", "capex",
)

ABNORMAL_MOVEMENT = "ABNORMAL_MOVEMENT"
ABNORMAL_SIGN_CHANGE = "ABNORMAL_SIGN_CHANGE"
ABNORMAL_FROM_ZERO = "ABNORMAL_FROM_ZERO"

INTEGRITY_CHECKS = (
    "balance_sheet_balances",
    "current_assets_subset",
    "current_liabilities_subset",
    "cash_subset",
    "debt_subset",
    "revenue_non_negative",
    "period_continuity",
)


@dataclass
class IntegrityResult:
    check_name: str
    period_end: str
    outcome: str                       # PASS | WARN | FAIL | SKIP
    detail: str | None = None
    lhs: float | None = None
    rhs: float | None = None
    deviation: float | None = None


@dataclass
class IntegrityReport:
    results: list[IntegrityResult]
    events: list[DataQualityEvent]     # abnormal-movement flags (D23)


def _skip(check, end, missing):
    return IntegrityResult(check, end, SKIP,
                           detail=f"input UNAVAILABLE: {', '.join(missing)}")


def _missing(values, *names):
    return [n for n in names if n not in values]


def _subset_check(check, end, values, smaller, larger, on_failure=FAIL):
    """`smaller <= larger`, skipping when either input is UNAVAILABLE."""
    gone = _missing(values, smaller, larger)
    if gone:
        return _skip(check, end, gone)
    a, b = values[smaller], values[larger]
    ok = a <= b
    return IntegrityResult(
        check, end, PASS if ok else on_failure,
        detail=None if ok else f"{smaller}={a:,.0f} exceeds {larger}={b:,.0f}",
        lhs=a, rhs=b,
    )


def _balance_sheet(end, values, tolerance):
    gone = _missing(values, "total_assets", "total_liabilities", "equity")
    if gone:
        return _skip("balance_sheet_balances", end, gone)
    assets = values["total_assets"]
    if assets <= 0:
        # rule 4: a zero or negative denominator never produces a number (D39a)
        return IntegrityResult("balance_sheet_balances", end, SKIP,
                               detail="ZERO_DENOMINATOR: total_assets is not positive")
    claimed = values["total_liabilities"] + values["equity"]
    deviation = abs(assets - claimed) / assets
    ok = deviation <= tolerance
    return IntegrityResult(
        "balance_sheet_balances", end, PASS if ok else WARN,
        detail=None if ok else (
            f"total_assets={assets:,.0f} vs liabilities+equity={claimed:,.0f} "
            f"deviates {deviation:.2%} > {tolerance:.0%}"
        ),
        lhs=assets, rhs=claimed, deviation=deviation,
    )


def _revenue_non_negative(end, values):
    if "revenue" not in values:
        return _skip("revenue_non_negative", end, ["revenue"])
    revenue = values["revenue"]
    ok = revenue >= 0
    return IntegrityResult(
        "revenue_non_negative", end, PASS if ok else FAIL,
        detail=None if ok else f"revenue={revenue:,.0f} is negative",
        lhs=revenue, rhs=0.0,
    )


def _continuity(ends, window):
    """Consecutive periods by day-gap between period ends, never by calendar
    year (D36): a 52/53-week filer's FY2009 can end 2010-01-03, so calendar
    arithmetic invents gaps that are not there.

    `ends` holds only periods with at least one resolved concept (D40). The
    methodology specifies this check "for trend use" and trends operate on
    concept values, so a period where nothing resolved is not a link in the
    chain. A phantom period between two real ones would otherwise break the
    chain twice, reporting two consecutive fiscal years as discontinuous.

    The earliest period has no predecessor, so it cannot be discontinuous —
    it is SKIP, not a warning.
    """
    low, high = window
    results = []
    for i, end in enumerate(ends):
        if i == 0:
            results.append(IntegrityResult("period_continuity", end, SKIP,
                                           detail="no prior period to compare"))
            continue
        gap = (date.fromisoformat(end) - date.fromisoformat(ends[i - 1])).days
        ok = low <= gap <= high
        results.append(IntegrityResult(
            "period_continuity", end, PASS if ok else WARN,
            detail=None if ok else (
                f"{gap} days since {ends[i - 1]}, outside {low}-{high}; "
                f"trends over this boundary are INSUFFICIENT_DATA"
            ),
            deviation=float(gap),
        ))
    return results


def _abnormal_movements(ends, by_period, threshold):
    """D23's three codes, as data_quality_events rather than stored results.

    A concept UNAVAILABLE in either period is NOT an abnormal movement — it is
    already recorded as a data gap, so it produces nothing here at all.
    """
    events = []
    for prev_end, end in zip(ends, ends[1:]):
        prev, cur = by_period.get(prev_end, {}), by_period.get(end, {})
        for concept in CORE_CONCEPTS:
            if concept not in prev or concept not in cur:
                continue
            before, after = prev[concept], cur[concept]
            if (before > 0 > after) or (before < 0 < after):
                code, detail = ABNORMAL_SIGN_CHANGE, (
                    f"{concept} {before:,.0f} -> {after:,.0f}: sign change "
                    f"(flagged regardless of magnitude)"
                )
            elif before == 0:
                code, detail = ABNORMAL_FROM_ZERO, (
                    f"{concept} 0 -> {after:,.0f}: prior period is zero, "
                    f"percentage undefined"
                )
            else:
                move = abs(after / before - 1)
                if move <= threshold:
                    continue
                code, detail = ABNORMAL_MOVEMENT, (
                    f"{concept} {before:,.0f} -> {after:,.0f}: "
                    f"{move:.0%} move exceeds {threshold:.0%}"
                )
            events.append(DataQualityEvent(code=code, concept=concept,
                                           period_end=end, detail=detail))
    return events


def run_integrity_checks(mapping, composites, cfg: dict | None = None) -> IntegrityReport:
    """Every check for every period the company has.

    `values` per period holds only concepts with an actual value: mapping's
    REPORTED rows and the CALCULATED composites. An UNAVAILABLE concept is
    absent, which is what makes every check skip rather than fail on it.
    """
    if cfg is None:
        cfg = config.integrity()
    tolerance = cfg["balance_sheet_tolerance"]
    threshold = cfg["abnormal_movement_threshold"]
    window = cfg["continuity_window_days"]

    by_period: dict[str, dict[str, float]] = {}
    for c in mapping.concepts:
        by_period.setdefault(c.end, {})[c.concept] = c.value
    for c in composites:
        if c.data_status == "CALCULATED":
            by_period.setdefault(c.end, {})[c.concept] = c.value
    # periods with no usable value at all still get checked — every check
    # skips, which is the honest record of a period we know nothing about
    for u in mapping.unavailable:
        by_period.setdefault(u.period_end, {})
    ends = sorted(by_period)
    # Continuity runs over trend-eligible periods only: those with at least one
    # resolved concept (D40). Every other check still runs on every period, so
    # a phantom period is recorded as all-SKIP rather than hidden.
    trend_ends = [e for e in ends if by_period[e]]

    results: list[IntegrityResult] = []
    for end in ends:
        values = by_period[end]
        results.append(_balance_sheet(end, values, tolerance))
        results.append(_subset_check("current_assets_subset", end, values,
                                     "current_assets", "total_assets"))
        results.append(_subset_check("current_liabilities_subset", end, values,
                                     "current_liabilities", "total_liabilities"))
        results.append(_subset_check("cash_subset", end, values,
                                     "cash", "current_assets"))
        results.append(_subset_check("debt_subset", end, values,
                                     "total_debt_ex_leases", "total_liabilities"))
        results.append(_revenue_non_negative(end, values))
    results.extend(_continuity(trend_ends, window))
    for end in ends:
        if not by_period[end]:
            results.append(IntegrityResult(
                "period_continuity", end, SKIP,
                detail="no concept resolved for this period; not a trend period",
            ))
    return IntegrityReport(
        results=results,
        events=_abnormal_movements(trend_ends, by_period, threshold),
    )


def period_verdict(results) -> str:
    """FAIL if any check failed, else WARN if any warned, else PASS.

    Derived, never stored (D37): storing it would encode the same invariant in
    two places, and this is the whole derivation.
    """
    outcomes = {r.outcome for r in results}
    if FAIL in outcomes:
        return FAIL
    if WARN in outcomes:
        return WARN
    return PASS
