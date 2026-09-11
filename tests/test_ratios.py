"""Task 11: the three ratios, every formula and every coverage edge case.

Figures are chosen so each expected value is exact mental arithmetic. Every
edge case in the methodology's coverage table is asserted separately, and the
evidence-versus-gap kind is asserted alongside the reason code — the code
alone does not tell Phase 6 how to treat it (D9, D41a).
"""

import pytest

from credit_risk.metrics.composites import CompositeConcept
from credit_risk.metrics.ratios import (
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
    # the negative denominator is itself surfaced (D41e)
    assert [(e.code, e.concept) for e in report.events] == [
        (NEGATIVE_DENOMINATOR, "current_ratio")]
    assert "-400" in report.events[0].detail


def test_no_event_when_the_denominator_is_fine():
    _, report = run([mc("current_assets", 600), mc("current_liabilities", 400)])
    assert report.events == []


def test_current_ratio_missing_inputs():
    m = one("current_ratio", [mc("current_liabilities", 400)])
    assert m.reason_code == "MISSING_INPUT:current_assets"
    m = one("current_ratio", [mc("current_assets", 600)])
    assert m.reason_code == "MISSING_INPUT:current_liabilities"


# ============ all three together ============

def test_every_period_produces_all_three_metrics():
    metrics, _ = run(unavailable=[UnavailableConcept("revenue", END, "NO_CANDIDATE_TAG")])
    assert set(metrics) == {"net_debt_to_ebitda", "ebit_interest_cover",
                            "current_ratio"}
    # a period with nothing resolved still gets a row per metric, all gaps
    assert all(m.data_status == "UNAVAILABLE" for m in metrics.values())
    assert all(m.kind == GAP for m in metrics.values())


def test_unavailable_metrics_carry_no_value_and_no_method():
    m = one("net_debt_to_ebitda", composites=[comp("ebitda", 200)])
    assert m.value is None and m.method is None and m.inputs == []
