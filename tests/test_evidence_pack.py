"""The evidence pack exporter (D73).

The pack is the **complete and exclusive** basis for any memo written from it, so
a duty the exporter drops is not a cosmetic defect: it is a number a model will
reason from without being able to see what it rests on. Phase 9 shipped the
exporter with no tests at all — the v1 final audit's finding 2 — so there is one
test per duty D73 records, driven from real cached filings rather than a
hand-built pack, because a fixture pack would only prove the exporter agrees
with a string this file wrote.
"""

import json
import re

import pytest

from credit_risk import config, pipeline
from credit_risk.export.evidence import REGISTERED_ASSUMPTIONS, build_pack
from credit_risk.scoring.engine import _cap_line
from credit_risk.store.provenance import filing_url

CCL, CAG = 815097, 23217

_cached = {c: config.RAW_DIR / f"CIK{c:010d}.json" for c in (CCL, CAG)}
pytestmark = pytest.mark.skipif(
    not all(p.exists() for p in _cached.values()),
    reason="no cached companyfacts in data/raw/ (gitignored)",
)


def _analysis(cik):
    return pipeline.analyse(json.loads(_cached[cik].read_text())["content"])


@pytest.fixture(scope="module")
def ccl():
    """A pack for a period that scores, stresses and reports — so every section
    below has something in it rather than passing vacuously."""
    raw = json.loads(_cached[CCL].read_text())["content"]
    analysis = _analysis(CCL)
    end = "2019-11-30"
    return raw, analysis, end, build_pack(raw, analysis, end, "CCL")


def _cells(pack):
    """Every table cell in the pack, so a check on rendered values cannot be
    fooled by the same token appearing in prose."""
    out = []
    for line in pack.splitlines():
        if line.startswith("|") and not set(line) <= set("|- "):
            out += [c.strip() for c in line.strip("|").split("|")]
    return out


# ============ duty 1: the cap line travels with the grade (D73b/D57) ============

def test_the_cap_line_travels_with_the_grade(ccl):
    """A grade without its cap line reads as judged when it is capped, and
    capped grades are systematic here, not exceptional."""
    _, analysis, end, pack = ccl
    score = next(s for s in analysis[6] if s.period_end == end)
    assert f"**{_cap_line(score)}**" in pack


def test_the_cap_line_is_generated_not_retyped(ccl):
    """Taken from D57's own generator, so the pack cannot drift from the CLI.
    Asserted by checking the pack carries the generator's exact wording for
    whichever branch this period takes."""
    _, analysis, end, pack = ccl
    score = next(s for s in analysis[6] if s.period_end == end)
    line = _cap_line(score)
    assert ("scored on all 5 categories" in line) != ("missing:" in line)
    assert line in pack


# ============ duty 2: the five stress output duties, verbatim (D73b) ============

DUTIES = ("floating_share = ", "new_debt_rate = ", "liquidity is NOT stressed",
          "the trend component carries its BASE-period verdict",
          "the stressed GRADE covers leverage, coverage and margin only")


def test_all_five_stress_duties_appear_in_the_pack(ccl):
    """Each was recorded as a decision before the engine existed. A pack with
    stressed figures but no basis for them is exactly what D73b forbids."""
    *_, pack = ccl
    for duty in DUTIES:
        assert duty in pack, duty


def test_the_duties_are_copied_verbatim_from_the_run(ccl):
    """Not paraphrased: the pack and the CLI must not be able to disagree."""
    _, analysis, end, pack = ccl
    runs = [r for r in analysis[7] if r.period_end == end]
    assert runs, "period should be stressable"
    for run in runs:
        for line in run.assumptions:
            assert f"- {line}" in pack, line


def test_every_scenario_carries_its_own_duties(ccl):
    """Duties printed once for the pack would let a reader attach the base
    run's resolved new_debt_rate to a severe run that priced differently."""
    _, analysis, end, pack = ccl
    scenarios = {r.scenario for r in analysis[7] if r.period_end == end}
    assert len(scenarios) > 1
    for duty in DUTIES:
        assert pack.count(duty) >= len(scenarios), duty


# ============ duty 3: a derived filing URL on every REPORTED row (D73d/D30b) ============

def _reported_rows(pack):
    """Section 3's data rows only. Scoped deliberately: an earlier draft of
    these tests searched the whole pack, and a sabotage that emptied section
    3's URL column still passed because section 1's single "Filing link" row
    satisfied the search. A test that cannot fail is not a test."""
    section = pack.split("## 3. Reported concepts")[1].split("## 4.")[0]
    rows = []
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip("|").split("|")]
        # the seven-column table only: section 3 also carries the two-column
        # "no usable value" table, and counting both made the row count wrong
        if line.startswith("| ") and len(cells) == 7 and cells[0] != "Concept":
            rows.append(line)
    return rows


def test_every_reported_concept_row_carries_a_derived_filing_url(ccl):
    """D30(b) chose derivation over storage so a link cannot drift from its
    accession. That obligation falls due in this exporter."""
    raw, analysis, end, pack = ccl
    rows = _reported_rows(pack)
    assert len(rows) == len([c for c in analysis[1].concepts if c.end == end])
    for row in rows:
        url = [c.strip() for c in row.strip("|").split("|")][-1]
        assert url.startswith("https://www.sec.gov/Archives/"), row


def test_the_url_on_a_row_is_derived_from_that_rows_own_accession(ccl):
    """A URL present but belonging to a different filing would be worse than
    none: it reads as a citation while pointing elsewhere."""
    raw, _, _, pack = ccl
    for row in _reported_rows(pack):
        cells = [c.strip() for c in row.strip("|").split("|")]
        accn, url = cells[-2], cells[-1]
        assert re.fullmatch(r"\d{10}-\d{2}-\d{6}", accn), row
        assert url == filing_url(raw["cik"], accn), row


# ============ duty 4: the register is populated from config (D73a) ============

def test_the_assumption_register_lists_every_registered_assumption(ccl):
    *_, pack = ccl
    for _, key, _, _ in REGISTERED_ASSUMPTIONS:
        assert key in pack, key


def test_every_registered_value_comes_from_config_not_a_placeholder(ccl):
    """D73a's whole point: the assumptions table is unwired in v1, so an empty
    register would ship a section that says nothing while looking complete."""
    *_, pack = ccl
    section = pack.split("## 8. Assumption register")[1].split("## 9.")[0]
    for _, key, _, _ in REGISTERED_ASSUMPTIONS:
        row = next(l for l in section.splitlines() if l.startswith(f"| {key} "))
        cells = [c.strip() for c in row.strip("|").split("|")]
        assert cells[1] not in ("—", "", "None"), row     # a value, not a blank
        assert cells[3] == "config", row                  # sourced, not invented
        assert cells[4], row                              # and states why


def test_a_registered_value_tracks_the_config_it_came_from(ccl):
    """Checked against the loaded config rather than a literal, so editing the
    YAML cannot leave the register stating a value the engine no longer uses."""
    *_, pack = ccl
    for family, key, _, _ in REGISTERED_ASSUMPTIONS:
        loaded = (config.stress() if family == "stress"
                  else config.load("composites"))
        value = loaded.get(key)
        row = next(l for l in pack.splitlines() if l.startswith(f"| {key} "))
        rendered = [c.strip() for c in row.strip("|").split("|")][1]
        expected = (str(value)
                    if isinstance(value, (str, bool, type(None)))
                    else f"{value:,.4f}")
        assert rendered == expected, f"{key}: pack {rendered!r} vs config {value!r}"


# ============ the boundary section ============

ABSENT = ("market data", "management commentary", "peer or industry comparisons",
          "forward estimates", "credit ratings from any agency",
          "beyond the tagged XBRL facts")


def test_the_pack_names_what_it_does_not_contain(ccl):
    """Stating the boundary is what makes the prompt's "Data not available"
    rule enforceable — otherwise the model must infer what it is missing."""
    *_, pack = ccl
    assert "## 9. What this pack does not contain" in pack
    for item in ABSENT:
        assert item in pack, item


def test_the_boundary_states_the_required_answer(ccl):
    *_, pack = ccl
    assert '**"Data not available"**' in pack


# ============ no artefacts reach the pack ============

ARTEFACTS = {"None", "nan", "NaN", "inf", "-inf", "Inf", "null", "NULL",
             "nan%", "None%", "inf%"}


def test_no_none_or_nan_artefact_reaches_a_table_cell(ccl):
    """A rendered `None` or `nan` is a number a model may quote. Checked on
    table cells rather than the whole text so the prose "None fired this
    period." is not a false positive."""
    *_, pack = ccl
    bad = [c for c in _cells(pack) if c in ARTEFACTS]
    assert not bad, f"artefacts in cells: {sorted(set(bad))}"


def test_no_artefact_survives_across_every_exportable_period(ccl):
    """One period proves little: the absent branches differ period to period,
    and an artefact hides in whichever branch the sample did not take."""
    raw, analysis, _, _ = ccl
    ends = sorted({c.end for c in analysis[1].concepts})
    assert len(ends) > 5
    for end in ends:
        bad = [c for c in _cells(build_pack(raw, analysis, end, "CCL"))
               if c in ARTEFACTS]
        assert not bad, f"{end}: {sorted(set(bad))}"


def test_an_unstressable_period_says_so_rather_than_rendering_empty(ccl):
    """The absent-section branch, asserted rather than assumed reachable."""
    raw, analysis, _, _ = ccl
    stressed = {r.period_end for r in analysis[7]}
    ends = [e for e in sorted({c.end for c in analysis[1].concepts})
            if e not in stressed]
    if not ends:
        pytest.skip("every period of this company is stressable")
    pack = build_pack(raw, analysis, ends[0], "CCL")
    assert "cannot be stress tested" in pack


# ============ D76: an integrity-FAIL period exports no metric value ============

def test_an_integrity_failed_period_exports_no_metric_value():
    """CAG's 122.5% EBITDA margin reached the pack before D76. The pack is the
    exclusive basis for a memo, so an arithmetically impossible figure must not
    be reachable at all — not reachable behind a marker."""
    raw = json.loads(_cached[CAG].read_text())["content"]
    analysis = _analysis(CAG)
    failed = sorted({r.period_end for r in analysis[3].results
                     if r.outcome == "FAIL"})
    assert failed, "CAG should still witness a fail-severity check"
    for end in failed:
        pack = build_pack(raw, analysis, end, "CAG")
        section = pack.split("### Metrics")[1].split("## 5.")[0]
        rows = [l for l in section.splitlines() if l.startswith("| ")][2:]
        assert rows
        for row in rows:
            cells = [c.strip() for c in row.strip("|").split("|")]
            assert cells[1] == "—", row
            assert cells[4] == "INTEGRITY_FAILED", row
        assert "1.2250" not in pack
