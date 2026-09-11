"""Task 6: select_annual_facts against the hand-built fixture.

The authority for every expected value here is
tests/fixtures/companyfacts_minimal_expected.md — the answers were written and
owner-verified BEFORE this code existed. If a test and that document disagree,
the document wins.

Synthetic mini-dicts at the bottom cover the branches the fixture deliberately
leaves out (FOREIGN_UNIT, NO_FYE_ANCHOR, FYE disagreement/tie, 10-K/A).
"""

import json
from pathlib import Path

import pytest

from credit_risk.normalise import quality, select_annual_facts

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "companyfacts_minimal.json"

ACCN_FY2022_10K = "0000999999-23-000001"
ACCN_FY2023_10K = "0000999999-24-000001"


@pytest.fixture(scope="module")
def result():
    return select_annual_facts(json.loads(FIXTURE_PATH.read_text()))


def by_key(facts):
    return {(f.tag, f.end): f for f in facts}


# --- the seven expected current rows -----------------------------------------

def test_selected_current_rows_match_expected_doc(result):
    """The exact 'Selected (current) rows' table from the expectations doc."""
    got = {(f.tag, f.end, f.val, f.accn) for f in result.selected}
    assert got == {
        ("Revenues", "2022-12-31", 1000, ACCN_FY2022_10K),   # D15: original filing
        ("Revenues", "2023-12-31", 1200, ACCN_FY2023_10K),
        ("NetIncomeLoss", "2022-12-31", 90, ACCN_FY2023_10K),  # restated value
        ("NetIncomeLoss", "2023-12-31", 110, ACCN_FY2023_10K),
        ("CostOfGoodsAndServicesSold", "2023-12-31", 600, ACCN_FY2023_10K),
        ("CashAndCashEquivalentsAtCarryingValue", "2022-12-31", 50, ACCN_FY2022_10K),
        ("CashAndCashEquivalentsAtCarryingValue", "2023-12-31", 70, ACCN_FY2023_10K),
    }
    assert all(f.status == "CURRENT" for f in result.selected)


# --- restatement (rule 4 / D14) ----------------------------------------------

def test_restatement_supersedes_original_never_deleted(result):
    assert [(s.tag, s.end, s.val, s.accn, s.superseded_by) for s in result.superseded] == [
        ("NetIncomeLoss", "2022-12-31", 100, ACCN_FY2022_10K, ACCN_FY2023_10K)
    ]
    assert result.superseded[0].status == "SUPERSEDED"


# --- equal-value duplicate (D15) ---------------------------------------------

def test_equal_value_duplicate_keeps_original_provenance(result):
    current = by_key(result.selected)[("Revenues", "2022-12-31")]
    assert current.accn == ACCN_FY2022_10K and current.superseded_by is None
    assert [(d.tag, d.end, d.val, d.accn) for d in result.duplicates] == [
        ("Revenues", "2022-12-31", 1000, ACCN_FY2023_10K)
    ]
    assert result.duplicates[0].status == "DUPLICATE"
    assert result.duplicates[0].superseded_by is None


# --- exclusions ---------------------------------------------------------------

def all_vals(result):
    return {
        f.val
        for bucket in (result.selected, result.superseded, result.duplicates)
        for f in bucket
    }


def test_quarterly_fact_excluded(result):
    assert 260 not in all_vals(result)          # rule 1: fp=Q2, form=10-Q


def test_bad_duration_fact_excluded(result):
    assert 800 not in all_vals(result)          # rule 2: 274 days, despite fp=FY/10-K


def test_off_fye_instant_excluded_not_unavailable(result):
    assert 55 not in all_vals(result)           # rule 3: end != derived FYE
    # its filing has an anchor, so it is excluded — not an UNAVAILABLE marker
    assert not any(u.end == "2023-06-30" for u in result.unavailable)


def test_dei_and_shares_units_silently_ignored(result):
    assert 50000000 not in all_vals(result)
    assert not any(u.unit == "shares" for u in result.unavailable)


# --- FYE derivation (D13) -----------------------------------------------------

def test_derived_fiscal_year_ends_and_no_warnings(result):
    assert result.fiscal_year_ends == ["2022-12-31", "2023-12-31"]
    assert result.warnings == []
    assert result.unavailable == []


# --- the fy-stamp trap --------------------------------------------------------

def test_fy_stamp_trap_periods_not_merged(result):
    """Both NetIncomeLoss periods carry fy=2023 (the restated 2022 fact was
    reported in the FY2023 10-K); grouping by fy would have merged them."""
    ni22 = by_key(result.selected)[("NetIncomeLoss", "2022-12-31")]
    ni23 = by_key(result.selected)[("NetIncomeLoss", "2023-12-31")]
    assert (ni22.val, ni23.val) == (90, 110)
    assert ni22.fy == 2023 and ni23.fy == 2023  # same stamp, different periods


# --- rule 6 provenance --------------------------------------------------------

def test_provenance_fields_recorded_on_every_selected_fact(result):
    for f in result.selected + result.superseded + result.duplicates:
        assert f.accn and f.filed and f.form and f.fp and f.end
        assert f.fy is not None
        assert f.unit == "USD"
    for f in result.selected:
        if f.tag == "CashAndCashEquivalentsAtCarryingValue":
            assert f.start is None              # instant facts have no start
        else:
            assert f.start is not None


# --- synthetic cases the fixture deliberately leaves out ----------------------

def duration(tag, start, end, val, accn="s-1", form="10-K", filed="2023-02-15"):
    return {"start": start, "end": end, "val": val, "accn": accn,
            "fy": 2022, "fp": "FY", "form": form, "filed": filed}


def wrap(tag_units):
    return {"facts": {"us-gaap": {
        tag: {"units": units} for tag, units in tag_units.items()
    }}}


@pytest.mark.parametrize("unit", ["EUR", "GBP", "JPY"])
def test_genuine_foreign_currency_is_unavailable(unit):
    """Rule 5: a real ISO-4217 non-USD currency still produces a FOREIGN_UNIT
    marker — this is the signal the code exists for (D24)."""
    cf = wrap({"Revenues": {unit: [duration("Revenues", "2022-01-01", "2022-12-31", 500)]}})
    res = select_annual_facts(cf)
    assert res.selected == []
    assert [(u.tag, u.unit, u.reason_code) for u in res.unavailable] == [
        ("Revenues", unit, "FOREIGN_UNIT")
    ]


@pytest.mark.parametrize("unit", ["USD/shares", "USD/Warrant"])
def test_per_unit_denomination_produces_no_marker(unit):
    """USD/shares is a rate per unit, not a foreign currency and not an amount:
    ignored like shares and pure, with no UNAVAILABLE marker at all (D24)."""
    cf = wrap({"CommonStockDividendsPerShareCashPaid": {unit: [
        duration("CommonStockDividendsPerShareCashPaid", "2022-01-01", "2022-12-31", 0.6)
    ]}})
    res = select_annual_facts(cf)
    assert res.selected == []
    assert res.unavailable == []
    assert res.warnings == []


@pytest.mark.parametrize("unit", ["shares", "pure", "segment", "patent", "Employee", "Y", "Rate"])
def test_non_monetary_units_produce_no_marker(unit):
    """Counts and dimensionless units are not money and not foreign currency."""
    cf = wrap({"NumberOfReportableSegments": {unit: [
        duration("NumberOfReportableSegments", "2022-01-01", "2022-12-31", 4)
    ]}})
    res = select_annual_facts(cf)
    assert res.selected == []
    assert res.unavailable == []


def test_usd_and_per_share_units_on_the_same_tag():
    """A tag carrying both USD and USD/shares yields the USD fact only."""
    cf = wrap({"Revenues": {
        "USD": [duration("Revenues", "2022-01-01", "2022-12-31", 500)],
        "USD/shares": [duration("Revenues", "2022-01-01", "2022-12-31", 1.25)],
    }})
    res = select_annual_facts(cf)
    assert [(f.val, f.unit) for f in res.selected] == [(500, "USD")]
    assert res.unavailable == []


def test_classify_unit_three_way_split():
    from credit_risk.normalise.selection import classify_unit
    assert classify_unit("USD") == "monetary"
    assert classify_unit("EUR") == "foreign"
    for unit in ("USD/shares", "shares", "pure", "segment", "Rate", "reporting_unit"):
        assert classify_unit(unit) == "non_monetary", unit


def test_no_fye_anchor_unavailable():
    """A filing with only balance-sheet data cannot validate its instants (D13)."""
    cf = wrap({"Assets": {"USD": [
        {"end": "2022-12-31", "val": 900, "accn": "s-1",
         "fy": 2022, "fp": "FY", "form": "10-K", "filed": "2023-02-15"}
    ]}})
    res = select_annual_facts(cf)
    assert res.selected == []
    assert [(u.tag, u.reason_code) for u in res.unavailable] == [("Assets", "NO_FYE_ANCHOR")]


def test_fye_disagreement_most_common_wins_and_flags():
    """Two duration ends 1 day apart: same fiscal year, most common wins (D13/D16)."""
    cf = wrap({
        "Revenues": {"USD": [duration("Revenues", "2022-01-01", "2022-12-31", 100)]},
        "OperatingIncomeLoss": {"USD": [duration("OperatingIncomeLoss", "2022-01-01", "2022-12-31", 20)]},
        "NetIncomeLoss": {"USD": [duration("NetIncomeLoss", "2022-01-02", "2023-01-01", 10)]},
        "Assets": {"USD": [
            {"end": "2022-12-31", "val": 900, "accn": "s-1",
             "fy": 2022, "fp": "FY", "form": "10-K", "filed": "2023-02-15"},
            {"end": "2023-01-01", "val": 901, "accn": "s-1",
             "fy": 2022, "fp": "FY", "form": "10-K", "filed": "2023-02-15"},
        ]},
    })
    res = select_annual_facts(cf)
    assert res.fiscal_year_ends == ["2022-12-31"]       # 2 votes beat 1
    assert [w.code for w in res.warnings] == [quality.FYE_DISAGREEMENT]
    assert res.warnings[0].period_end == "2022-12-31"   # the winning anchor
    kept_instants = [f for f in res.selected if f.start is None]
    assert [(f.end, f.val) for f in kept_instants] == [("2022-12-31", 900)]


def test_fye_tie_is_ambiguous_and_fail_safe():
    """Equal votes for two nearby ends: no anchor is guessed; instants near the
    tied dates are UNAVAILABLE with AMBIGUOUS_FYE (D16, fail-safe)."""
    cf = wrap({
        "Revenues": {"USD": [duration("Revenues", "2022-01-01", "2022-12-31", 100)]},
        "NetIncomeLoss": {"USD": [duration("NetIncomeLoss", "2022-01-02", "2023-01-01", 10)]},
        "Assets": {"USD": [
            {"end": "2022-12-31", "val": 900, "accn": "s-1",
             "fy": 2022, "fp": "FY", "form": "10-K", "filed": "2023-02-15"},
        ]},
    })
    res = select_annual_facts(cf)
    assert res.fiscal_year_ends == []
    assert [w.code for w in res.warnings] == [quality.FYE_TIE]
    assert [(u.tag, u.reason_code) for u in res.unavailable] == [("Assets", "AMBIGUOUS_FYE")]
    assert all(f.start is not None for f in res.selected)  # durations still selected


def test_duration_and_instant_sharing_an_end_date_are_separate_facts():
    """D29: modelled on KHC's GoodwillImpairmentLoss 2018-12-29, where one filing
    reported the same tag as both a duration and an instant fact. Grouping them
    together made each supersede the other — one ended up 'superseded by its own
    accession' — so both must stay CURRENT instead."""
    cf = wrap({"GoodwillImpairmentLoss": {"USD": [
        duration("GoodwillImpairmentLoss", "2021-12-31", "2022-12-31", 7008, accn="s-1"),
        {"end": "2022-12-31", "val": 6900, "accn": "s-1",
         "fy": 2022, "fp": "FY", "form": "10-K", "filed": "2023-02-15"},
    ]}})
    res = select_annual_facts(cf)
    assert {(f.val, f.start is None) for f in res.selected} == {
        (7008, False),   # the duration fact
        (6900, True),    # the instant fact
    }
    assert all(f.status == "CURRENT" for f in res.selected)
    assert res.superseded == [] and res.duplicates == []
    assert not any(f.superseded_by == f.accn for f in res.superseded)


def test_restatement_still_supersedes_within_one_period_type():
    """Widening identity must not stop same-shape restatements superseding."""
    cf = wrap({"Revenues": {"USD": [
        duration("Revenues", "2021-12-31", "2022-12-31", 100, accn="s-1"),
        duration("Revenues", "2021-12-31", "2022-12-31", 90, accn="s-2",
                 filed="2024-02-15"),
    ]}})
    res = select_annual_facts(cf)
    assert [(f.val, f.accn) for f in res.selected] == [(90, "s-2")]
    assert [(s.val, s.superseded_by) for s in res.superseded] == [(100, "s-2")]


def test_same_day_refiling_tiebreak_warns():
    """D16(4): same filed date, different accessions — the accession-order
    heuristic must be visible, not silent. Higher accession wins, lower is
    superseded, and a SAME_DAY_REFILING_TIEBREAK warning names both."""
    cf = wrap({"Revenues": {"USD": [
        duration("Revenues", "2022-01-01", "2022-12-31", 100, accn="s-1"),
        duration("Revenues", "2022-01-01", "2022-12-31", 90, accn="s-2"),
    ]}})
    res = select_annual_facts(cf)
    assert [(f.val, f.accn) for f in res.selected] == [(90, "s-2")]
    assert [(s.val, s.superseded_by) for s in res.superseded] == [(100, "s-2")]
    tiebreaks = [w for w in res.warnings if w.code == quality.SAME_DAY_REFILING_TIEBREAK]
    assert len(tiebreaks) == 1
    event = tiebreaks[0]
    assert (event.tag, event.period_end, event.accession) == (
        "Revenues", "2022-12-31", "s-1",
    )
    assert "s-1" in event.detail and "s-2" in event.detail


def test_10ka_form_accepted():
    """Rule 1 accepts 10-K/A — the branch the fixture leaves uncovered."""
    cf = wrap({"Revenues": {"USD": [
        duration("Revenues", "2022-01-01", "2022-12-31", 100, form="10-K/A")
    ]}})
    res = select_annual_facts(cf)
    assert [(f.val, f.form) for f in res.selected] == [(100, "10-K/A")]
