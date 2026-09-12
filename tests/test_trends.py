"""Phase 7: trend classification and early warnings.

**D43 is a hard requirement for this file, not a reference.** Every trend rule
is sequence-based, and D43 exists because `revenue_growth` cited D40's
phantom-period exclusion without applying it. So there is **one eligibility
test per rule, on that rule's own series**, and **one window test per rule** —
seven and seven, parametrised so a new trended metric cannot be added without
one. A shared test would prove the mechanism works somewhere; it would not
prove it is wired to each rule, which is exactly the gap D43 records.
"""

import pytest

from credit_risk import config
from credit_risk.trends.engine import (
    DETERIORATING,
    IMPROVING,
    INSUFFICIENT_DATA,
    STABLE,
    TRENDED,
    Trend,
    classify,
    compute_trends,
    detect_warnings,
)

TH = config.thresholds()
MAT = TH["trend_materiality"]
RELATIVE = set(MAT["relative"])
WINDOW = config.integrity()["continuity_window_days"]

# three consecutive fiscal years, and a fourth that is a genuine gap away
Y1, Y2, Y3 = "2021-12-31", "2022-12-31", "2023-12-31"
GAP_YEAR = "2026-12-31"      # 1096 days after Y3 — outside the window
PHANTOM = "2023-02-15"       # sits between Y2 and Y3, resolves nothing

# a value series per metric that classifies Stable, so eligibility tests are
# not confounded by the verdict
STABLE_SERIES = {
    "net_debt_to_ebitda": [2.0, 2.05, 2.1],
    "ebit_interest_cover": [5.0, 5.05, 5.1],
    "ebitda_margin": [0.20, 0.201, 0.202],
    "revenue_growth": [0.10, 0.11, 0.12],
    "cash_to_current_liabilities": [0.50, 0.51, 0.52],
    "fcf": [1000.0, 1010.0, 1020.0],
    "total_debt": [5000.0, 5010.0, 5020.0],
}


def series_for(metric, ends, values=None):
    values = values or STABLE_SERIES[metric]
    return {metric: dict(zip(ends, values))}


def verdict(trends, metric, period_end):
    return next(t for t in trends
                if t.metric == metric and t.period_end == period_end)


# =====================================================================
# D43: eligibility, one test per rule, on that rule's own series
# =====================================================================

@pytest.mark.parametrize("metric", sorted(TRENDED))
def test_eligibility_uses_this_rules_own_series(metric):
    """A period where OTHER metrics resolve but this one does not is not a
    link in this metric's chain (D40 applied per rule).

    The phantom period here resolves a different metric entirely. If
    eligibility were computed on "the period" rather than on this series, the
    window would include it and the trend would break.
    """
    ends = [Y1, Y2, PHANTOM, Y3]
    series = series_for(metric, [Y1, Y2, Y3])         # this metric: 3 periods
    series["some_other_metric"] = {PHANTOM: 1.0}      # resolves only there
    trends = compute_trends(series, ends, TH, WINDOW)

    # the window skips the phantom and classifies on Y1..Y3
    t = verdict(trends, metric, Y3)
    assert t.verdict != INSUFFICIENT_DATA, metric
    assert t.window == (Y1, Y2, Y3), metric
    # and the phantom itself is INSUFFICIENT_DATA for this metric, named
    assert verdict(trends, metric, PHANTOM).verdict == INSUFFICIENT_DATA
    assert "does not resolve" in verdict(trends, metric, PHANTOM).reason


@pytest.mark.parametrize("metric", sorted(TRENDED))
def test_window_test_rejects_a_real_gap_for_this_rule(metric):
    """Eligible is not the same as contiguous (D36/D43): three periods that
    all resolve this metric but span a multi-year hole must not classify.
    """
    ends = [Y1, Y2, GAP_YEAR]
    trends = compute_trends(series_for(metric, ends), ends, TH, WINDOW)
    t = verdict(trends, metric, GAP_YEAR)
    assert t.verdict == INSUFFICIENT_DATA, metric
    assert "consecutive" in t.reason, metric


@pytest.mark.parametrize("metric", sorted(TRENDED))
def test_fewer_than_three_periods_is_insufficient_for_this_rule(metric):
    ends = [Y2, Y3]
    trends = compute_trends(series_for(metric, ends, STABLE_SERIES[metric][:2]),
                            ends, TH, WINDOW)
    assert verdict(trends, metric, Y3).verdict == INSUFFICIENT_DATA, metric


def test_every_trended_metric_has_an_eligibility_test():
    """The guard on D43: adding a trended metric without an eligibility test
    must fail here rather than silently inherit someone else's."""
    assert set(STABLE_SERIES) == set(TRENDED)


# =====================================================================
# classification
# =====================================================================

def cls(metric, values):
    return classify(metric, values, MAT, RELATIVE)[0]


def test_absolute_materiality_on_a_one_year_change():
    # leverage rising 2.0 -> 2.6 is +0.6, material at 0.5
    assert cls("net_debt_to_ebitda", [2.0, 2.0, 2.6]) == DETERIORATING
    # +0.4 is not
    assert cls("net_debt_to_ebitda", [2.0, 2.0, 2.4]) == STABLE


def test_direction_decides_which_verdict_a_material_change_earns():
    # falling leverage is good; falling cover is bad
    assert cls("net_debt_to_ebitda", [3.0, 3.0, 2.4]) == IMPROVING
    assert cls("ebit_interest_cover", [5.0, 5.0, 3.5]) == DETERIORATING
    assert cls("ebit_interest_cover", [3.5, 3.5, 5.0]) == IMPROVING


def test_window_change_needs_monotonicity():
    """A material change across the window that is not monotonic stays Stable:
    the methodology requires each year worse than the last."""
    # 2.0 -> 2.9 -> 2.7: window change +0.7 material, but the series fell in
    # the last step, so it is not monotonic. change_1y is -0.2, immaterial.
    assert cls("net_debt_to_ebitda", [2.0, 2.9, 2.7]) == STABLE
    # monotonic and material, with an immaterial final step
    assert cls("net_debt_to_ebitda", [2.0, 2.4, 2.7]) == DETERIORATING


def test_monotonic_is_strict_a_flat_year_breaks_it():
    """D49: a stalled series is not 'each year worse than the last'.

    Both cases are chosen so the ONE-YEAR change is immaterial (0.0 and 0.2,
    below 0.5) and only the window rule can fire — otherwise the 1y rule
    decides first and monotonicity is never consulted.
    """
    # window change +0.6 is material, but the second step is flat
    assert cls("net_debt_to_ebitda", [2.0, 2.6, 2.6]) == STABLE
    # same window change, strictly monotonic
    assert cls("net_debt_to_ebitda", [2.0, 2.4, 2.6]) == DETERIORATING


def test_relative_materiality_is_a_proportion_of_the_base():
    # fcf 1000 -> 700 is -30%, material at 20%
    assert cls("fcf", [1000.0, 1000.0, 700.0]) == DETERIORATING
    # -10% is not
    assert cls("fcf", [1000.0, 1000.0, 900.0]) == STABLE
    # total_debt +20% is material at 15%, and rising is bad
    assert cls("total_debt", [5000.0, 5000.0, 6000.0]) == DETERIORATING


def test_absolute_and_relative_metrics_are_not_confused():
    """A 0.6 absolute change is material for leverage; the same 0.6 on a
    relative metric is a rounding error."""
    assert cls("net_debt_to_ebitda", [2.0, 2.0, 2.6]) == DETERIORATING
    assert cls("fcf", [1000.0, 1000.0, 1000.6]) == STABLE


def test_relative_change_with_a_zero_base_refuses():
    """D34's shape: an undefined proportion is refused, not computed."""
    assert cls("fcf", [0.0, 0.0, 500.0]) == INSUFFICIENT_DATA
    assert cls("total_debt", [0.0, 100.0, 200.0]) == INSUFFICIENT_DATA


def test_revenue_growth_has_an_absolute_clause_the_others_lack():
    """D49: negative growth is Deteriorating regardless of direction of
    travel — growth improving from -20% to -5% is still negative growth."""
    assert cls("revenue_growth", [-0.20, -0.10, -0.05]) == DETERIORATING
    # positive and rising is Improving, on the shared change rule
    assert cls("revenue_growth", [0.02, 0.05, 0.12]) == IMPROVING


def test_revenue_growth_change_is_an_acceleration():
    """Its change_1y compares growth RATES, so a fall from 12% to 4% growth is
    an 8pp deceleration — material at 5pp — while revenue still grew."""
    v, d1, _, _ = classify("revenue_growth", [0.12, 0.12, 0.04], MAT, RELATIVE)
    assert v == DETERIORATING
    assert d1 == pytest.approx(-0.08)


# =====================================================================
# warnings and escalation
# =====================================================================

def trend_rows(period_end, **verdicts):
    return [Trend(metric, period_end, v, change_1y=1.0, window=(Y1, Y2, Y3))
            for metric, v in verdicts.items()]


def fire(period_end, trends, series):
    return detect_warnings(trends, series, [period_end], {}, TH)


def test_each_trend_warning_fires_on_deterioration_only():
    for metric, indicator in (
        ("net_debt_to_ebitda", "leverage_deterioration"),
        ("ebit_interest_cover", "coverage_deterioration"),
        ("fcf", "cash_flow_deterioration"),
        ("ebitda_margin", "margin_deterioration"),
        ("revenue_growth", "revenue_deterioration"),
        ("cash_to_current_liabilities", "liquidity_deterioration"),
        ("total_debt", "debt_increase"),
    ):
        bad = fire(Y3, trend_rows(Y3, **{metric: DETERIORATING}), {})
        assert [w.indicator for w in bad] == [indicator], metric
        for verdict_ in (IMPROVING, STABLE, INSUFFICIENT_DATA):
            quiet = fire(Y3, trend_rows(Y3, **{metric: verdict_}), {})
            assert quiet == [], (metric, verdict_)


def test_base_severities_match_the_methodology():
    expected = {
        "leverage_deterioration": "Medium", "coverage_deterioration": "Medium",
        "cash_flow_deterioration": "Medium", "margin_deterioration": "Low",
        "revenue_deterioration": "Low", "liquidity_deterioration": "Medium",
        "debt_increase": "Low",
    }
    for metric, indicator in (
        ("net_debt_to_ebitda", "leverage_deterioration"),
        ("ebit_interest_cover", "coverage_deterioration"),
        ("fcf", "cash_flow_deterioration"),
        ("ebitda_margin", "margin_deterioration"),
        ("revenue_growth", "revenue_deterioration"),
        ("cash_to_current_liabilities", "liquidity_deterioration"),
        ("total_debt", "debt_increase"),
    ):
        w = fire(Y3, trend_rows(Y3, **{metric: DETERIORATING}), {})[0]
        assert w.base_severity == expected[indicator], indicator


def test_the_four_level_warnings():
    cases = [
        ({"fcf": {Y3: -1.0}}, "negative_fcf", "Medium"),
        ({"ebitda": {Y3: 0.0}}, "negative_ebitda", "High"),
        ({"equity": {Y3: -5.0}}, "negative_equity", "High"),
        ({"ebit_interest_cover": {Y3: 1.9}}, "coverage_below_2x", "High"),
    ]
    for series, indicator, severity in cases:
        fired = fire(Y3, [], series)
        assert [w.indicator for w in fired] == [indicator]
        assert fired[0].base_severity == severity


def test_level_warning_boundaries():
    assert fire(Y3, [], {"fcf": {Y3: 0.0}}) == []            # < 0, not <= 0
    assert fire(Y3, [], {"ebitda": {Y3: 0.0}})               # <= 0 fires
    assert fire(Y3, [], {"ebit_interest_cover": {Y3: 2.0}}) == []   # < 2.0
    assert fire(Y3, [], {"ebit_interest_cover": {Y3: 1.99}})


def test_a_missing_input_fires_nothing():
    """A level warning must not fire on absence — that would read a data gap
    as a finding."""
    assert fire(Y3, [], {"equity": {}}) == []
    assert fire(Y3, [], {}) == []


def test_escalation_raises_every_warning_one_level_and_records_why():
    series = {"fcf": {Y3: -1.0}, "ebitda": {Y3: -2.0}, "equity": {Y3: -3.0}}
    fired = fire(Y3, [], series)
    assert len(fired) == 3
    for w in fired:
        assert w.escalated and w.warnings_in_period == 3
        assert "3 warnings fired" in w.escalation_reason
        assert "threshold of 3" in w.escalation_reason
    severities = {w.indicator: (w.base_severity, w.severity) for w in fired}
    assert severities["negative_fcf"] == ("Medium", "High")
    assert severities["negative_ebitda"] == ("High", "High")   # High stays High


def test_two_warnings_do_not_escalate():
    series = {"fcf": {Y3: -1.0}, "equity": {Y3: -3.0}}
    fired = fire(Y3, [], series)
    assert len(fired) == 2
    assert not any(w.escalated for w in fired)
    assert all(w.severity == w.base_severity for w in fired)
    assert all(w.escalation_reason is None for w in fired)


def test_escalation_is_one_level_not_to_the_top():
    """Low -> Medium, not Low -> High."""
    trends = trend_rows(Y3, ebitda_margin=DETERIORATING,
                        revenue_growth=DETERIORATING, total_debt=DETERIORATING)
    fired = fire(Y3, trends, {})
    assert len(fired) == 3
    assert all(w.base_severity == "Low" and w.severity == "Medium"
               for w in fired)


def test_escalation_counts_across_both_warning_kinds():
    """Two trend warnings plus one level warning still reaches the threshold."""
    trends = trend_rows(Y3, ebitda_margin=DETERIORATING,
                        revenue_growth=DETERIORATING)
    fired = fire(Y3, trends, {"equity": {Y3: -1.0}})
    assert len(fired) == 3
    assert all(w.escalated for w in fired)


# =====================================================================
# the trend fingerprint (D52)
# =====================================================================

def test_trend_fingerprint_covers_trend_settings_only():
    from credit_risk.trends.fingerprint import (
        FINGERPRINTED_KEYS, trend_config_values, trend_fingerprint)
    assert set(trend_config_values()) == set(FINGERPRINTED_KEYS)
    # trend_points moves scores, so it belongs to the score fingerprint
    assert "trend_points" not in FINGERPRINTED_KEYS


def test_trend_fingerprint_moves_when_a_materiality_threshold_moves():
    """A warning that stopped firing because a threshold moved must be
    distinguishable from one that stopped because the company improved."""
    from credit_risk.trends.fingerprint import trend_config_values, trend_fingerprint
    base = dict(trend_config_values())
    moved = {**base, "trend_materiality": {**base["trend_materiality"],
                                           "net_debt_to_ebitda": 1.0}}
    assert trend_fingerprint(base) != trend_fingerprint(moved)
    escalation = {**base, "warning_escalation_count": 4}
    assert trend_fingerprint(base) != trend_fingerprint(escalation)
