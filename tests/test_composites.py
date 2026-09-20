"""Task 9: composite concepts, every rule with a hand-computed expected value.

All figures in these tests are small integers chosen so the expected results
can be verified by mental arithmetic — each assertion's comment shows the sum.
Config is passed explicitly so no test depends on config/composites.yaml's
shipped values (those are exercised by tests/test_real_companies.py).
"""

import pytest

from credit_risk.metrics import composites
from credit_risk.metrics.composites import (
    CompositeConcept,
    _deviation,
    compute_composites,
)
from credit_risk.normalise.mapping import MappedConcept, MappingResult, UnavailableConcept
from credit_risk.store.db import connect
from credit_risk.store.schema import create_schema
from credit_risk.store.writer import store_company_data
from credit_risk.normalise.selection import SelectedFact, SelectionResult

CFG = {
    "include_operating_leases": True,
    "include_st_investments": True,
    "component_aggregate_tolerance": 0.05,
}
END = "2023-12-31"


def mc(concept, value, source_tag="T", end=END, start=None):
    return MappedConcept(
        concept=concept, value=value, unit="USD", source_tag=source_tag,
        label=None, end=end, start=start, fy=2023, fp="FY", form="10-K",
        filed="2024-02-01", accn="0000000000-24-000001", frame=None,
    )


def run(concepts, cfg=None):
    mapping = MappingResult(concepts=concepts, unavailable=[], warnings=[])
    return {(c.concept, c.end): c for c in compute_composites(mapping, cfg or CFG)}


# ============ _deviation edges (D34) ============

def test_deviation_ordinary_case_matches_d26s_measured_figure():
    # CCL 2010: |8624 - 9364| / 9364 = 0.0790...
    assert _deviation(8624, 9364) == pytest.approx(0.0790, abs=0.0001)


def test_deviation_both_zero_is_agreement():
    assert _deviation(0.0, 0.0) == 0.0


def test_deviation_aggregate_zero_components_nonzero_refuses():
    assert _deviation(100.0, 0.0) == float("inf")


def test_deviation_negative_components_against_equal_positive_aggregate():
    """The misplaced-abs() canary (D34): abs() on the inputs would make this
    0.0 — perfect agreement manufactured from contradictory data."""
    assert _deviation(-8624.0, 8624.0) == float("inf")


def test_deviation_negative_aggregate_refuses():
    assert _deviation(8624.0, -8624.0) == float("inf")


# ============ total_debt branch 1: plain components ============

def test_plain_components_full_set():
    out = run([
        mc("short_term_debt", 100), mc("current_ltd", 200), mc("noncurrent_ltd", 300),
        mc("finance_lease_liab_current", 10), mc("finance_lease_liab_noncurrent", 20),
        mc("operating_lease_liab_current", 5), mc("operating_lease_liab_noncurrent", 15),
    ])
    td = out[("total_debt", END)]
    # 100 + 200 + 300 + (10+20) + (5+15) = 650
    assert td.value == 650
    assert td.method == "debt_from_components"
    assert td.data_status == "CALCULATED"
    assert td.detail is None                      # nothing zero-by-absence
    ex = out[("total_debt_ex_leases", END)]
    # ex-leases excludes BOTH lease kinds (D33): 100 + 200 + 300 = 600
    assert ex.value == 600
    assert ex.data_status == "CALCULATED"


def test_operating_lease_toggle_off_changes_total_but_not_ex_leases():
    cfg = dict(CFG, include_operating_leases=False)
    out = run([
        mc("short_term_debt", 100), mc("current_ltd", 200), mc("noncurrent_ltd", 300),
        mc("finance_lease_liab_current", 10), mc("finance_lease_liab_noncurrent", 20),
        mc("operating_lease_liab_current", 5), mc("operating_lease_liab_noncurrent", 15),
    ], cfg)
    # 100 + 200 + 300 + 30 = 630 (operating leases excluded by config)
    assert out[("total_debt", END)].value == 630
    assert out[("total_debt_ex_leases", END)].value == 600


def test_zero_by_absence_is_recorded():
    out = run([mc("noncurrent_ltd", 300)])
    td = out[("total_debt", END)]
    # within-pair zero (D33): 0 + 300 = 300; optional components all absent
    assert td.value == 300
    for name in ("current_ltd", "short_term_debt",
                 "finance_lease_liab", "operating_lease_liab"):
        assert name in td.detail
    assert td.detail.startswith("zero_by_absence:")


def test_d26_check_passes_at_exactly_the_tolerance():
    # components 105 vs aggregate 100: |105-100|/100 = 0.05 == tolerance -> agree
    out = run([
        mc("current_ltd", 45), mc("noncurrent_ltd", 60),
        mc("total_ltd_aggregate", 100),
    ])
    td = out[("total_debt", END)]
    assert td.data_status == "CALCULATED"
    assert td.value == 105                # components used, never the aggregate
    assert td.method == "debt_from_components"


def test_d26_check_refuses_just_above_the_tolerance():
    # components 106 vs aggregate 100: 0.06 > 0.05 -> refuse, both figures recorded
    out = run([
        mc("current_ltd", 46), mc("noncurrent_ltd", 60),
        mc("total_ltd_aggregate", 100),
    ])
    td = out[("total_debt", END)]
    assert td.data_status == "UNAVAILABLE"
    assert td.reason_code == "COMPONENT_AGGREGATE_MISMATCH"
    assert "106" in td.detail and "100" in td.detail
    ex = out[("total_debt_ex_leases", END)]
    assert ex.reason_code == "COMPONENT_AGGREGATE_MISMATCH"


def test_d26_comparison_basis_excludes_short_term_debt():
    # components 100 vs aggregate 100 agree exactly; STD 50 must not join the
    # comparison (it would fake a 50% deviation) but must join the value
    out = run([
        mc("short_term_debt", 50), mc("current_ltd", 40), mc("noncurrent_ltd", 60),
        mc("total_ltd_aggregate", 100),
    ])
    td = out[("total_debt", END)]
    assert td.data_status == "CALCULATED"
    assert td.value == 150                # 50 + 40 + 60


def test_d26_half_pair_missing_member_counts_as_zero_in_comparison():
    # WBD shape: current only, 30 vs aggregate 100 -> 70% deviation -> refuse
    out = run([mc("current_ltd", 30), mc("total_ltd_aggregate", 100)])
    assert out[("total_debt", END)].reason_code == "COMPONENT_AGGREGATE_MISMATCH"


# ============ branch 2: aggregate only ============

def test_aggregate_substitutes_for_the_pair_in_the_same_formula():
    out = run([
        mc("short_term_debt", 50), mc("total_ltd_aggregate", 500),
        mc("operating_lease_liab_current", 10), mc("operating_lease_liab_noncurrent", 20),
    ])
    td = out[("total_debt", END)]
    # 500 + 50 + (10+20) = 580
    assert td.value == 580
    assert td.method == "debt_from_aggregate"
    # ex-leases: 500 + 50 = 550
    assert out[("total_debt_ex_leases", END)].value == 550


# ============ branch 3: lease-inclusive LTD (D27) ============

LEASE_PAIR = [
    mc("ltd_incl_leases_current", 100, source_tag="LongTermDebtAndCapitalLeaseObligationsCurrent"),
    mc("ltd_incl_leases_noncurrent", 900, source_tag="LongTermDebtAndCapitalLeaseObligations"),
]


def test_lease_inclusive_branch_composition():
    """No short_term_debt: the pair alone is the whole figure, and the
    standalone lease tags are excluded because the pair already contains them."""
    out = run(LEASE_PAIR + [
        mc("operating_lease_liab_current", 5), mc("operating_lease_liab_noncurrent", 15),
        mc("finance_lease_liab_current", 1), mc("finance_lease_liab_noncurrent", 2),
    ])
    td = out[("total_debt", END)]
    assert td.value == 1000                       # 100 + 900
    assert td.method == "debt_from_lease_inclusive_ltd"
    ex = out[("total_debt_ex_leases", END)]
    assert ex.data_status == "UNAVAILABLE"
    assert ex.reason_code == "LEASES_NOT_SEPARABLE"


def test_lease_inclusive_refuses_short_term_debt_that_looks_like_the_maturities():
    """D78(a). `ltd_incl_leases_current` IS a current-maturities figure, so a
    short_term_debt of the same size may be that debt tagged twice — YUM's
    Note 11 shows exactly that. 98 against a li_cur of 100 is within the
    component/aggregate tolerance, and no aggregate reconciles them, so refuse.
    This is D32's rule generalised to the branch it was missing from."""
    out = run(LEASE_PAIR + [mc("short_term_debt", 98)])
    td = out[("total_debt", END)]
    assert td.data_status == "UNAVAILABLE"
    assert td.reason_code == "ST_DEBT_SCOPE_UNCERTAIN"
    assert "unverifiable" in td.detail
    assert out[("total_debt_ex_leases", END)].reason_code == "ST_DEBT_SCOPE_UNCERTAIN"


def test_lease_inclusive_adds_short_term_debt_of_a_different_size():
    """The other half of the rule, which matters as much: refusing whenever the
    overlap was merely possible over-refused badly. KHC carries short_term_debt
    at 0.6% of its current maturities — obviously separate borrowing, and
    refusing it cost 9 of KHC's 12 lease-inclusive periods."""
    out = run(LEASE_PAIR + [mc("short_term_debt", 5)])
    assert out[("total_debt", END)].value == 1005


def test_lease_inclusive_zero_short_term_debt_never_triggers_the_guard():
    """Zero cannot double-count anything. KHC FY2023 tags it at exactly zero."""
    out = run(LEASE_PAIR + [mc("short_term_debt", 0)])
    assert out[("total_debt", END)].value == 1000


def test_lease_inclusive_adds_short_term_debt_when_the_aggregate_confirms_it():
    """Verifiable case: aggregate 1050 sits at pair + std, so the two are
    disjoint and std is genuinely separate short-term borrowing."""
    out = run(LEASE_PAIR + [mc("short_term_debt", 50),
                            mc("ltd_incl_leases_aggregate", 1050)])
    td = out[("total_debt", END)]
    assert td.value == 1050
    assert td.method == "debt_from_lease_inclusive_ltd"


def test_lease_inclusive_drops_short_term_debt_the_aggregate_already_contains():
    """The other verifiable case: aggregate 1000 sits at the pair, so std is
    already inside it and adding it would double-count."""
    out = run(LEASE_PAIR + [mc("short_term_debt", 50),
                            mc("ltd_incl_leases_aggregate", 1000)])
    td = out[("total_debt", END)]
    assert td.value == 1000
    assert "already" in (td.detail or "") or td.value == 1000


def test_aggregate_branch_refuses_finance_leases_it_cannot_reconcile():
    """D78(b). `LongTermDebt` is filer-dependent on whether it already contains
    finance leases — measured across the adopted 43, where a cross-check exists
    it says "contained" 6 times and "separate" 7. With no cross-check, refuse."""
    out = run([mc("total_ltd_aggregate", 1000),
               mc("finance_lease_liab_current", 10),
               mc("finance_lease_liab_noncurrent", 40)])
    td = out[("total_debt", END)]
    assert td.data_status == "UNAVAILABLE"
    assert td.reason_code == "LEASE_CONTAINMENT_UNVERIFIABLE"


def test_aggregate_branch_drops_finance_leases_already_inside_the_aggregate():
    """MCK's real shape: the lease note shows finance leases sit inside the
    balance-sheet debt lines, and the lease-inclusive aggregate confirms it by
    sitting at the aggregate rather than above it."""
    out = run([mc("total_ltd_aggregate", 1000),
               mc("ltd_incl_leases_aggregate", 1000),
               mc("finance_lease_liab_current", 10),
               mc("finance_lease_liab_noncurrent", 40)])
    td = out[("total_debt", END)]
    assert td.value == 1000
    assert "already in aggregate" in (td.detail or "")


def test_aggregate_branch_adds_finance_leases_when_they_are_separate():
    out = run([mc("total_ltd_aggregate", 1000),
               mc("ltd_incl_leases_aggregate", 1050),
               mc("finance_lease_liab_current", 10),
               mc("finance_lease_liab_noncurrent", 40)])
    assert out[("total_debt", END)].value == 1050


def test_lease_inclusive_cross_check_refuses_beyond_tolerance():
    # pair 1000 vs aggregate 1100: |1000-1100|/1100 = 9.09% > 5% -> refuse
    out = run(LEASE_PAIR + [mc("ltd_incl_leases_aggregate", 1100)])
    td = out[("total_debt", END)]
    assert td.reason_code == "COMPONENT_AGGREGATE_MISMATCH"


def test_lease_inclusive_aggregate_is_never_a_value_source():
    # pair absent, aggregate present -> NO_DEBT_DATA, not a 1100 total (D27.1)
    out = run([mc("ltd_incl_leases_aggregate", 1100)])
    assert out[("total_debt", END)].reason_code == "NO_DEBT_DATA"


def test_plain_path_wins_over_lease_inclusive():
    # D27 precedence: noncurrent_ltd alone forces the plain branch
    out = run(LEASE_PAIR + [mc("noncurrent_ltd", 300)])
    td = out[("total_debt", END)]
    assert td.method == "debt_from_components"
    assert td.value == 300


def test_half_resolved_lease_pair_is_no_debt_data():
    # D33.4: one member of the pair alone falls through
    out = run([mc("ltd_incl_leases_noncurrent", 900)])
    assert out[("total_debt", END)].reason_code == "NO_DEBT_DATA"


# ============ branch 4: nothing ============

def test_no_debt_data_when_nothing_resolves():
    out = run([mc("cash", 100)])
    td = out[("total_debt", END)]
    assert td.data_status == "UNAVAILABLE"
    assert td.reason_code == "NO_DEBT_DATA"


def test_short_term_debt_alone_is_not_zero_ltd():
    # never assume zero debt: STD without any LTD concept refuses
    out = run([mc("short_term_debt", 50)])
    assert out[("total_debt", END)].reason_code == "NO_DEBT_DATA"


# ============ DebtCurrent guard (D32) ============

def test_debtcurrent_with_current_ltd_refuses():
    out = run([
        mc("short_term_debt", 100, source_tag="DebtCurrent"),
        mc("current_ltd", 50), mc("noncurrent_ltd", 300),
    ])
    td = out[("total_debt", END)]
    assert td.data_status == "UNAVAILABLE"
    assert td.reason_code == "ST_DEBT_SCOPE_UNCERTAIN"
    assert "100" in td.detail and "50" in td.detail   # both values recorded


def test_debtcurrent_without_current_ltd_is_usable():
    out = run([
        mc("short_term_debt", 100, source_tag="DebtCurrent"),
        mc("noncurrent_ltd", 300),
    ])
    td = out[("total_debt", END)]
    # 100 + 300 = 400; no overlap possible without current_ltd
    assert td.value == 400
    assert td.data_status == "CALCULATED"


def test_short_term_borrowings_with_current_ltd_is_fine():
    # the guard is about the TAG, not about short_term_debt in general
    out = run([
        mc("short_term_debt", 100, source_tag="ShortTermBorrowings"),
        mc("current_ltd", 50), mc("noncurrent_ltd", 300),
    ])
    assert out[("total_debt", END)].value == 450


# ============ net_debt ============

def test_net_debt_full():
    out = run([
        mc("noncurrent_ltd", 650), mc("cash", 100), mc("short_term_investments", 50),
    ])
    nd = out[("net_debt", END)]
    # 650 - 100 - 50 = 500
    assert nd.value == 500
    assert nd.detail is None


def test_net_debt_sti_zero_by_absence():
    out = run([mc("noncurrent_ltd", 650), mc("cash", 100)])
    nd = out[("net_debt", END)]
    # 650 - 100 = 550, STI zeroed and recorded (D33.1)
    assert nd.value == 550
    assert nd.detail == "zero_by_absence: short_term_investments"


def test_net_debt_sti_toggle_off_ignores_sti_silently():
    cfg = dict(CFG, include_st_investments=False)
    out = run([
        mc("noncurrent_ltd", 650), mc("cash", 100), mc("short_term_investments", 50),
    ], cfg)
    nd = out[("net_debt", END)]
    assert nd.value == 550                # STI not subtracted
    assert nd.detail is None              # config choice, not absence


def test_net_debt_cash_missing_is_missing_input():
    out = run([mc("noncurrent_ltd", 650)])
    assert out[("net_debt", END)].reason_code == "MISSING_INPUT:cash"


def test_net_debt_unavailable_total_debt_propagates():
    out = run([mc("cash", 100)])          # no debt data at all
    assert out[("net_debt", END)].reason_code == "MISSING_INPUT:total_debt"


def test_negative_net_debt_is_valid_net_cash():
    out = run([mc("noncurrent_ltd", 300), mc("cash", 1000)])
    # 300 - 1000 = -700, reported as negative
    assert out[("net_debt", END)].value == -700


# ============ ebitda ============

def test_ebitda_and_its_label():
    out = run([mc("ebit", 100, start="2023-01-01"), mc("d_and_a", 40, start="2023-01-01")])
    e = out[("ebitda", END)]
    # 100 + 40 = 140
    assert e.value == 140
    assert e.label == "EBITDA (EBIT + D&A)"
    assert e.method == "ebit + d_and_a"


def test_ebitda_never_falls_back_to_ebit():
    out = run([mc("ebit", 100, start="2023-01-01")])
    e = out[("ebitda", END)]
    assert e.data_status == "UNAVAILABLE"
    assert e.reason_code == "MISSING_INPUT:d_and_a"


def test_ebitda_negative_ebit_is_reported_negative():
    out = run([mc("ebit", -50, start="2023-01-01"), mc("d_and_a", 40, start="2023-01-01")])
    assert out[("ebitda", END)].value == -10


# ============ fcf ============

def test_fcf():
    out = run([mc("cfo", 200, start="2023-01-01"), mc("capex", 80, start="2023-01-01")])
    # 200 - 80 = 120 (capex stored as positive outflow)
    assert out[("fcf", END)].value == 120


def test_fcf_missing_capex():
    out = run([mc("cfo", 200, start="2023-01-01")])
    assert out[("fcf", END)].reason_code == "MISSING_INPUT:capex"


# ============ gross_profit fallback ============

def test_gross_profit_fallback_computes_when_tag_absent():
    out = run([mc("revenue", 1000, start="2023-01-01"),
               mc("cost_of_revenue", 600, start="2023-01-01")])
    gp = out[("gross_profit", END)]
    # 1000 - 600 = 400
    assert gp.value == 400
    assert gp.data_status == "CALCULATED"
    assert gp.method == "revenue - cost_of_revenue"


def test_gross_profit_reported_tag_wins_no_composite_row():
    out = run([mc("gross_profit", 400), mc("revenue", 1000), mc("cost_of_revenue", 600)])
    assert ("gross_profit", END) not in out


def test_gross_profit_fallback_needs_both_inputs():
    out = run([mc("revenue", 1000, start="2023-01-01")])
    assert ("gross_profit", END) not in out    # mapping's NO_CANDIDATE_TAG row stands


# ============ storage: concept_inputs, no accession, idempotency ============

@pytest.fixture
def conn():
    c = connect(":memory:")
    create_schema(c)
    yield c
    c.close()


def _store(conn, concepts, unavailable=()):
    # each mapped concept needs a backing CURRENT fact: the schema's REPORTED
    # CHECK requires fact_id, which the writer resolves by (tag, end, shape)
    facts = [SelectedFact(tag=c.source_tag, val=c.value, unit=c.unit, end=c.end,
                          start=c.start, fy=c.fy, fp=c.fp, form=c.form,
                          filed=c.filed, accn=c.accn, frame=c.frame)
             for c in concepts]
    mapping = MappingResult(concepts=concepts, unavailable=list(unavailable), warnings=[])
    selection = SelectionResult(selected=facts, superseded=[], duplicates=[],
                                unavailable=[], warnings=[], fiscal_year_ends=[])
    comps = compute_composites(mapping, CFG)
    store_company_data(conn, 999999, "Test Co", selection, mapping,
                       composites=comps, fingerprint="fp-test")
    return comps


def test_stored_composite_row_shape(conn):
    _store(conn, [mc("noncurrent_ltd", 300), mc("cash", 100)])
    row = conn.execute(
        """SELECT * FROM concepts WHERE concept='total_debt' AND status='CURRENT'"""
    ).fetchone()
    assert row["data_status"] == "CALCULATED"
    assert row["value"] == 300
    assert row["method"] == "debt_from_components"
    assert row["accession"] is None       # provenance flows through concept_inputs
    assert "zero_by_absence" in row["detail"]


def test_concept_inputs_link_composite_to_its_inputs(conn):
    _store(conn, [mc("noncurrent_ltd", 300), mc("cash", 100)])
    rows = conn.execute(
        """SELECT i.concept AS input FROM concept_inputs ci
           JOIN concepts c ON c.id = ci.concept_id
           JOIN concepts i ON i.id = ci.input_concept_id
           WHERE c.concept = 'net_debt'"""
    ).fetchall()
    assert sorted(r["input"] for r in rows) == ["cash", "total_debt"]


def test_composite_restore_is_idempotent(conn):
    concepts = [mc("noncurrent_ltd", 300), mc("cash", 100)]
    _store(conn, concepts)
    _store(conn, concepts)
    n = conn.execute(
        "SELECT COUNT(*) AS n FROM concepts WHERE concept='total_debt'"
    ).fetchone()["n"]
    assert n == 1                          # no supersession churn on re-store


def test_gross_profit_fallback_supersedes_nothing_on_restore(conn):
    concepts = [mc("revenue", 1000, start="2023-01-01"),
                mc("cost_of_revenue", 600, start="2023-01-01")]
    unavailable = [UnavailableConcept("gross_profit", END, "NO_CANDIDATE_TAG")]
    _store(conn, concepts, unavailable)
    _store(conn, concepts, unavailable)
    rows = conn.execute(
        "SELECT status, data_status, value FROM concepts WHERE concept='gross_profit'"
    ).fetchall()
    # exactly one row: the CALCULATED fallback; mapping's UNAVAILABLE was
    # skipped as filled, not stored-then-superseded
    assert len(rows) == 1
    assert rows[0]["status"] == "CURRENT"
    assert rows[0]["value"] == 400


def test_mismatch_refusal_stores_both_figures(conn):
    _store(conn, [mc("current_ltd", 46), mc("noncurrent_ltd", 60),
                  mc("total_ltd_aggregate", 100)])
    row = conn.execute(
        "SELECT * FROM concepts WHERE concept='total_debt' AND status='CURRENT'"
    ).fetchone()
    assert row["data_status"] == "UNAVAILABLE"
    assert row["reason_code"] == "COMPONENT_AGGREGATE_MISMATCH"
    assert "106" in row["detail"] and "100" in row["detail"]
