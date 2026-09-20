"""The golden set: four company-years hand-verified against their filings.

**This is the only test in the suite that checks the engine against something
other than itself.** Every other test compares it to hand-built fixtures or to
its own prior output, so all of them share one failure mode: if the engine
misreads a filing consistently, nothing notices. These four cases were read
from the human-readable income statement, balance sheet, cash-flow statement
and footnotes of the filing documents — never from companyfacts, the cached
payload, or any pipeline output.

The markdown files in `tests/golden/` are the evidence; this module is the
enforcement. **It parses those files rather than restating their numbers**, so
the two cannot drift apart (CLAUDE.md rule 13, one invariant one layer).

Two kinds of row are enforced:

- `AGREES` — the engine must still reproduce the filing figure exactly.
- `DIFFERS` — the engine must still produce the *recorded* value. Four of the
  sixteen disagreements are engine defects; pinning them means a fix makes this
  test fail loudly and forces the evidence file to be updated with it, rather
  than the defect quietly disappearing. The classification of each is in the
  markdown.
"""

import json
import re
from pathlib import Path

import pytest

from credit_risk import config
from credit_risk.pipeline import analyse

GOLDEN_DIR = Path(__file__).parent / "golden"
FILES = sorted(GOLDEN_DIR.glob("*_FY*.md"))

CIKS = {"CCL": 815097, "YUM": 1041061, "MCK": 927653, "BDX": 10795}
ENDS = {"CCL_FY2019": "2019-11-30", "YUM_FY2023": "2023-12-31",
        "MCK_FY2023": "2023-03-31", "BDX_FY2009": "2009-09-30"}

pytestmark = pytest.mark.skipif(
    not FILES or not config.RAW_DIR.exists(),
    reason="no golden files or no cached companyfacts (data/raw is gitignored)",
)


def _num(cell):
    cell = cell.strip().strip("`")
    if cell in ("—", ""):
        return None
    try:
        return float(cell.replace(",", ""))
    except ValueError:
        return cell          # a reason code such as ST_DEBT_SCOPE_UNCERTAIN


def parse(path):
    """Rows of (concept, filing_value, engine_value, verdict) from one file."""
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| `"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 4 or cells[3] not in ("AGREES", "DIFFERS"):
            continue
        rows.append((cells[0].strip("`"), _num(cells[1]), _num(cells[2]), cells[3]))
    return rows


def engine_values(key):
    cik, end = CIKS[key.split("_")[0]], ENDS[key]
    raw = json.loads((config.RAW_DIR / f"CIK{cik:010d}.json").read_text())["content"]
    _, mp, cp, _, _, _, _, _ = analyse(raw)
    out = {}
    for c in mp.concepts:
        if c.end == end:
            out[c.concept] = c.value
    for c in cp:
        if c.end == end:
            out[c.concept] = c.value if c.value is not None else c.reason_code
    return out


@pytest.fixture(scope="module", params=[p.stem for p in FILES])
def case(request):
    key = request.param
    return key, parse(GOLDEN_DIR / f"{key}.md"), engine_values(key)


def test_the_evidence_file_has_rows(case):
    key, rows, _ = case
    assert len(rows) >= 14, f"{key}: only {len(rows)} verified rows"


def test_every_agreeing_figure_still_matches_the_filing(case):
    """The core assertion: the engine reproduces what a person reads in the
    filing. A failure here means the engine's reading of a real 10-K changed."""
    key, rows, eng = case
    for concept, filing, _, verdict in rows:
        if verdict != "AGREES":
            continue
        got = eng.get(concept)
        assert got is not None, f"{key}: {concept} no longer resolves"
        assert abs(got - filing) < 0.5, (
            f"{key}: {concept} — filing says {filing:,.0f}, engine now {got:,.0f}")


def test_every_recorded_disagreement_is_unchanged(case):
    """Pins the sixteen known differences — four engine defects, five
    restatement effects, and the rest consequent. If one is fixed, this fails
    and the evidence file must be updated to say so."""
    key, rows, eng = case
    for concept, filing, recorded, verdict in rows:
        if verdict != "DIFFERS":
            continue
        got = eng.get(concept)
        if isinstance(recorded, str):
            assert got == recorded, f"{key}: {concept} was {recorded}, now {got}"
        elif recorded is None:
            assert got is None, f"{key}: {concept} was unresolved, now {got}"
        else:
            assert got is not None and abs(got - recorded) < 0.5, (
                f"{key}: {concept} was {recorded:,.0f}, now {got}")
            assert abs(got - filing) >= 0.5, (
                f"{key}: {concept} now MATCHES the filing — the defect is fixed. "
                f"Update tests/golden/{key}.md and move this row to AGREES.")


def test_each_file_states_its_independence(case):
    """The whole value of this set rests on the figures not coming from the
    XBRL. If that sentence is ever removed, the set stops meaning anything."""
    key, _, _ = case
    text = (GOLDEN_DIR / f"{key}.md").read_text(encoding="utf-8")
    assert "Independence statement" in text
    assert "companyfacts" in text and "cached JSON" in text
    assert "sec.gov/Archives" in text, f"{key}: no filing URL"


def test_bdx_refusal_is_the_documented_one():
    """BDX FY2009 is the set's refusal case: the engine declines total_debt
    because DebtCurrent may already contain current_ltd, and the filing's debt
    note confirms it does. Asserted directly, not just via the table."""
    if "BDX_FY2009" not in [p.stem for p in FILES]:
        pytest.skip("BDX golden file absent")
    eng = engine_values("BDX_FY2009")
    assert eng["total_debt"] == "ST_DEBT_SCOPE_UNCERTAIN"
    text = (GOLDEN_DIR / "BDX_FY2009.md").read_text(encoding="utf-8")
    assert "200,085" in text and "402,965" in text
