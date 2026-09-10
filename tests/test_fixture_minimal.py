"""Task 5: structural guards on the hand-built companyfacts fixture.

These are NOT selection tests — select_annual_facts arrives in Task 6 and will be
tested against tests/fixtures/companyfacts_minimal_expected.md. These only assert
the fixture file itself has the geometry that document claims, so an accidental
edit to the fixture can't silently invalidate the hand-computed expectations.
"""

import json
from datetime import date
from pathlib import Path

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "companyfacts_minimal.json"


def load():
    return json.loads(FIXTURE_PATH.read_text())


def test_fixture_parses_with_expected_shape_and_no_output_fields():
    data = load()
    assert data["cik"] == 999999
    assert set(data["facts"]) == {"dei", "us-gaap"}
    us_gaap = data["facts"]["us-gaap"]
    assert len(us_gaap["Revenues"]["units"]["USD"]) == 5
    assert len(us_gaap["NetIncomeLoss"]["units"]["USD"]) == 3
    assert len(us_gaap["CostOfGoodsAndServicesSold"]["units"]["USD"]) == 1
    assert len(us_gaap["CashAndCashEquivalentsAtCarryingValue"]["units"]["USD"]) == 3
    # the fallback case requires the primary tag to be absent
    assert "CostOfRevenue" not in us_gaap
    # instant facts carry no `start`; duration facts always do
    for fact in us_gaap["CashAndCashEquivalentsAtCarryingValue"]["units"]["USD"]:
        assert "start" not in fact
    # superseded_by is an output of OUR selection, never present in SEC input
    assert "superseded_by" not in FIXTURE_PATH.read_text()


def test_duration_day_counts_match_expectations_doc():
    """Hand-computed: full calendar years are 364 days, the stub period 274, Q2 90."""
    us_gaap = load()["facts"]["us-gaap"]
    day_counts = set()
    for tag in us_gaap.values():
        for fact in tag["units"]["USD"]:
            if "start" in fact:
                day_counts.add(
                    (date.fromisoformat(fact["end"]) - date.fromisoformat(fact["start"])).days
                )
    assert day_counts == {90, 274, 364}
    assert 350 <= 364 <= 380          # the clean annual facts sit inside the window
    assert not (350 <= 90 <= 380)     # R5 outside
    assert not (350 <= 274 <= 380)    # R4 outside


def test_restatement_pair_geometry():
    """N1/N2: same concept and period, different filings; later-filed value is 90."""
    facts = load()["facts"]["us-gaap"]["NetIncomeLoss"]["units"]["USD"]
    fy2022 = [f for f in facts if f["end"] == "2022-12-31"]
    assert len(fy2022) == 2
    assert {f["val"] for f in fy2022} == {100, 90}
    original, restated = sorted(fy2022, key=lambda f: f["filed"])
    assert original["filed"] < restated["filed"]
    assert original["accn"] != restated["accn"]
    assert restated["val"] == 90
    # the fy-stamp trap: the restated fact's period is 2022 but its fy is 2023
    assert restated["fy"] == 2023
