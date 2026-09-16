"""Phase 9: evidence export and the memo validator.

The validator is the control the AI workflow rests on, so these tests cover the
four defects the five-violation reality test exposed — every one a matching bug
that would have made the validator either useless (false positives everywhere)
or dangerous (missing real violations).
"""

import pytest

from credit_risk.export.validator import (
    GRADE_LABELS,
    check_grades,
    extract_figures,
    matches,
    pack_grade,
    pack_values,
    render,
    stamp_sections,
    validate,
)
from credit_risk.store.provenance import filing_url

PACK = """# Evidence pack — Test Co — 2023-12-31

## 1. Company and filing

| Field | Value |
|---|---|
| CIK | 815097 |
| Sourcing filing | 10-K 0000815097-20-000003 filed 2020-01-28 |

## 2. Grade

**Grade 4 (scored on all 5 categories)**

| Concept | Value |
|---|---|
| revenue | 20,825,000,000 |
| ebitda | 5,436,000,000 |
| cfo | 5,475,000,000 |
| net_debt_to_ebitda | 2.0206 |
| ebitda_margin | 0.2610 |
"""


# ============ filing_url (D30b) ============

def test_filing_url_matches_edgars_shape():
    assert filing_url(815097, "0000815097-20-000003") == (
        "https://www.sec.gov/Archives/edgar/data/815097/"
        "000081509720000003/0000815097-20-000003-index.htm")


def test_filing_url_without_an_accession():
    assert filing_url(815097, None) is None
    assert filing_url(815097, "") is None


# ============ extraction: the four defects the reality test found ============

def test_scale_words_attach_longest_first():
    """Defect 1. Regex alternation is first-match-wins, so a bare `m` matched
    before `million`, the suffix group failed on "illion", and the scale
    backtracked to None — turning "$5,436 million" into 5,436 and reporting a
    correct figure as unverified. The same bug class as the grade labels."""
    for text, expected in (("$5,436 million", 5.436e9),
                           ("$5.48 billion", 5.48e9),
                           ("20.8bn", 2.08e10),
                           ("450k", 450_000.0)):
        figures = extract_figures(text)
        assert len(figures) == 1, text
        assert figures[0].value == pytest.approx(expected), text


def test_a_figure_ending_a_sentence_is_still_extracted():
    """Defect 4. The lookahead rejected a trailing full stop, so any figure at
    the end of a sentence was silently mis-parsed."""
    figures = extract_figures("EBITDA was $5,436 million.")
    assert figures[0].value == pytest.approx(5.436e9)


def test_identifiers_are_not_figures():
    """Defect 2. An accession number is a citation; extracting its digit runs
    reported three phantom unverified numbers per Source line."""
    figures = extract_figures("Source: 10-K 0000815097-20-000003")
    assert all("815097" not in f.text for f in figures)
    assert not any(f.value > 1e6 for f in figures)


def test_percentages_and_multiples_canonicalise():
    assert extract_figures("26.1%")[0].value == pytest.approx(0.261)
    assert extract_figures("2.02x")[0].value == pytest.approx(2.02)


# ============ matching at the memo's stated precision ============

def test_a_correctly_rounded_figure_matches():
    """The design's whole point: exact-digit matching would flag "$20.8
    billion" against a pack holding 20,825,000,000 — correct, natural writing —
    and a validator that cries wolf gets ignored."""
    values = pack_values(PACK)
    for text in ("$20.8 billion", "$20,825,000,000", "$20.83 billion",
                 "$5,436 million", "$5.44 billion"):
        assert matches(extract_figures(text)[0], values), text


def test_a_wrongly_rounded_figure_does_not_match():
    """Write more digits and you are held to more."""
    values = pack_values(PACK)
    for text in ("$20.9 billion", "$20.75 billion", "$5,437 million"):
        assert not matches(extract_figures(text)[0], values), text


def test_an_invented_figure_does_not_match():
    values = pack_values(PACK)
    assert not matches(extract_figures("$4,735,000,000")[0], values)


def test_a_ratio_matches_its_percentage_form():
    values = pack_values(PACK)
    assert matches(extract_figures("26.10%")[0], values)   # pack has 0.2610


# ============ the low-confidence rule ============

def test_small_bare_numbers_are_low_confidence():
    """A bare number under 100 will coincide with something in a pack of dozens
    by chance; counting it as verified inflates the pass rate."""
    for text in ("4", "5 categories", "in 2019"):
        assert extract_figures(text)[0].is_low_confidence, text


def test_precision_rescues_a_small_number_from_low_confidence():
    """Defect 3. 2.0206 matching the pack is not a coincidence — precision, not
    magnitude alone, decides."""
    figure = extract_figures("2.0206")[0]
    assert not figure.is_low_confidence
    assert matches(figure, pack_values(PACK))


def test_a_scaled_or_suffixed_number_is_never_low_confidence():
    assert not extract_figures("4 billion")[0].is_low_confidence
    assert not extract_figures("12%")[0].is_low_confidence


# ============ grade checking ============

def test_grade_labels_are_longest_first():
    """D73c: "Very strong" contains "strong" and "Very high risk" contains
    "high risk", so naive matching misclassifies every Grade 1 and Grade 6."""
    labels = [label for label, _ in GRADE_LABELS]
    assert labels.index("very strong") < labels.index("strong")
    assert labels.index("very high risk") < labels.index("high risk")


def test_an_explicit_contradicting_grade_is_caught():
    issues = check_grades("We would consider it Grade 2 on our scale.", 4)
    assert len(issues) == 1 and issues[0][1] == 2 and issues[0][2] == 4


def test_a_band_label_in_a_grading_context_is_caught():
    issues = check_grades("The profile is characterised as Very strong.", 4)
    assert len(issues) == 1 and issues[0][1] == 1


def test_ordinary_english_is_not_a_grade_claim():
    """Defect 3 of the reality test: the doc says to check "any sentence
    containing a grade word", which taken literally fires on "leverage is
    moderate" and "cash flow was strong" — burying the real violations."""
    assert check_grades("Leverage is moderate for the sector.", 4) == []
    assert check_grades("Operating cash flow was strong.", 4) == []
    assert check_grades("Coverage is elevated relative to peers.", 4) == []


def test_the_packs_own_grade_is_not_flagged():
    assert check_grades("The pack assigns Grade 4.", 4) == []


def test_pack_grade_is_read_from_the_cap_line():
    assert pack_grade(PACK) == 4
    assert pack_grade("no grade here") is None


# ============ sections and REVIEWED gating ============

def test_a_verbatim_table_section_keeps_its_status():
    memo = "## Copied\n\n| revenue | 20,825,000,000 |\n"
    assert stamp_sections(memo, PACK) == [("Copied", "VERBATIM_FROM_PACK")]


def test_prose_is_ai_interpreted():
    memo = "## Analysis\n\nLeverage looks manageable.\n"
    assert stamp_sections(memo, PACK) == [("Analysis", "AI_INTERPRETED")]


def test_reviewed_is_impossible_with_unverified_figures():
    memo = "Status: REVIEWED\n\nEBITDA was $9,999,999,999.\n"
    report = validate(memo, PACK)
    assert report.reviewed_claimed
    assert report.unverified
    assert not report.may_be_reviewed
    assert "REJECTED" in render(report)


def test_reviewed_is_impossible_with_a_grade_mismatch():
    memo = "Status: REVIEWED\n\nWe would rate it Grade 1.\n"
    report = validate(memo, PACK)
    assert not report.may_be_reviewed


def test_a_clean_memo_may_be_reviewed():
    memo = "Status: REVIEWED\n\nRevenue was $20.8 billion.\n"
    report = validate(memo, PACK)
    assert report.may_be_reviewed
    assert "REJECTED" not in render(report)


# ============ the limitation statement (D74) ============

def test_the_limitation_appears_above_the_results_in_every_run():
    """A limitation below the verdict is one a reader can skip, and a clean
    validation read as a clean memo is worse than no validation."""
    for memo in ("Status: REVIEWED\n\nRevenue was $20.8 billion.\n",
                 "EBITDA was $9,999,999,999.\n"):
        out = render(validate(memo, PACK))
        assert "A CLEAN VALIDATION IS NOT A CLEAN MEMO" in out
        assert out.index("DOES NOT TELL YOU") < out.index("Figures found")


def test_the_limitation_names_what_it_cannot_catch():
    out = render(validate("Revenue was $20.8 billion.\n", PACK))
    assert "used correctly" in out
    assert "false conclusion" in out


# ============ the characterised limitation, asserted (D74) ============

def test_a_figure_cited_under_the_wrong_label_passes():
    """Characterised limitation, not a defect: the validator reads numbers, not
    labels. Asserted so the boundary is pinned rather than assumed."""
    memo = "EBITDA was $5,475,000,000.\n"          # that is the pack's cfo
    assert not validate(memo, PACK).unverified


def test_true_figures_in_a_false_claim_pass():
    """The expected result of the five-violation test, pinned. A human must
    read the memo; the validator cannot do this part."""
    memo = "Liquidity is robust: net_debt_to_ebitda 2.0206.\n"
    report = validate(memo, PACK)
    assert not report.unverified and not report.grade_issues
    assert report.may_be_reviewed
