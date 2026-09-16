"""Phase 6: the scoring engine, every rule with a hand-computed expected value.

The band tests are pinned to the two tables printed in the methodology, edge
values included — those tables are the specification, so they are the fixtures.
The missing-data tests assert each of D45's five treatments and every branch of
the category-outcome rule, including the two interactions that were specified
precisely because they are easy to get wrong: a mixed-kind category, and a
period where capping and redistribution both apply.
"""

import pytest

from credit_risk.metrics.ratios import MetricResult
from credit_risk.scoring.engine import (
    CAUSE_GAP,
    CAUSE_UNLEVERED,
    DROPPED_GAP,
    DROPPED_UNLEVERED,
    EVIDENCE_ZERO,
    NOT_YET_IMPLEMENTED,
    SCORED,
    band_points,
    cap_for,
    explain,
    grade_for,
    score_period,
)
from credit_risk.scoring.fingerprint import (
    FINGERPRINTED_KEYS,
    score_config_values,
    score_fingerprint,
)
from credit_risk import config

END = "2023-12-31"
TH = config.thresholds()
BANDS, GRADES = TH["bands"], TH["grades"]
CAPS = TH["max_grade_by_categories_scored"]


def ok(metric, value):
    return MetricResult(metric=metric, end=END, value=value,
                        method="m", data_status="CALCULATED")


def bad(metric, reason):
    return MetricResult(metric=metric, end=END, value=None, method=None,
                        data_status="UNAVAILABLE", reason_code=reason)


def by(*results):
    return {r.metric: r for r in results}


def cat(score, name):
    return next(c for c in score.categories if c.name == name)


def comp(score, name, metric):
    return next(c for c in cat(score, name).components if c.metric == metric)


# ============ band lookup: the two documented tables, edges included ============

@pytest.mark.parametrize("value,points", [
    (-2.0, 10),    # net cash
    (0.5, 10),     # < 1.0x  Very low
    (1.0, 8),      # exactly an edge -> the bucket to its right
    (1.5, 8),      # 1.0-2.0x  Low
    (2.0, 6), (2.5, 6),          # 2.0-3.0x  Moderate
    (3.0, 4), (3.9, 4),          # 3.0-4.0x  Elevated
    (4.0, 2), (4.9, 2),          # 4.0-5.0x  High
    (5.0, 0), (12.0, 0),         # >= 5.0x   Very high
])
def test_net_debt_to_ebitda_band_table(value, points):
    """The methodology's printed table, value by value."""
    assert band_points("net_debt_to_ebitda", value, BANDS) == points


@pytest.mark.parametrize("value,points", [
    (0.5, 0), (0.99, 0),         # < 1.0x
    (1.0, 2), (2.4, 2),          # 1.0-2.5x
    (2.5, 4), (4.9, 4),          # 2.5-5.0x
    (5.0, 6), (9.9, 6),          # 5.0-10.0x
    (10.0, 8), (19.9, 8),        # 10.0-20.0x
    (20.0, 10), (6307.0, 10),    # >= 20.0x  (max observed: 6,307x)
])
def test_ebit_interest_cover_band_table(value, points):
    """Higher-is-better resolves the same way: direction lives in the points
    array, not in the comparison."""
    assert band_points("ebit_interest_cover", value, BANDS) == points


def test_every_banded_metric_has_one_more_point_than_edges():
    for metric, band in BANDS.items():
        assert len(band["points"]) == len(band["edges"]) + 1, metric


# ============ grades: half-open on the lower bound (D45b) ============

@pytest.mark.parametrize("score,grade", [
    (100.0, 1), (85.0, 1),
    (84.9, 2), (70.0, 2),
    (69.9, 3), (55.0, 3),
    (54.9, 4), (40.0, 4),
    (39.9, 5), (25.0, 5),
    (24.9, 6), (0.0, 6),
])
def test_grade_boundaries_are_half_open(score, grade):
    assert grade_for(score, GRADES) == grade


# ============ the graduated cap (D46) ============

@pytest.mark.parametrize("n,cap", [(0, 4), (1, 4), (2, 4), (3, 3), (4, 3), (5, None)])
def test_cap_is_graduated_by_categories_scored(n, cap):
    assert cap_for(n, CAPS) == cap


# ============ the five treatments (D45) ============

def test_scored_component_takes_band_points():
    s = score_period(END, by(ok("net_debt_to_ebitda", 1.5),
                             ok("debt_to_capital", 0.1)), TH)
    assert comp(s, "leverage", "net_debt_to_ebitda").treatment == SCORED
    # (8 + 10) / 2 = 9
    assert cat(s, "leverage").points == 9.0


def test_evidence_scores_zero_and_is_counted_not_dropped():
    """Negative EBITDA is a finding, not a hole: it pulls the mean down."""
    s = score_period(END, by(bad("net_debt_to_ebitda", "NEGATIVE_EBITDA"),
                             ok("debt_to_capital", 0.1)), TH)
    c = comp(s, "leverage", "net_debt_to_ebitda")
    assert c.treatment == EVIDENCE_ZERO and c.points == 0.0
    # (0 + 10) / 2 = 5 — dropping it would have given 10
    assert cat(s, "leverage").points == 5.0


def test_gap_is_dropped_from_the_mean():
    s = score_period(END, by(bad("net_debt_to_ebitda", "MISSING_INPUT:ebitda"),
                             ok("debt_to_capital", 0.1)), TH)
    assert comp(s, "leverage", "net_debt_to_ebitda").treatment == DROPPED_GAP
    assert cat(s, "leverage").points == 10.0        # mean of what remains
    assert cat(s, "leverage").absent_cause is None  # still scored


def test_unlevered_component_is_dropped_benignly():
    s = score_period(END, by(bad("fcf_to_debt", "NO_DEBT"),
                             ok("fcf_margin", 0.20)), TH)
    assert comp(s, "cash_flow", "fcf_to_debt").treatment == DROPPED_UNLEVERED
    # scored on fcf_margin alone; the unlevered component neither counts nor
    # marks the category gap-touched (the other categories here are absent for
    # unrelated reasons, so the score-level cap is not what this asserts)
    assert cat(s, "cash_flow").points == 10.0
    assert cat(s, "cash_flow").absent_cause is None


def test_nothing_is_pending_now_that_phase_7_has_landed():
    """The not_yet_implemented mechanism survives with an empty set: it is what
    lets a future component join the row shape before it can be scored, and its
    emptiness is the record that nothing is currently pending."""
    from credit_risk.scoring.engine import PENDING_COMPONENTS
    assert PENDING_COMPONENTS == frozenset()


def test_trend_component_scores_from_a_verdict(  ):
    """The transition Phase 6 was designed for: the row shape does not change,
    only the treatment and the points (D50)."""
    s = score_period(END, by(ok("revenue_growth", 0.12)), TH,
                     trends={"ebitda_margin": "Stable"})
    c = comp(s, "business_performance", "ebitda_margin_trend")
    assert c.treatment == SCORED
    assert c.points == 6.0          # Stable, just above the midpoint
    assert c.trend == "Stable"
    assert cat(s, "business_performance").points == 8.0     # (10 + 6) / 2


@pytest.mark.parametrize("verdict,points", [
    ("Improving", 10.0), ("Stable", 6.0), ("Deteriorating", 0.0)])
def test_trend_points_mapping(verdict, points):
    s = score_period(END, by(ok("revenue_growth", 0.12)), TH,
                     trends={"ebitda_margin": verdict})
    assert comp(s, "business_performance", "ebitda_margin_trend").points == points


def test_insufficient_trend_data_is_a_gap_not_a_verdict():
    s = score_period(END, by(ok("revenue_growth", 0.12)), TH,
                     trends={"ebitda_margin": "INSUFFICIENT_DATA"})
    c = comp(s, "business_performance", "ebitda_margin_trend")
    assert c.treatment == DROPPED_GAP
    assert c.reason_code == "INSUFFICIENT_DATA"
    assert cat(s, "business_performance").points == 10.0    # scored on growth alone


def test_a_company_with_no_trends_at_all_gaps_the_component():
    """JNJ and KHC's shape: ebitda_margin never resolves, so the trend can
    never exist — a data gap where Phase 6 previously excluded it entirely."""
    s = score_period(END, by(ok("revenue_growth", 0.12)), TH, trends={})
    assert comp(s, "business_performance",
                "ebitda_margin_trend").treatment == DROPPED_GAP


# ============ the category-outcome rule, including the two interactions ============

def test_mixed_kind_category_scores_on_what_counts():
    """A gap beside an evidence-zero: the category still scores, on the
    evidence-zero alone. This is LUMN's cash-flow shape."""
    s = score_period(END, by(bad("fcf_to_debt", "MISSING_INPUT:fcf"),
                             bad("fcf_margin", "NEGATIVE_EBITDA")), TH)
    c = cat(s, "cash_flow")
    assert c.points == 0.0 and c.absent_cause is None


def test_category_emptied_by_a_gap_caps_the_grade():
    s = score_period(END, by(
        ok("net_debt_to_ebitda", 0.5), ok("debt_to_capital", 0.1),
        ok("ebit_interest_cover", 20.0),
        ok("current_ratio", 3.0), ok("cash_to_current_liabilities", 1.0),
        ok("fcf_to_debt", 0.5), ok("fcf_margin", 0.3),
        bad("revenue_growth", "INSUFFICIENT_DATA"),     # empties the category
    ), TH)
    assert cat(s, "business_performance").absent_cause == CAUSE_GAP
    assert s.categories_available == 4
    assert s.grade_uncapped == 1 and s.grade == 3       # capped at N=4
    assert s.grade_capped and s.cap_binding


def test_category_emptied_benignly_redistributes_without_capping():
    """An unlevered company must not be penalised for having no debt."""
    s = score_period(END, by(
        ok("net_debt_to_ebitda", 0.5), ok("debt_to_capital", 0.1),
        bad("ebit_interest_cover", "NO_INTEREST_NO_DEBT"),   # empties coverage
        ok("current_ratio", 3.0), ok("cash_to_current_liabilities", 1.0),
        bad("fcf_to_debt", "NO_DEBT"), ok("fcf_margin", 0.3),
        ok("revenue_growth", 0.2),
    ), TH)
    assert cat(s, "coverage").absent_cause == CAUSE_UNLEVERED
    assert s.categories_available == 4
    assert not s.grade_capped
    assert s.total_score == 100.0 and s.grade == 1      # rescaled over 80 weight


def test_cap_and_redistribution_together_cap_once():
    """One rescale; the cap applies once, from the GAP absence, and is a
    ceiling rather than something that stacks."""
    s = score_period(END, by(
        ok("net_debt_to_ebitda", 0.5), ok("debt_to_capital", 0.1),
        bad("ebit_interest_cover", "NO_INTEREST_NO_DEBT"),   # NEITHER absence
        ok("current_ratio", 3.0), ok("cash_to_current_liabilities", 1.0),
        bad("fcf_to_debt", "MISSING_INPUT:fcf"),
        bad("fcf_margin", "MISSING_INPUT:fcf"),              # GAP absence
        ok("revenue_growth", 0.2),
    ), TH)
    assert cat(s, "coverage").absent_cause == CAUSE_UNLEVERED
    assert cat(s, "cash_flow").absent_cause == CAUSE_GAP
    assert s.categories_available == 3
    assert s.total_score == 100.0                        # rescaled over 60
    assert s.grade_uncapped == 1 and s.grade == 3        # N=3 -> cap 3, once


def test_a_thin_score_caps_harder_than_a_nearly_complete_one():
    """D46's whole point, asserted directly: same score, different N."""
    thin = score_period(END, by(ok("ebit_interest_cover", 20.0)), TH)
    assert thin.categories_available == 1
    assert thin.total_score == 100.0
    assert thin.grade == 4          # N <= 2
    assert thin.grade_uncapped == 1


def test_no_scoreable_category_produces_no_score_at_all():
    s = score_period(END, by(bad("revenue_growth", "MISSING_INPUT:revenue")), TH)
    assert s is None


# ============ the fingerprint (D45 question 3) ============

def test_fingerprint_covers_the_allowlist_and_nothing_else():
    assert set(score_config_values()) == set(FINGERPRINTED_KEYS)
    # trend and warning settings move Phase 7 output, never a score
    assert "trend_materiality" not in FINGERPRINTED_KEYS
    assert "warning_escalation_count" not in FINGERPRINTED_KEYS


def test_fingerprint_moves_when_a_band_edge_moves():
    base = dict(score_config_values())
    moved = {**base, "bands": {**base["bands"],
                               "net_debt_to_ebitda": {
                                   **base["bands"]["net_debt_to_ebitda"],
                                   "edges": [1.5, 2.0, 3.0, 4.0, 5.0]}}}
    assert score_fingerprint(base) != score_fingerprint(moved)


def test_fingerprint_moves_when_a_weight_or_grade_boundary_moves():
    base = dict(score_config_values())
    assert score_fingerprint(base) != score_fingerprint(
        {**base, "weights": {**base["weights"], "leverage": 30}})
    assert score_fingerprint(base) != score_fingerprint(
        {**base, "grades": {**base["grades"], 85: 2}})


def test_fingerprint_is_stable_and_order_independent():
    assert score_fingerprint() == score_fingerprint()
    assert score_fingerprint({"a": 1, "b": 2}) == score_fingerprint({"b": 2, "a": 1})


def test_missing_scoring_setting_raises():
    with pytest.raises(KeyError, match="grades"):
        score_config_values({"weights": {}, "bands": {},
                             "max_grade_by_categories_scored": {}})


# ============ explain output ============

def full_score():
    return score_period(END, by(
        ok("net_debt_to_ebitda", 2.5), ok("debt_to_capital", 0.3),
        ok("ebit_interest_cover", 9.0),
        ok("current_ratio", 0.5), ok("cash_to_current_liabilities", 0.05),
        ok("fcf_to_debt", 0.08), ok("fcf_margin", 0.04),
        ok("revenue_growth", 0.12),
    ), TH)


def test_explain_headline_states_the_cap_or_its_absence():
    assert "scored on all 5 categories" in explain(full_score())["headline"]
    thin = score_period(END, by(ok("ebit_interest_cover", 20.0)), TH)
    head = explain(thin)["headline"]
    assert "capped" in head and "uncapped 1" in head and "1 of 5" in head
    assert "leverage [data_gap]" in head


def test_explain_lists_every_category_with_contributions():
    report = explain(full_score())
    assert len(report["categories"]) == 5
    leverage = next(c for c in report["categories"] if c["category"] == "leverage")
    assert leverage["points"] == 7.0          # (6 + 8) / 2
    assert leverage["contribution"] == 17.5   # 7/10 * 25


def test_explain_strongest_and_weakest_never_overlap():
    """With few categories, top-two and bottom-two would name the same one."""
    thin = score_period(END, by(ok("ebit_interest_cover", 20.0),
                                ok("current_ratio", 3.0),
                                ok("cash_to_current_liabilities", 1.0)), TH)
    report = explain(thin)
    assert not set(report["strongest"]) & set(report["weakest"])


def test_explain_top_drivers_are_the_three_costliest():
    report = explain(full_score())
    drivers = report["top_drivers"]
    assert len(drivers) == 3
    # liquidity is bottom-banded twice here, so it must dominate
    assert {d["metric"] for d in drivers} >= {"current_ratio",
                                              "cash_to_current_liabilities"}
    assert drivers[0]["points_lost"] >= drivers[-1]["points_lost"]


def test_explain_carries_real_trends_per_component():
    """Phase 6 promised a trend field per component and filled it with null.
    Phase 7 fills it for real, and the output shape is unchanged."""
    s = score_period(END, by(
        ok("net_debt_to_ebitda", 2.5), ok("debt_to_capital", 0.3),
        ok("ebit_interest_cover", 9.0),
        ok("current_ratio", 0.5), ok("cash_to_current_liabilities", 0.05),
        ok("fcf_to_debt", 0.08), ok("fcf_margin", 0.04),
        ok("revenue_growth", 0.12),
    ), TH, trends={"net_debt_to_ebitda": "Deteriorating",
                   "ebit_interest_cover": "Improving",
                   "ebitda_margin": "Stable"})
    report = explain(s)
    assert report["deteriorating_metrics"] == ["net_debt_to_ebitda"]
    trends = {c["metric"]: c["trend"] for cat_ in report["categories"]
              for c in cat_["components"]}
    assert trends["net_debt_to_ebitda"] == "Deteriorating"
    assert trends["ebit_interest_cover"] == "Improving"
    assert trends["ebitda_margin_trend"] == "Stable"
    # a metric with no verdict says nothing rather than claiming stability
    assert trends["current_ratio"] is None


def test_explain_carries_the_disclaimer():
    report = explain(full_score())
    assert "Not a credit rating" in report["disclaimer"]
    assert "Moody" in report["disclaimer"]


# ============ the four company shapes docs/build-plan.md requires ============

def test_build_plan_fixture_clean_company():
    s = full_score()
    assert s.categories_available == 5 and not s.grade_capped


def test_build_plan_fixture_unlevered_company():
    """No debt anywhere: coverage and the debt-denominated cash-flow metric
    drop benignly, and the grade is not capped for it."""
    s = score_period(END, by(
        ok("net_debt_to_ebitda", -1.0), ok("debt_to_capital", 0.0),
        bad("ebit_interest_cover", "NO_INTEREST_NO_DEBT"),
        ok("current_ratio", 2.5), ok("cash_to_current_liabilities", 0.9),
        bad("fcf_to_debt", "NO_DEBT"), ok("fcf_margin", 0.2),
        ok("revenue_growth", 0.08),
    ), TH)
    assert cat(s, "coverage").absent_cause == CAUSE_UNLEVERED
    assert not s.grade_capped
    assert s.grade == 1          # net cash + strong everything, uncapped


def test_build_plan_fixture_negative_ebitda_company():
    """Both EBITDA-based leverage metrics refuse on evidence; leverage scores
    0 rather than dropping out, so the company is not flattered."""
    s = score_period(END, by(
        bad("net_debt_to_ebitda", "NEGATIVE_EBITDA"), ok("debt_to_capital", 0.7),
        bad("ebit_interest_cover", "NEGATIVE_EARNINGS"),
        ok("current_ratio", 1.1), ok("cash_to_current_liabilities", 0.15),
        ok("fcf_to_debt", 0.01), ok("fcf_margin", 0.01),
        ok("revenue_growth", -0.4),
    ), TH)
    assert comp(s, "leverage", "net_debt_to_ebitda").treatment == EVIDENCE_ZERO
    assert cat(s, "leverage").points == 1.0        # (0 + 2) / 2
    assert cat(s, "coverage").points == 0.0        # counted, not dropped
    assert not s.grade_capped                      # evidence is not a gap
    assert s.grade == 6


def test_build_plan_fixture_company_missing_interest_expense():
    """A gap, not evidence: coverage empties, the grade caps, and the output
    says which category went missing and why."""
    s = score_period(END, by(
        ok("net_debt_to_ebitda", 0.5), ok("debt_to_capital", 0.1),
        bad("ebit_interest_cover", "INTEREST_MISSING_WITH_DEBT"),
        ok("current_ratio", 3.0), ok("cash_to_current_liabilities", 1.0),
        ok("fcf_to_debt", 0.5), ok("fcf_margin", 0.3),
        ok("revenue_growth", 0.2),
    ), TH)
    assert cat(s, "coverage").absent_cause == CAUSE_GAP
    assert s.categories_available == 4
    assert s.grade_capped and s.cap_binding
    assert s.grade_uncapped == 1 and s.grade == 3
    assert explain(s)["absent_categories"] == {"coverage": CAUSE_GAP}


def test_trend_points_is_in_the_score_fingerprint():
    """D50: the boundary is "does this move a score". trend_points sits beside
    the trend settings in config but moves scores, so it belongs here — this
    test exists because the allowlist and the decision drifted apart once."""
    assert "trend_points" in FINGERPRINTED_KEYS
    base = dict(score_config_values())
    moved = {**base, "trend_points": {**base["trend_points"], "Stable": 5}}
    assert score_fingerprint(base) != score_fingerprint(moved)


def test_trend_settings_stay_out_of_the_score_fingerprint():
    """The other half of the same boundary: these change which warnings fire,
    not what a score is (D52)."""
    assert "trend_materiality" not in FINGERPRINTED_KEYS
    assert "warning_escalation_count" not in FINGERPRINTED_KEYS
