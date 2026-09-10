"""Fact selection (docs/data-sources.md rules 1-6; DECISIONS D13-D16).

Selects annual facts from a raw SEC companyfacts dict. Selection only — tag
mapping is Task 7, so everything here works on raw us-gaap tag names.

The authority for expected behaviour is
tests/fixtures/companyfacts_minimal_expected.md: if this module and that
document disagree, this module is wrong.

Rule order is load-bearing (D14): rules 1-3 filter, then rule 4 dedups the
survivors. Facts are never grouped by their `fy` stamp — SEC stamps `fy` with
the filing's fiscal year, not the fact's period, so two different periods can
share an `fy`. Period identity is always (tag, end).
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date

ANNUAL_FORMS = {"10-K", "10-K/A"}       # rule 1
DURATION_MIN_DAYS = 350                 # rule 2, inclusive (per the expectations doc)
DURATION_MAX_DAYS = 380
FYE_CLUSTER_DAYS = 14                   # D16(1): duration ends this close = same fiscal year
IGNORED_UNITS = {"shares", "pure"}      # rule 5: ignored for financial items


@dataclass
class SelectedFact:
    tag: str
    val: float
    unit: str
    end: str
    start: str | None
    fy: int | None
    fp: str | None
    form: str | None
    filed: str | None
    accn: str | None
    frame: str | None
    status: str = "CURRENT"             # CURRENT | SUPERSEDED | DUPLICATE
    superseded_by: str | None = None    # accession of the displacing filing


@dataclass
class UnavailableFact:
    tag: str
    unit: str
    end: str | None
    reason_code: str                    # FOREIGN_UNIT | NO_FYE_ANCHOR | AMBIGUOUS_FYE
    accn: str | None = None


@dataclass
class SelectionResult:
    selected: list[SelectedFact]        # current facts
    superseded: list[SelectedFact]      # kept, superseded_by set — never deleted
    duplicates: list[SelectedFact]      # equal-value later copies (D15), no supersession
    unavailable: list[UnavailableFact]
    warnings: list[str]
    fiscal_year_ends: list[str]         # derived FYE dates, ISO, sorted (D13)


def _fact_from_raw(tag: str, unit: str, raw: dict) -> SelectedFact:
    return SelectedFact(
        tag=tag,
        val=raw.get("val"),
        unit=unit,
        end=raw.get("end"),
        start=raw.get("start"),
        fy=raw.get("fy"),
        fp=raw.get("fp"),
        form=raw.get("form"),
        filed=raw.get("filed"),
        accn=raw.get("accn"),
        frame=raw.get("frame"),
    )


def _derive_fiscal_year_ends(duration_facts: list[SelectedFact]):
    """D13: fiscal year ends come from accepted duration facts' end dates.

    Distinct end dates within FYE_CLUSTER_DAYS of each other are treated as
    the same fiscal year (D16(1)); within a cluster the most common date wins
    with a warning, and an exact tie chooses no anchor at all (D16(2)).
    """
    counts = Counter(sf.end for sf in duration_facts)
    dates = sorted(counts)

    clusters: list[list[str]] = []
    cluster: list[str] = []
    prev = None
    for d in dates:
        dd = date.fromisoformat(d)
        if prev is not None and (dd - prev).days > FYE_CLUSTER_DAYS:
            clusters.append(cluster)
            cluster = []
        cluster.append(d)
        prev = dd
    if cluster:
        clusters.append(cluster)

    fyes: set[str] = set()
    warnings: list[str] = []
    ambiguous: set[str] = set()
    for cl in clusters:
        if len(cl) == 1:
            fyes.add(cl[0])
            continue
        detail = ", ".join(f"{d} x{counts[d]}" for d in cl)
        best = max(counts[d] for d in cl)
        winners = [d for d in cl if counts[d] == best]
        if len(winners) == 1:
            fyes.add(winners[0])
            warnings.append(
                f"Fiscal year end disagreement ({detail}); "
                f"using most common {winners[0]} (D13)"
            )
        else:
            ambiguous.update(cl)
            warnings.append(
                f"Fiscal year end tie ({detail}); no anchor chosen — instants "
                f"near these dates are UNAVAILABLE with AMBIGUOUS_FYE (D16)"
            )
    return fyes, warnings, ambiguous


def _near_ambiguous(end: str, ambiguous: set[str]) -> bool:
    e = date.fromisoformat(end)
    return any(
        abs((e - date.fromisoformat(a)).days) <= FYE_CLUSTER_DAYS for a in ambiguous
    )


def select_annual_facts(companyfacts: dict) -> SelectionResult:
    us_gaap = companyfacts.get("facts", {}).get("us-gaap", {})

    unavailable: list[UnavailableFact] = []
    duration_facts: list[SelectedFact] = []
    instant_facts: list[SelectedFact] = []

    for tag, tag_obj in us_gaap.items():
        for unit, facts in tag_obj.get("units", {}).items():
            if unit in IGNORED_UNITS:
                continue
            if unit != "USD":
                # rule 5: non-USD monetary units are UNAVAILABLE, never converted
                for raw in facts:
                    unavailable.append(
                        UnavailableFact(
                            tag=tag,
                            unit=unit,
                            end=raw.get("end"),
                            reason_code="FOREIGN_UNIT",
                            accn=raw.get("accn"),
                        )
                    )
                continue
            for raw in facts:
                # rule 1: annual facts from annual filings only
                if raw.get("fp") != "FY" or raw.get("form") not in ANNUAL_FORMS:
                    continue
                sf = _fact_from_raw(tag, unit, raw)
                if sf.start is not None:
                    # rule 2: full-year durations only
                    days = (date.fromisoformat(sf.end) - date.fromisoformat(sf.start)).days
                    if DURATION_MIN_DAYS <= days <= DURATION_MAX_DAYS:
                        duration_facts.append(sf)
                else:
                    instant_facts.append(sf)

    fyes, warnings, ambiguous = _derive_fiscal_year_ends(duration_facts)
    anchored_filings = {sf.accn for sf in duration_facts}

    # rule 3, with D13/D16 anchoring
    kept_instants: list[SelectedFact] = []
    for sf in instant_facts:
        if sf.end in fyes:
            kept_instants.append(sf)
        elif _near_ambiguous(sf.end, ambiguous):
            unavailable.append(
                UnavailableFact(
                    tag=sf.tag, unit=sf.unit, end=sf.end,
                    reason_code="AMBIGUOUS_FYE", accn=sf.accn,
                )
            )
        elif sf.accn in anchored_filings:
            pass  # the filing has an anchor; this instant just isn't at a year end
        else:
            unavailable.append(
                UnavailableFact(
                    tag=sf.tag, unit=sf.unit, end=sf.end,
                    reason_code="NO_FYE_ANCHOR", accn=sf.accn,
                )
            )

    # rule 4 (last, per D14), with D15's equal-value handling
    groups: dict = defaultdict(list)
    for sf in duration_facts + kept_instants:
        groups[(sf.tag, sf.end)].append(sf)

    selected: list[SelectedFact] = []
    superseded: list[SelectedFact] = []
    duplicates: list[SelectedFact] = []
    for facts in groups.values():
        facts.sort(key=lambda s: (s.filed or "", s.accn or ""))  # D16(4) tiebreak
        current = facts[0]
        for later in facts[1:]:
            if later.val == current.val:
                later.status = "DUPLICATE"          # D15: identical value, no supersession
                duplicates.append(later)
            else:
                current.status = "SUPERSEDED"       # value changed: real restatement
                current.superseded_by = later.accn
                superseded.append(current)
                current = later
        current.status = "CURRENT"
        selected.append(current)

    order = lambda s: (s.tag, s.end, s.accn or "")
    return SelectionResult(
        selected=sorted(selected, key=order),
        superseded=sorted(superseded, key=order),
        duplicates=sorted(duplicates, key=order),
        unavailable=sorted(unavailable, key=lambda u: (u.tag, u.end or "", u.accn or "")),
        warnings=warnings,
        fiscal_year_ends=sorted(fyes),
    )
