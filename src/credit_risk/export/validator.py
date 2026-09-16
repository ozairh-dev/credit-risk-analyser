"""Memo validator (Phase 9, docs/ai-governance.md).

Deterministic checks on a memo written from an evidence pack. **This is the
control the whole AI workflow rests on**, so its limits are stated as loudly as
its results (D74).

## What it checks

- every number in the memo appears in the pack, **at the precision the memo
  states it**;
- no sentence claims a grade other than the pack's;
- `REVIEWED` is impossible while unverified figures remain;
- sections are stamped `AI_INTERPRETED` unless verbatim from a pack table.

## What it cannot check, and why that is stated in every run

The validator verifies that numbers **appear**, never that they are **used
correctly**. A memo may cite `5,436` as EBITDA when the pack holds it as CFO and
pass cleanly; it may assemble entirely true figures into a conclusion none of
them support and pass cleanly.

**A clean validation is not a clean memo.** That sentence is printed above the
results in every run, never below, because a limitation under the verdict is one
a reader can skip — and a clean validation mistaken for a clean memo is worse
than no validation at all (D74).
"""

import re
from dataclasses import dataclass, field

# Band labels from the methodology. LONGEST FIRST is load-bearing (D73c):
# "Very strong" contains "strong" and "Very high risk" contains "high risk", so
# naive matching classifies every Grade 1 mention as Grade 2 and every Grade 6
# as Grade 5.
GRADE_LABELS = (
    ("very high risk", 6),
    ("very strong", 1),
    ("high risk", 5),
    ("moderate", 3),
    ("elevated", 4),
    ("strong", 2),
)

SCALES = {
    "k": 1e3, "thousand": 1e3,
    "m": 1e6, "mm": 1e6, "million": 1e6, "millions": 1e6,
    "bn": 1e9, "b": 1e9, "billion": 1e9, "billions": 1e9,
    "tn": 1e12, "trillion": 1e12,
}

# A number, optional scale word, optional % or x suffix.
#
# The scale alternation is LONGEST-FIRST, for the same reason the grade labels
# are (D73c): regex alternation is first-match-wins, so a bare `m` matches
# before `million`, the suffix group then fails on "illion", and the whole
# scale backtracks to None — silently turning "$5,436 million" into 5,436 and
# flagging a correct figure as unverified. Caught by the five-violation test.
_SCALE_ALT = "|".join(sorted(SCALES, key=len, reverse=True))
TOKEN = re.compile(
    r"(?<![\w.\-])(-?\d[\d,]*(?:\.\d+)?)\s*"
    rf"({_SCALE_ALT})?"
    # `(?!\.\d)` stops "5.48" splitting; `(?!\w)` stops "5x4". A trailing
    # SENTENCE period must still match — `(?![\w.])` rejected "$5,436 million."
    # and reported a correct figure as unverified.
    r"\s*(%|x)?(?!\.\d)(?!\w)",
    re.IGNORECASE,
)

# Identifiers are not claims. An accession number contains three digit runs
# that would otherwise be extracted as figures and reported as unverified.
IDENTIFIER = re.compile(r"\d{10}-\d{2}-\d{6}|\bCIK\s*\d+|/\d{6,}/|\b\d{18,}\b")

# Below this a coincidental match is likely in a pack of dozens of numbers.
LOW_CONFIDENCE_BELOW = 100
YEAR = re.compile(r"^(19|20)\d\d$")


@dataclass
class Figure:
    text: str           # as written in the memo
    value: float        # canonical value
    precision: int      # significant figures the memo stated
    is_low_confidence: bool


@dataclass
class Report:
    figures: list = field(default_factory=list)
    verified: list = field(default_factory=list)
    unverified: list = field(default_factory=list)
    low_confidence: list = field(default_factory=list)
    grade_issues: list = field(default_factory=list)
    sections: list = field(default_factory=list)
    reviewed_claimed: bool = False

    @property
    def may_be_reviewed(self) -> bool:
        """REVIEWED is impossible while anything is unverified."""
        return not self.unverified and not self.grade_issues


def _sig_figs(literal: str) -> int:
    """Significant figures the memo actually wrote."""
    digits = literal.replace(",", "").replace("-", "").lstrip("0")
    if "." in digits:
        return len(digits.replace(".", "").lstrip("0")) or 1
    return len(digits.rstrip("0")) or 1


def _canonical(literal: str, scale: str | None, suffix: str | None) -> float:
    value = float(literal.replace(",", ""))
    if scale:
        value *= SCALES[scale.lower()]
    if suffix == "%":
        value /= 100.0
    return value


def extract_figures(text: str) -> list:
    """Every numeric claim in the memo, canonicalised and unit-aware.

    Identifiers are blanked first: an accession number is a citation, not a
    figure, and extracting its digit runs reports three phantom unverified
    numbers per source line.
    """
    figures = []
    text = IDENTIFIER.sub(" ", text)
    for match in TOKEN.finditer(text):
        literal, scale, suffix = match.group(1), match.group(2), match.group(3)
        bare = literal.replace(",", "")
        value = _canonical(literal, scale, suffix)
        # A small number stated to 4+ significant figures is not a
        # coincidence: 2.0206 matching the pack is a real match, while a bare
        # "4" is not. Precision, not magnitude alone, decides.
        precise = _sig_figs(literal) >= 4
        is_year = bool(YEAR.match(bare))
        # A year is always low-confidence: 2019 has four significant figures
        # but is a date, not a claim, and precision must not rescue it.
        low = (not scale and not suffix
               and (is_year or (abs(value) < LOW_CONFIDENCE_BELOW and not precise)))
        figures.append(Figure(match.group(0).strip(), value,
                              _sig_figs(literal), low))
    return figures


def pack_values(pack: str) -> list:
    """Every numeric value the pack contains, canonicalised the same way."""
    values = []
    for match in TOKEN.finditer(pack):
        values.append(_canonical(match.group(1), match.group(2), match.group(3)))
    return values


def _round_sig(value: float, figs: int) -> float:
    if value == 0:
        return 0.0
    from math import floor, log10
    return round(value, -int(floor(log10(abs(value)))) + (figs - 1))


def matches(figure: Figure, values) -> bool:
    """Does any pack value round to this figure at the memo's own precision?

    This is the heart of the design (D74). Exact-digit matching would flag
    "$20.8 billion" against a pack holding 20,825,000,000 — correct, natural
    writing — and a validator that cries wolf gets ignored. A blanket tolerance
    would let a model shift figures for slack. Matching at the memo's stated
    precision verifies the memo's own claim: write more digits and you are held
    to more; write fewer and you are not punished for it.
    """
    def within(candidate: float) -> bool:
        """Is `candidate` inside the interval the memo's figure represents?

        Stated directly rather than by comparing rounded values, because
        rounding a tie is ambiguous: 20,825,000,000 to four significant
        figures is 20.82 under round-half-to-even and 20.83 under the
        round-half-up people are taught. Comparing rounded values rejects one
        of those arbitrarily; an interval accepts both, which is what "rounds
        to this figure" actually means.
        """
        if figure.value == 0:
            return candidate == 0
        from math import floor, log10
        last_digit = floor(log10(abs(figure.value))) - (figure.precision - 1)
        return abs(candidate - figure.value) <= 0.5 * (10 ** last_digit)

    for value in values:
        if within(value):
            return True
        # a percentage written against a pack ratio, and vice versa
        if value and (within(value * 100) or within(value / 100)):
            return True
    return False


def pack_grade(pack: str) -> int | None:
    m = re.search(r"\*\*Grade\s+(\d)", pack)
    return int(m.group(1)) if m else None


# A band label only claims a grade when it appears in a GRADING context. The
# governance doc says to check "any sentence containing a grade word", but taken
# literally that fires on ordinary English — "leverage is moderate" and
# "cash flow was strong" are not grade claims, and flagging them buries the real
# violations (D74). Caught by the five-violation test, which produced three
# false positives and missed nothing only by luck.
GRADING_CONTEXT = re.compile(
    r"\b(grade|graded|rating|rated|rate it|credit profile|profile is|"
    r"characteris|characteriz|classif|assess(?:ed|ment)?|scale|"
    r"investment.grade|speculative|we would consider)\b",
    re.IGNORECASE,
)


def check_grades(memo: str, grade: int | None) -> list:
    """Sentences claiming a grade other than the pack's (D73c).

    Two ways a sentence claims a grade: an explicit "Grade N", which always
    counts; or a band label INSIDE a grading context, which distinguishes
    "characterised as Very strong" from "cash flow was strong".
    """
    if grade is None:
        return []
    issues = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n{2,}", memo):
        low = " ".join(sentence.lower().split())
        if not low:
            continue
        claimed = None
        m = re.search(r"\bgrade\s+(\d)\b", low)
        if m:
            claimed = int(m.group(1))
        elif GRADING_CONTEXT.search(low):
            for label, value in GRADE_LABELS:      # longest first (D73c)
                if label in low:
                    claimed = value
                    break
        if claimed is not None and claimed != grade:
            issues.append((sentence.strip()[:160], claimed, grade))
    return issues


def _normalise_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip().strip("|").replace("|", " ")).lower()


def stamp_sections(memo: str, pack: str) -> list:
    """AI_INTERPRETED unless a section is verbatim from a pack table."""
    pack_lines = {_normalise_line(l) for l in pack.splitlines()
                  if l.strip().startswith("|")}
    sections, current, body = [], None, []
    for line in memo.splitlines():
        if line.startswith("#"):
            if current:
                sections.append((current, body))
            current, body = line.lstrip("# ").strip(), []
        elif current:
            body.append(line)
    if current:
        sections.append((current, body))

    stamped = []
    for name, lines in sections:
        content = [l for l in lines if l.strip()]
        verbatim = bool(content) and all(
            _normalise_line(l) in pack_lines for l in content)
        stamped.append((name, "VERBATIM_FROM_PACK" if verbatim
                        else "AI_INTERPRETED"))
    return stamped


def validate(memo: str, pack: str) -> Report:
    report = Report()
    values = pack_values(pack)
    for figure in extract_figures(memo):
        report.figures.append(figure)
        if figure.is_low_confidence:
            report.low_confidence.append(figure)
        elif matches(figure, values):
            report.verified.append(figure)
        else:
            report.unverified.append(figure)
    report.grade_issues = check_grades(memo, pack_grade(pack))
    report.sections = stamp_sections(memo, pack)
    report.reviewed_claimed = bool(
        re.search(r"^\s*status\s*:\s*reviewed", memo, re.I | re.M))
    return report


def render(report: Report) -> str:
    """The report. The limitation goes ABOVE the results, always (D74)."""
    L = [
        "=" * 72,
        "WHAT THIS VALIDATION DOES NOT TELL YOU",
        "=" * 72,
        "This checks that every number in the memo APPEARS in the evidence",
        "pack. It does NOT check that the numbers are used correctly.",
        "",
        "  - A figure cited under the wrong label passes: quoting the pack's",
        "    cash-flow figure as EBITDA is invisible to this check.",
        "  - True figures assembled into a false conclusion pass. The validator",
        "    reads numbers, not arguments.",
        "",
        "A CLEAN VALIDATION IS NOT A CLEAN MEMO. A human must read it.",
        "=" * 72,
        "",
    ]
    L += [f"Figures found:        {len(report.figures)}",
          f"  verified in pack:   {len(report.verified)}",
          f"  UNVERIFIED:         {len(report.unverified)}",
          f"  low-confidence:     {len(report.low_confidence)}", ""]

    if report.unverified:
        L += ["Unverified figures — these do not appear in the pack at the",
              "precision the memo states:", ""]
        L += [f"  - {f.text}" for f in report.unverified] + [""]

    if report.low_confidence:
        L += ["Low-confidence matches — NOT counted as verified:", "",
              "  A bare number below 100, or a 4-digit year, will coincide with",
              "  something in a pack of dozens of figures by chance. Counting",
              "  those as verified would inflate the pass rate and make the",
              "  verified count meaningless. They are listed so a human checks",
              "  them, not because they are wrong.", ""]
        L += [f"  - {f.text}" for f in report.low_confidence] + [""]

    if report.grade_issues:
        L += ["Grade mismatches — the memo may not state a grade other than",
              "the pack's:", ""]
        for sentence, claimed, actual in report.grade_issues:
            L += [f"  - claims grade {claimed}, pack says {actual}:",
                  f"    \"{sentence}\""]
        L += [""]

    L += ["Section status:", ""]
    L += [f"  {status:20} {name}" for name, status in report.sections] + [""]

    if report.reviewed_claimed and not report.may_be_reviewed:
        L += ["REJECTED: the memo claims Status: REVIEWED, but unverified "
              "figures or grade mismatches remain.", ""]
    elif report.may_be_reviewed:
        L += ["Deterministic checks passed. A human must still review and sign "
              "off — see the limitation above.", ""]
    else:
        L += ["Not eligible to be marked REVIEWED until the items above are "
              "resolved.", ""]
    return "\n".join(L)
