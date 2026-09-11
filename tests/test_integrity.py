"""Task 10: integrity checks, every rule with a hand-computed expected value.

Each check gets a passing case, a failing case, and — asserted separately,
because they are different outcomes — a skip-on-UNAVAILABLE case. Figures are
small integers so every expectation can be checked by mental arithmetic.
"""

import pytest

from credit_risk.metrics.integrity import (
    INTEGRITY_CHECKS,
    ABNORMAL_FROM_ZERO,
    ABNORMAL_MOVEMENT,
    ABNORMAL_SIGN_CHANGE,
    FAIL,
    PASS,
    SKIP,
    WARN,
    period_verdict,
    run_integrity_checks,
)
from credit_risk.normalise.mapping import MappedConcept, MappingResult, UnavailableConcept
from credit_risk.metrics.composites import CompositeConcept

CFG = {
    "balance_sheet_tolerance": 0.01,
    "abnormal_movement_threshold": 3.0,
    "continuity_window_days": [350, 380],
}
END = "2023-12-31"
PRIOR = "2022-12-31"


def mc(concept, value, end=END):
    return MappedConcept(
        concept=concept, value=value, unit="USD", source_tag="T", label=None,
        end=end, start=None, fy=2023, fp="FY", form="10-K",
        filed="2024-02-01", accn="0000000000-24-000001", frame=None,
    )


def comp(concept, value, end=END, status="CALCULATED"):
    return CompositeConcept(concept=concept, end=end, value=value, method="m",
                            data_status=status)


def run(concepts, composites=(), unavailable=(), cfg=None):
    mapping = MappingResult(concepts=list(concepts),
                            unavailable=list(unavailable), warnings=[])
    return run_integrity_checks(mapping, list(composites), cfg or CFG)


def result(report, check, end=END):
    found = [r for r in report.results if r.check_name == check and r.period_end == end]
    assert len(found) == 1, f"expected exactly one {check} for {end}, got {len(found)}"
    return found[0]


# ============ balance sheet balances (warn) ============

def test_balance_sheet_passes_within_tolerance():
    # |1000 - (600 + 395)| / 1000 = 0.5% <= 1%
    r = result(run([mc("total_assets", 1000), mc("total_liabilities", 600),
                    mc("equity", 395)]), "balance_sheet_balances")
    assert r.outcome == PASS
    assert r.deviation == pytest.approx(0.005)


def test_balance_sheet_passes_at_exactly_the_tolerance():
    # |1000 - (600 + 390)| / 1000 = 1.0% == tolerance -> still passes
    r = result(run([mc("total_assets", 1000), mc("total_liabilities", 600),
                    mc("equity", 390)]), "balance_sheet_balances")
    assert r.outcome == PASS
    assert r.deviation == pytest.approx(0.01)


def test_balance_sheet_warns_just_above_tolerance():
    # |1000 - (600 + 389)| / 1000 = 1.1% > 1% -> warn, never fail
    r = result(run([mc("total_assets", 1000), mc("total_liabilities", 600),
                    mc("equity", 389)]), "balance_sheet_balances")
    assert r.outcome == WARN
    assert r.lhs == 1000 and r.rhs == 989
    assert "1.10%" in r.detail


def test_balance_sheet_skips_when_an_input_is_unavailable():
    r = result(run([mc("total_assets", 1000), mc("total_liabilities", 600)]),
               "balance_sheet_balances")
    assert r.outcome == SKIP
    assert "equity" in r.detail


def test_balance_sheet_skips_on_zero_total_assets():
    """D39a: rule 4 — a zero denominator never produces a number."""
    r = result(run([mc("total_assets", 0), mc("total_liabilities", 600),
                    mc("equity", 395)]), "balance_sheet_balances")
    assert r.outcome == SKIP
    assert "ZERO_DENOMINATOR" in r.detail


# ============ current subset checks (fail), split per D39b ============

def test_current_assets_subset_passes_and_fails():
    ok = result(run([mc("current_assets", 400), mc("total_assets", 1000)]),
                "current_assets_subset")
    assert ok.outcome == PASS
    bad = result(run([mc("current_assets", 1400), mc("total_assets", 1000)]),
                 "current_assets_subset")
    assert bad.outcome == FAIL
    assert bad.lhs == 1400 and bad.rhs == 1000


def test_current_liabilities_subset_is_independent_of_the_assets_check():
    """D39b: one comparison can skip while the other runs."""
    report = run([mc("current_assets", 400), mc("total_assets", 1000),
                  mc("current_liabilities", 300)])   # total_liabilities absent
    assert result(report, "current_assets_subset").outcome == PASS
    assert result(report, "current_liabilities_subset").outcome == SKIP


def test_current_liabilities_subset_fails_when_exceeded():
    r = result(run([mc("current_liabilities", 900), mc("total_liabilities", 600)]),
               "current_liabilities_subset")
    assert r.outcome == FAIL


def test_subset_passes_at_equality():
    r = result(run([mc("current_assets", 1000), mc("total_assets", 1000)]),
               "current_assets_subset")
    assert r.outcome == PASS      # <=, not <


# ============ cash subset (fail) ============

def test_cash_subset_pass_fail_and_skip():
    assert result(run([mc("cash", 100), mc("current_assets", 400)]),
                  "cash_subset").outcome == PASS
    assert result(run([mc("cash", 500), mc("current_assets", 400)]),
                  "cash_subset").outcome == FAIL
    assert result(run([mc("cash", 100)]), "cash_subset").outcome == SKIP


# ============ debt subset (fail) ============

def test_debt_subset_reads_the_composite():
    report = run([mc("total_liabilities", 1000)],
                 composites=[comp("total_debt_ex_leases", 600)])
    assert result(report, "debt_subset").outcome == PASS


def test_debt_subset_fails_when_debt_exceeds_liabilities():
    report = run([mc("total_liabilities", 500)],
                 composites=[comp("total_debt_ex_leases", 600)])
    r = result(report, "debt_subset")
    assert r.outcome == FAIL
    assert r.lhs == 600 and r.rhs == 500


def test_debt_subset_skips_when_the_composite_was_refused():
    """An UNAVAILABLE composite is a data gap, not a violation — the same
    evidence-versus-gap split as D9. This is the LUMN/KHC shape: every
    lease-inclusive period has total_debt_ex_leases UNAVAILABLE (D27)."""
    report = run([mc("total_liabilities", 1000)],
                 composites=[comp("total_debt_ex_leases", None,
                                  status="UNAVAILABLE")])
    r = result(report, "debt_subset")
    assert r.outcome == SKIP
    assert "total_debt_ex_leases" in r.detail


# ============ non-negative revenue (fail) ============

def test_revenue_non_negative_pass_fail_skip():
    assert result(run([mc("revenue", 1000)]), "revenue_non_negative").outcome == PASS
    assert result(run([mc("revenue", 0)]), "revenue_non_negative").outcome == PASS
    assert result(run([mc("revenue", -5)]), "revenue_non_negative").outcome == FAIL
    r = result(run([], unavailable=[UnavailableConcept("revenue", END, "NO_CANDIDATE_TAG")]),
               "revenue_non_negative")
    assert r.outcome == SKIP


# ============ period continuity (warn) — D36 ============

# JNJ's real period ends, the 52/53-week sequence that calendar-year keying
# mis-reads: FY2009 ends 2010-01-03, so calendar 2009 has no period end and
# calendar 2012 has two.
JNJ_ENDS = [
    "2007-12-30", "2008-12-28", "2010-01-03", "2011-01-02", "2012-01-01",
    "2012-12-30", "2013-12-29", "2014-12-28", "2016-01-03", "2017-01-01",
    "2017-12-31", "2018-12-30", "2019-12-29", "2021-01-03", "2022-01-02",
    "2023-01-01", "2023-12-31", "2024-12-29", "2025-12-28",
]


def test_continuity_never_warns_on_a_real_52_53_week_sequence():
    """D36, defended by test rather than by argument.

    Calendar-year keying flags six of these boundaries (2008->2010,
    2012->2012, 2014->2016, 2017->2017, 2019->2021, 2023->2023). All six are
    fiscal-calendar artefacts, and the day-gap reading flags none.
    """
    report = run([mc("revenue", 100, end=e) for e in JNJ_ENDS])
    continuity = [r for r in report.results if r.check_name == "period_continuity"]
    assert len(continuity) == len(JNJ_ENDS)
    assert [r.outcome for r in continuity[1:]] == [PASS] * (len(JNJ_ENDS) - 1)
    # the calendar-year reading would have called these consecutive years equal
    # or two apart; the day gaps are all ordinary
    assert all(363 <= r.deviation <= 371 for r in continuity[1:])


def test_continuity_first_period_skips_rather_than_warning():
    report = run([mc("revenue", 100, end=e) for e in ("2022-12-31", "2023-12-31")])
    first = result(report, "period_continuity", "2022-12-31")
    assert first.outcome == SKIP
    assert "no prior period" in first.detail


def test_continuity_warns_on_a_real_gap():
    # 2020-12-31 -> 2022-12-31 is 730 days: a genuinely missing year
    report = run([mc("revenue", 100, end=e) for e in ("2020-12-31", "2022-12-31")])
    r = result(report, "period_continuity", "2022-12-31")
    assert r.outcome == WARN
    assert r.deviation == 730
    assert "INSUFFICIENT_DATA" in r.detail


# ============ abnormal movement (warn, D23 codes) ============

def codes(report):
    return {(e.concept, e.code) for e in report.events}


def test_abnormal_movement_flags_above_threshold_only():
    # revenue 100 -> 500: |500/100 - 1| = 4.0 > 3.0 -> flag
    # cash    100 -> 300: |300/100 - 1| = 2.0 -> no flag
    report = run([mc("revenue", 100, end=PRIOR), mc("cash", 100, end=PRIOR),
                  mc("revenue", 500), mc("cash", 300)])
    assert codes(report) == {("revenue", ABNORMAL_MOVEMENT)}


def test_abnormal_movement_at_exactly_the_threshold_does_not_flag():
    # 100 -> 400 is exactly 3.0; the rule is > 3.0
    report = run([mc("revenue", 100, end=PRIOR), mc("revenue", 400)])
    assert codes(report) == set()


def test_sign_change_flags_regardless_of_magnitude():
    # ebitda 100 -> -1: a 1.01 move, but the sign changed
    report = run([mc("ebit", 100, end=PRIOR), mc("ebit", -1)])
    assert codes(report) == {("ebit", ABNORMAL_SIGN_CHANGE)}


def test_prior_zero_flags_from_zero_never_an_infinite_percentage():
    report = run([mc("capex", 0, end=PRIOR), mc("capex", 50)])
    assert codes(report) == {("capex", ABNORMAL_FROM_ZERO)}


def test_unavailable_in_either_period_is_not_an_abnormal_movement():
    """D23: already recorded as a data gap, so it produces no event."""
    report = run([mc("revenue", 100, end=PRIOR)],
                 unavailable=[UnavailableConcept("revenue", END, "NO_CANDIDATE_TAG")])
    assert codes(report) == set()


def test_abnormal_movement_covers_composites_but_not_non_core_concepts():
    report = run([mc("dividends", 100, end=PRIOR), mc("dividends", 900)],
                 composites=[comp("total_debt", 100, end=PRIOR),
                             comp("total_debt", 900)])
    # dividends is deliberately out of scope (D23); total_debt is in
    assert codes(report) == {("total_debt", ABNORMAL_MOVEMENT)}


# ============ period verdict (derived, D37) ============

def test_verdict_precedence():
    from credit_risk.metrics.integrity import IntegrityResult as R
    assert period_verdict([R("a", END, PASS), R("b", END, SKIP)]) == PASS
    assert period_verdict([R("a", END, PASS), R("b", END, WARN)]) == WARN
    assert period_verdict([R("a", END, WARN), R("b", END, FAIL)]) == FAIL


def test_a_period_where_everything_skipped_is_pass_with_no_evidence():
    """Not a failure — but the summary must show checks_run = 0 so a reader
    can tell it apart from a period that genuinely passed."""
    report = run([], unavailable=[UnavailableConcept("revenue", END, "NO_CANDIDATE_TAG")])
    per_period = [r for r in report.results if r.period_end == END]
    assert {r.outcome for r in per_period} == {SKIP}
    assert period_verdict(per_period) == PASS


# ============ phantom periods (D40) ============

def test_phantom_period_does_not_break_continuity():
    """A period where nothing resolved sits between two real ones. It must not
    report two consecutive fiscal years as discontinuous (D40).

    This is LUMN's shape exactly: 2013-12-31 and 2014-12-31 are 365 days
    apart, with 2014-02-20 — carrying only an out-of-tag-map fact — between.
    """
    report = run(
        [mc("revenue", 100, end="2013-12-31"), mc("revenue", 110, end="2014-12-31")],
        unavailable=[UnavailableConcept("revenue", "2014-02-20", "NO_CANDIDATE_TAG")],
    )
    continuity = {r.period_end: r for r in report.results
                  if r.check_name == "period_continuity"}
    assert continuity["2014-12-31"].outcome == PASS
    assert continuity["2014-12-31"].deviation == 365
    # the phantom is recorded, not hidden — just not a link in the chain
    assert continuity["2014-02-20"].outcome == SKIP
    assert "not a trend period" in continuity["2014-02-20"].detail


def test_phantom_period_still_gets_every_other_check():
    """Nothing is hidden: the period appears with every check skipped (D40)."""
    report = run(
        [mc("revenue", 100, end="2013-12-31")],
        unavailable=[UnavailableConcept("revenue", "2014-02-20", "NO_CANDIDATE_TAG")],
    )
    phantom = [r for r in report.results if r.period_end == "2014-02-20"]
    assert {r.outcome for r in phantom} == {SKIP}
    assert {r.check_name for r in phantom} == set(INTEGRITY_CHECKS)


def test_phantom_period_does_not_suppress_abnormal_movement_across_it():
    """A phantom between two real periods must not hide a real year-on-year
    move — without D40 the comparison would be real->phantom and back."""
    report = run(
        [mc("revenue", 100, end="2013-12-31"), mc("revenue", 500, end="2014-12-31")],
        unavailable=[UnavailableConcept("revenue", "2014-02-20", "NO_CANDIDATE_TAG")],
    )
    assert codes(report) == {("revenue", ABNORMAL_MOVEMENT)}
