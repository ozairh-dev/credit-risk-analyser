"""Task 7: map_concepts — tag mapping over the selection output.

Fixture-driven tests run the real pipeline (fixture JSON -> select_annual_facts
-> map_concepts with the real config/tag_map.yaml); the authority for those is
tests/fixtures/companyfacts_minimal_expected.md. Synthetic tests construct
SelectionResult directly to cover cases the fixture leaves out.
"""

import json
from pathlib import Path

import pytest

from credit_risk.normalise import map_concepts, quality, select_annual_facts
from credit_risk.normalise.selection import SelectedFact, SelectionResult

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "companyfacts_minimal.json"


@pytest.fixture(scope="module")
def mapped():
    selection = select_annual_facts(json.loads(FIXTURE_PATH.read_text()))
    return map_concepts(selection)


def by_key(result):
    return {(c.concept, c.end): c for c in result.concepts}


# --- the authority case: fallback tag ----------------------------------------

def test_fallback_resolution_matches_expected_doc(mapped):
    """cost_of_revenue = 600 via the 2nd candidate; primary CostOfRevenue absent."""
    c = by_key(mapped)[("cost_of_revenue", "2023-12-31")]
    assert c.value == 600
    assert c.source_tag == "CostOfGoodsAndServicesSold"
    assert c.data_status == "REPORTED"


# --- primary tag present: no fall-through ------------------------------------

def test_primary_tag_resolves_revenue(mapped):
    r22 = by_key(mapped)[("revenue", "2022-12-31")]
    r23 = by_key(mapped)[("revenue", "2023-12-31")]
    assert (r22.value, r23.value) == (1000, 1200)
    assert r22.source_tag == "Revenues" and r23.source_tag == "Revenues"
    assert r22.label == "Revenues"      # reported label preserved


# --- restated current value flows through ------------------------------------

def test_restated_current_value_flows_through(mapped):
    ni22 = by_key(mapped)[("net_income", "2022-12-31")]
    assert ni22.value == 90             # the restatement, not the original 100
    assert ni22.accn == "0000999999-24-000001"


# --- no candidate present -----------------------------------------------------

def test_no_candidate_concept_unavailable(mapped):
    un = {(u.concept, u.period_end): u.reason_code for u in mapped.unavailable}
    assert un[("ebit", "2022-12-31")] == "NO_CANDIDATE_TAG"
    assert un[("ebit", "2023-12-31")] == "NO_CANDIDATE_TAG"
    assert un[("cost_of_revenue", "2022-12-31")] == "NO_CANDIDATE_TAG"
    # never borrowed from another period: no mapped cost_of_revenue for 2022
    assert ("cost_of_revenue", "2022-12-31") not in by_key(mapped)


def test_completeness_counts(mapped):
    """31 concepts x 2 fiscal years = 62 slots; the fixture resolves exactly 7."""
    assert len(mapped.concepts) == 7
    assert len(mapped.unavailable) == 55
    assert mapped.warnings == []


# --- rule 6 provenance + data_status ------------------------------------------

def test_provenance_carried_and_status_reported(mapped):
    for c in mapped.concepts:
        assert c.data_status == "REPORTED"
        assert c.accn and c.filed and c.form and c.fp and c.end
        assert c.fy is not None and c.unit == "USD"
        assert c.source_tag and c.label
    assert by_key(mapped)[("cash", "2022-12-31")].start is None   # instant
    assert by_key(mapped)[("revenue", "2022-12-31")].start is not None


# --- synthetic helpers --------------------------------------------------------

def fact(tag, end, val, start=None, accn="s-1", label=None):
    return SelectedFact(
        tag=tag, val=val, unit="USD", end=end, start=start,
        fy=2022, fp="FY", form="10-K", filed="2023-02-15",
        accn=accn, frame=None, label=label or tag,
    )


def selection_of(facts, fyes=("2022-12-31",)):
    return SelectionResult(
        selected=facts, superseded=[], duplicates=[],
        unavailable=[], warnings=[], fiscal_year_ends=list(fyes),
    )


# --- candidate disagreement (owner's call) ------------------------------------

def test_candidate_disagreement_warns_first_wins():
    sel = selection_of([
        fact("Revenues", "2022-12-31", 100, start="2022-01-01"),
        fact("SalesRevenueNet", "2022-12-31", 95, start="2022-01-01"),
    ])
    res = map_concepts(sel, tag_map={"revenue": ["Revenues", "SalesRevenueNet"]})
    assert [(c.concept, c.value, c.source_tag) for c in res.concepts] == [
        ("revenue", 100, "Revenues")
    ]
    assert len(res.warnings) == 1
    w = res.warnings[0]
    assert w.code == quality.CANDIDATE_TAG_DISAGREEMENT
    assert (w.concept, w.tag, w.period_end) == ("revenue", "Revenues", "2022-12-31")
    assert "Revenues=100" in w.detail and "SalesRevenueNet=95" in w.detail


def test_equal_value_candidates_do_not_warn():
    """D17: equal-value co-tagging is routine XBRL practice — silent."""
    sel = selection_of([
        fact("Revenues", "2022-12-31", 100, start="2022-01-01"),
        fact("SalesRevenueNet", "2022-12-31", 100, start="2022-01-01"),
    ])
    res = map_concepts(sel, tag_map={"revenue": ["Revenues", "SalesRevenueNet"]})
    assert res.warnings == []
    assert res.concepts[0].source_tag == "Revenues"


# --- config is the authority (rule 6) -----------------------------------------

def test_mapping_order_is_config_driven():
    """Reversing the candidate list in the map flips the winner — nothing is
    hard-coded in code (CLAUDE.md rule 6)."""
    facts = [
        fact("Revenues", "2022-12-31", 100, start="2022-01-01"),
        fact("SalesRevenueNet", "2022-12-31", 95, start="2022-01-01"),
    ]
    forward = map_concepts(selection_of(facts),
                           tag_map={"revenue": ["Revenues", "SalesRevenueNet"]})
    reverse = map_concepts(selection_of(facts),
                           tag_map={"revenue": ["SalesRevenueNet", "Revenues"]})
    assert forward.concepts[0].source_tag == "Revenues"
    assert reverse.concepts[0].source_tag == "SalesRevenueNet"
    assert reverse.concepts[0].value == 95


# --- current/noncurrent split concepts (D11) ----------------------------------

def test_lease_concepts_resolve_independently():
    sel = selection_of([
        fact("Revenues", "2022-12-31", 100, start="2022-01-01"),  # duration anchor
        fact("OperatingLeaseLiabilityCurrent", "2022-12-31", 10),
        fact("OperatingLeaseLiabilityNoncurrent", "2022-12-31", 40),
    ])
    res = map_concepts(sel, tag_map={
        "operating_lease_liab_current": ["OperatingLeaseLiabilityCurrent"],
        "operating_lease_liab_noncurrent": ["OperatingLeaseLiabilityNoncurrent"],
    })
    got = {(c.concept, c.value) for c in res.concepts}
    assert got == {
        ("operating_lease_liab_current", 10),
        ("operating_lease_liab_noncurrent", 40),
    }
    assert res.warnings == [] and res.unavailable == []
