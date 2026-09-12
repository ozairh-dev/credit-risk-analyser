"""Task 11: the three ratios, every formula and every coverage edge case.

Figures are chosen so each expected value is exact mental arithmetic. Every
edge case in the methodology's coverage table is asserted separately, and the
evidence-versus-gap kind is asserted alongside the reason code — the code
alone does not tell Phase 6 how to treat it (D9, D41a).
"""

import pytest

from credit_risk.metrics.composites import CompositeConcept
from credit_risk.metrics.ratios import (
    METRICS,
    EVIDENCE,
    GAP,
    INTEREST_MISSING_WITH_DEBT,
    NEGATIVE_DENOMINATOR,
    NEGATIVE_EARNINGS,
    NEGATIVE_EBITDA,
    NEITHER,
    NO_INTEREST_NO_DEBT,
    ZERO_DENOMINATOR,
    compute_metrics,
    reason_kind,
)
from credit_risk.normalise.mapping import MappedConcept, MappingResult, UnavailableConcept

END = "2023-12-31"


def mc(concept, value, end=END):
    return MappedConcept(
        concept=concept, value=value, unit="USD", source_tag="T", label=None,
        end=end, start=None, fy=2023, fp="FY", form="10-K",
        filed="2024-02-01", accn="0000000000-24-000001", frame=None,
    )


def comp(concept, value, end=END, status="CALCULATED"):
    return CompositeConcept(concept=concept, end=end, value=value, method="m",
                            data_status=status)


def run(concepts=(), composites=(), unavailable=()):
    mapping = MappingResult(concepts=list(concepts),
                            unavailable=list(unavailable), warnings=[])
    report = compute_metrics(mapping, list(composites))
    return {m.metric: m for m in report.metrics}, report


def one(metric, concepts=(), composites=(), unavailable=()):
    metrics, _ = run(concepts, composites, unavailable)
    return metrics[metric]


# ============ reason kinds (D9, D41a) ============

def test_reason_kinds_are_three_not_two():
    assert reason_kind(NEGATIVE_EBITDA) == EVIDENCE
    assert reason_kind(NEGATIVE_EARNINGS) == EVIDENCE
    assert reason_kind(INTEREST_MISSING_WITH_DEBT) == GAP
    assert reason_kind(ZERO_DENOMINATOR) == GAP
    assert reason_kind(NEGATIVE_DENOMINATOR) == GAP
    assert reason_kind("MISSING_INPUT:ebitda") == GAP
    # not a gap: an unlevered company must not cap the grade
    assert reason_kind(NO_INTEREST_NO_DEBT) == NEITHER
    assert reason_kind(None) is None


def test_every_missing_input_variant_is_a_gap():
    for concept in ("net_debt", "ebitda", "ebit", "total_debt",
                    "current_assets", "current_liabilities"):
        assert reason_kind(f"MISSING_INPUT:{concept}") == GAP


# ============ net_debt_to_ebitda ============

def test_net_debt_to_ebitda():
    m = one("net_debt_to_ebitda",
            composites=[comp("net_debt", 500), comp("ebitda", 200)])
    assert m.value == 2.5                       # 500 / 200
    assert m.data_status == "CALCULATED"
    assert m.method == "net_debt / ebitda"
    assert m.inputs == [("net_debt", END), ("ebitda", END)]


def test_net_cash_is_valid_and_reported_negative():
    m = one("net_debt_to_ebitda",
            composites=[comp("net_debt", -400), comp("ebitda", 200)])
    assert m.value == -2.0                      # -400 / 200


def test_negative_ebitda_is_evidence_not_a_gap():
    m = one("net_debt_to_ebitda",
            composites=[comp("net_debt", 500), comp("ebitda", -50)])
    assert m.data_status == "UNAVAILABLE"
    assert m.reason_code == NEGATIVE_EBITDA
    assert m.kind == EVIDENCE                   # scores 0, worst band (D9)


def test_zero_ebitda_takes_negative_ebitda_too():
    """D41d: the code names the worst band, not the sign."""
    m = one("net_debt_to_ebitda",
            composites=[comp("net_debt", 500), comp("ebitda", 0)])
    assert m.reason_code == NEGATIVE_EBITDA
    assert m.kind == EVIDENCE


def test_net_debt_to_ebitda_missing_inputs_are_gaps():
    m = one("net_debt_to_ebitda", composites=[comp("ebitda", 200)])
    assert m.reason_code == "MISSING_INPUT:net_debt"
    assert m.kind == GAP
    m = one("net_debt_to_ebitda", composites=[comp("net_debt", 500)])
    assert m.reason_code == "MISSING_INPUT:ebitda"
    assert m.kind == GAP


def test_refused_composite_propagates_as_a_missing_input():
    """A composite the engine refused (D26) is UNAVAILABLE, so it is absent
    from the value dict and the ratio reports it as a gap."""
    m = one("net_debt_to_ebitda",
            composites=[comp("net_debt", None, status="UNAVAILABLE"),
                        comp("ebitda", 200)])
    assert m.reason_code == "MISSING_INPUT:net_debt"


# ============ ebit_interest_cover — all coverage edge cases ============

def test_ebit_interest_cover():
    m = one("ebit_interest_cover",
            [mc("ebit", 600), mc("interest_expense", 150)],
            composites=[comp("total_debt", 1000)])
    assert m.value == 4.0                       # 600 / 150
    assert m.method == "ebit / interest_expense"


def test_interest_missing_with_zero_debt_is_neither_gap_nor_evidence():
    m = one("ebit_interest_cover", [mc("ebit", 600)],
            composites=[comp("total_debt", 0)])
    assert m.reason_code == NO_INTEREST_NO_DEBT
    assert m.kind == NEITHER                    # unlevered: no grade cap


def test_interest_missing_with_debt_is_a_gap():
    m = one("ebit_interest_cover", [mc("ebit", 600)],
            composites=[comp("total_debt", 1000)])
    assert m.reason_code == INTEREST_MISSING_WITH_DEBT
    assert m.kind == GAP


def test_interest_zero_with_debt_is_treated_the_same():
    """Almost certainly a tag gap, not free debt."""
    m = one("ebit_interest_cover",
            [mc("ebit", 600), mc("interest_expense", 0)],
            composites=[comp("total_debt", 1000)])
    assert m.reason_code == INTEREST_MISSING_WITH_DEBT


def test_negative_interest_is_treated_as_the_zero_case():
    """D41f: a tagging artefact, never a negative coverage ratio."""
    m = one("ebit_interest_cover",
            [mc("ebit", 600), mc("interest_expense", -150)],
            composites=[comp("total_debt", 1000)])
    assert m.reason_code == INTEREST_MISSING_WITH_DEBT
    assert m.value is None


def test_interest_missing_with_total_debt_unavailable():
    """D41b: the gate could not be evaluated — a gap about the gate, not a
    claim about the company."""
    m = one("ebit_interest_cover", [mc("ebit", 600)])
    assert m.reason_code == "MISSING_INPUT:total_debt"
    assert m.kind == GAP


def test_negative_earnings_is_evidence():
    m = one("ebit_interest_cover",
            [mc("ebit", -100), mc("interest_expense", 150)],
            composites=[comp("total_debt", 1000)])
    assert m.reason_code == NEGATIVE_EARNINGS
    assert m.kind == EVIDENCE                   # scored in the worst band


def test_zero_ebit_with_interest_is_negative_earnings():
    m = one("ebit_interest_cover",
            [mc("ebit", 0), mc("interest_expense", 150)],
            composites=[comp("total_debt", 1000)])
    assert m.reason_code == NEGATIVE_EARNINGS   # rule is ebit <= 0


def test_interest_gate_wins_over_negative_earnings():
    """D41c: both rules apply; the gap is reported first, because negative
    earnings is a claim about a ratio you could have computed."""
    m = one("ebit_interest_cover",
            [mc("ebit", -100), mc("interest_expense", 0)],
            composites=[comp("total_debt", 1000)])
    assert m.reason_code == INTEREST_MISSING_WITH_DEBT
    assert m.kind == GAP


def test_ebit_missing_with_interest_present_is_a_gap():
    m = one("ebit_interest_cover", [mc("interest_expense", 150)],
            composites=[comp("total_debt", 1000)])
    assert m.reason_code == "MISSING_INPUT:ebit"
    assert m.kind == GAP


# ============ current_ratio ============

def test_current_ratio():
    m = one("current_ratio",
            [mc("current_assets", 600), mc("current_liabilities", 400)])
    assert m.value == 1.5                       # 600 / 400
    assert m.method == "current_assets / current_liabilities"


def test_current_ratio_zero_denominator():
    m = one("current_ratio",
            [mc("current_assets", 600), mc("current_liabilities", 0)])
    assert m.reason_code == ZERO_DENOMINATOR
    assert m.kind == GAP
    assert m.value is None                      # never infinite


def test_current_ratio_negative_denominator_refuses_and_warns():
    metrics, report = run([mc("current_assets", 600),
                           mc("current_liabilities", -400)])
    m = metrics["current_ratio"]
    assert m.reason_code == NEGATIVE_DENOMINATOR
    assert m.kind == GAP
    # the negative denominator is itself surfaced (D41e) — once per metric
    # that hit it, since three ratios share this denominator
    # only the metrics that actually reached the denominator: cash is absent
    # here, so cash_to_current_liabilities refuses earlier with MISSING_INPUT
    surfaced = {e.concept for e in report.events}
    assert surfaced == {"current_ratio", "quick_ratio"}
    assert metrics["cash_to_current_liabilities"].reason_code == "MISSING_INPUT:cash"
    assert all(e.code == NEGATIVE_DENOMINATOR for e in report.events)
    assert all("-400" in e.detail for e in report.events)


def test_no_event_when_the_denominator_is_fine():
    _, report = run([mc("current_assets", 600), mc("current_liabilities", 400)])
    assert report.events == []


def test_current_ratio_missing_inputs():
    m = one("current_ratio", [mc("current_liabilities", 400)])
    assert m.reason_code == "MISSING_INPUT:current_assets"
    m = one("current_ratio", [mc("current_assets", 600)])
    assert m.reason_code == "MISSING_INPUT:current_liabilities"


# ============ all three together ============

def test_every_period_produces_every_metric():
    metrics, _ = run(unavailable=[UnavailableConcept("revenue", END, "NO_CANDIDATE_TAG")])
    assert set(metrics) == set(METRICS)
    assert len(METRICS) == 17          # 19 in the table minus ROA and ROE
    # a period with nothing resolved still gets a row per metric, all gaps
    assert all(m.data_status == "UNAVAILABLE" for m in metrics.values())
    assert all(m.kind == GAP for m in metrics.values())


def test_unavailable_metrics_carry_no_value_and_no_method():
    m = one("net_debt_to_ebitda", composites=[comp("ebitda", 200)])
    assert m.value is None and m.method is None and m.inputs == []


# =============================================================================
# Phase 5 completion: the remaining fourteen ratios
# =============================================================================

from credit_risk.metrics.ratios import (          # noqa: E402
    INSUFFICIENT_DATA,
    INVENTORY_UNKNOWN,
    NON_POSITIVE_CAPITAL,
    NO_DEBT,
)

PRIOR = "2022-12-31"


# ============ new reason kinds (D42a) ============

def test_no_debt_is_neither_not_a_gap():
    """D42a: an unlevered company cannot have a debt ratio, and that is a good
    thing — GAP would cap the grade of a debt-free company."""
    assert reason_kind(NO_DEBT) == NEITHER


def test_the_other_new_codes_are_gaps():
    assert reason_kind(NON_POSITIVE_CAPITAL) == GAP
    assert reason_kind(INSUFFICIENT_DATA) == GAP
    assert reason_kind(INVENTORY_UNKNOWN) == GAP


# ============ leverage ============

def test_debt_to_ebitda():
    m = one("debt_to_ebitda",
            composites=[comp("total_debt", 900), comp("ebitda", 300)])
    assert m.value == 3.0                       # 900 / 300
    assert m.method == "total_debt / ebitda"


def test_debt_to_ebitda_negative_ebitda_is_evidence():
    m = one("debt_to_ebitda",
            composites=[comp("total_debt", 900), comp("ebitda", -10)])
    assert m.reason_code == NEGATIVE_EBITDA and m.kind == EVIDENCE


def test_debt_to_capital():
    m = one("debt_to_capital", [mc("equity", 600)],
            composites=[comp("total_debt", 400)])
    assert m.value == 0.4                       # 400 / (400 + 600)
    assert m.method == "total_debt / (total_debt + equity)"


def test_debt_to_capital_survives_negative_equity_while_capital_stays_positive():
    m = one("debt_to_capital", [mc("equity", -200)],
            composites=[comp("total_debt", 500)])
    assert m.value == pytest.approx(500 / 300)  # capital 300, still positive


def test_debt_to_capital_non_positive_capital_is_its_own_reason():
    """Not ZERO_DENOMINATOR: the denominator is a computed sum, so the record
    names what happened rather than a bare arithmetic fact."""
    m = one("debt_to_capital", [mc("equity", -400)],
            composites=[comp("total_debt", 400)])
    assert m.reason_code == NON_POSITIVE_CAPITAL   # capital == 0
    assert m.kind == GAP
    m = one("debt_to_capital", [mc("equity", -500)],
            composites=[comp("total_debt", 400)])
    assert m.reason_code == NON_POSITIVE_CAPITAL   # capital < 0


# ============ coverage: the second cover ratio ============

def test_ebitda_interest_cover_is_a_distinct_metric():
    metrics, _ = run([mc("ebit", 600), mc("interest_expense", 150)],
                     composites=[comp("total_debt", 1000), comp("ebitda", 900)])
    assert metrics["ebitda_interest_cover"].value == 6.0      # 900 / 150
    assert metrics["ebit_interest_cover"].value == 4.0        # 600 / 150
    # never presented as the same thing: different method strings
    assert (metrics["ebitda_interest_cover"].method
            != metrics["ebit_interest_cover"].method)


def test_ebitda_interest_cover_carries_every_coverage_gate():
    # interest missing, no debt
    m = one("ebitda_interest_cover", composites=[comp("ebitda", 900),
                                                 comp("total_debt", 0)])
    assert m.reason_code == NO_INTEREST_NO_DEBT and m.kind == NEITHER
    # interest missing, debt present
    m = one("ebitda_interest_cover", composites=[comp("ebitda", 900),
                                                 comp("total_debt", 1000)])
    assert m.reason_code == INTEREST_MISSING_WITH_DEBT
    # the gate could not be evaluated
    m = one("ebitda_interest_cover", composites=[comp("ebitda", 900)])
    assert m.reason_code == "MISSING_INPUT:total_debt"


def test_ebitda_interest_cover_negative_ebitda_names_the_failed_input():
    """D42d: neither coverage-table row fits, so the code names the input that
    actually failed. EVIDENCE either way."""
    m = one("ebitda_interest_cover", [mc("interest_expense", 150)],
            composites=[comp("ebitda", -50), comp("total_debt", 1000)])
    assert m.reason_code == NEGATIVE_EBITDA
    assert m.kind == EVIDENCE


# ============ liquidity ============

def test_quick_ratio_subtracts_inventory():
    m = one("quick_ratio", [mc("current_assets", 900), mc("inventory", 300),
                            mc("current_liabilities", 400)])
    assert m.value == 1.5                       # (900 - 300) / 400
    assert ("inventory", END) in m.inputs


def test_quick_ratio_treats_inventory_as_zero_for_a_non_inventory_business():
    """No inventory concept resolves in ANY period -> a non-inventory business."""
    m = one("quick_ratio", [mc("current_assets", 900),
                            mc("current_liabilities", 400)])
    assert m.value == 2.25                      # 900 / 400, inventory 0
    assert ("inventory", END) not in m.inputs


def test_quick_ratio_refuses_when_the_company_reports_inventory_elsewhere():
    """D42b, the cross-period rule: inventory resolves in another period, so
    this period's absence is a gap, not a zero. Treating it as zero would
    overstate the ratio; subtracting an unknown would fabricate a number."""
    metrics, _ = run([mc("current_assets", 900), mc("current_liabilities", 400),
                      mc("inventory", 300, end=PRIOR),
                      mc("current_assets", 800, end=PRIOR),
                      mc("current_liabilities", 400, end=PRIOR)])
    assert metrics["quick_ratio"].reason_code == INVENTORY_UNKNOWN
    assert metrics["quick_ratio"].kind == GAP


def test_quick_ratio_cross_period_rule_is_company_wide_not_per_period():
    """The prior period still computes — the rule refuses only the period
    whose inventory is missing."""
    mapping = MappingResult(
        concepts=[mc("current_assets", 900), mc("current_liabilities", 400),
                  mc("inventory", 300, end=PRIOR),
                  mc("current_assets", 800, end=PRIOR),
                  mc("current_liabilities", 400, end=PRIOR)],
        unavailable=[], warnings=[])
    by_period = {(m.metric, m.end): m for m in compute_metrics(mapping, []).metrics}
    assert by_period[("quick_ratio", PRIOR)].value == 1.25    # (800-300)/400
    assert by_period[("quick_ratio", END)].reason_code == INVENTORY_UNKNOWN


def test_cash_to_current_liabilities():
    m = one("cash_to_current_liabilities",
            [mc("cash", 200), mc("current_liabilities", 400)])
    assert m.value == 0.5                       # 200 / 400


# ============ debt-denominated ratios: NO_DEBT ============

def test_cash_to_debt():
    m = one("cash_to_debt", [mc("cash", 250)],
            composites=[comp("total_debt", 1000)])
    assert m.value == 0.25                      # 250 / 1000


def test_zero_debt_refuses_rather_than_producing_infinity():
    for metric, concepts, comps in (
        ("cash_to_debt", [mc("cash", 250)], [comp("total_debt", 0)]),
        ("fcf_to_debt", [], [comp("fcf", 150), comp("total_debt", 0)]),
        ("cfo_to_debt", [mc("cfo", 300)], [comp("total_debt", 0)]),
    ):
        m = one(metric, concepts, composites=comps)
        assert m.reason_code == NO_DEBT, metric
        assert m.kind == NEITHER, metric
        assert m.value is None, metric


def test_fcf_and_cfo_to_debt_compute():
    m = one("fcf_to_debt", composites=[comp("fcf", 150), comp("total_debt", 600)])
    assert m.value == 0.25                      # 150 / 600
    m = one("cfo_to_debt", [mc("cfo", 300)], composites=[comp("total_debt", 600)])
    assert m.value == 0.5                       # 300 / 600


def test_negative_fcf_over_debt_is_valid_and_negative():
    m = one("fcf_to_debt", composites=[comp("fcf", -120), comp("total_debt", 600)])
    assert m.value == -0.2


# ============ margins ============

def test_the_four_margins_and_capex_intensity():
    metrics, _ = run(
        [mc("revenue", 1000), mc("ebit", 150), mc("net_income", 80),
         mc("capex", 90), mc("cfo", 200)],
        composites=[comp("ebitda", 250), comp("fcf", 110)])
    assert metrics["ebitda_margin"].value == 0.25       # 250 / 1000
    assert metrics["ebit_margin"].value == 0.15         # 150 / 1000
    assert metrics["net_margin"].value == 0.08          #  80 / 1000
    assert metrics["fcf_margin"].value == 0.11          # 110 / 1000
    assert metrics["capex_to_revenue"].value == 0.09    #  90 / 1000


def test_margins_refuse_on_zero_revenue():
    m = one("ebit_margin", [mc("revenue", 0), mc("ebit", 150)])
    assert m.reason_code == ZERO_DENOMINATOR and m.kind == GAP


def test_negative_margin_is_valid_and_negative():
    m = one("net_margin", [mc("revenue", 1000), mc("net_income", -250)])
    assert m.value == -0.25


# ============ revenue_growth — the sequence-dependent one (D42c) ============

def test_revenue_growth_over_consecutive_periods():
    metrics, _ = run([mc("revenue", 1000, end=PRIOR), mc("revenue", 1200)])
    m = metrics["revenue_growth"]
    assert m.value == pytest.approx(0.2)        # 1200 / 1000 - 1
    assert m.inputs == [("revenue", END), ("revenue", PRIOR)]


def test_revenue_growth_first_period_is_insufficient_data():
    metrics, _ = run([mc("revenue", 1000, end=PRIOR)])
    by = {(m.metric, m.end): m for m in
          compute_metrics(MappingResult(concepts=[mc("revenue", 1000, end=PRIOR)],
                                        unavailable=[], warnings=[]), []).metrics}
    assert by[("revenue_growth", PRIOR)].reason_code == INSUFFICIENT_DATA


def test_revenue_growth_refuses_across_a_non_adjacent_pair():
    """D42c: adjacent in the series is not adjacent in time. A two-year gap
    must not be labelled one-year growth."""
    metrics, _ = run([mc("revenue", 1000, end="2021-12-31"),
                      mc("revenue", 1200, end=END)])
    assert metrics["revenue_growth"].reason_code == INSUFFICIENT_DATA


def test_revenue_growth_tolerates_a_52_53_week_year():
    """364 and 371 day gaps are ordinary fiscal years, not gaps (D36's window)."""
    metrics, _ = run([mc("revenue", 1000, end="2022-01-01"),
                      mc("revenue", 1100, end="2022-12-31")])
    assert metrics["revenue_growth"].value == pytest.approx(0.1)


def test_revenue_growth_skips_a_period_whose_prior_has_no_revenue():
    """The prior period exists but revenue does not resolve there."""
    metrics, _ = run([mc("cash", 50, end=PRIOR), mc("revenue", 1200)])
    assert metrics["revenue_growth"].reason_code == INSUFFICIENT_DATA


def test_revenue_growth_is_negative_when_revenue_falls():
    metrics, _ = run([mc("revenue", 1000, end=PRIOR), mc("revenue", 750)])
    assert metrics["revenue_growth"].value == pytest.approx(-0.25)
