"""Tag mapping (docs/data-sources.md "Normalisation"; DECISIONS D11, D17).

Consumes the output of select_annual_facts and produces internal concepts.
The candidate tag lists — and their order, which decides first-found-wins —
come from config/tag_map.yaml only (CLAUDE.md rule 6): nothing here names a
concept or a tag.

Mapping only: composite concepts (total_debt, ebitda, ...) and the
gross_profit calculated fallback are Task 9 — they produce CALCULATED values,
and everything mapped here is REPORTED.
"""

from collections import defaultdict
from dataclasses import dataclass

from credit_risk import config
from credit_risk.normalise import quality
from credit_risk.normalise.quality import DataQualityEvent
from credit_risk.normalise.selection import SelectionResult


@dataclass
class MappedConcept:
    concept: str                # internal name, e.g. cost_of_revenue
    value: float
    unit: str
    source_tag: str             # the candidate tag that actually supplied the value
    label: str | None           # SEC's reported label for that tag, preserved
    end: str
    start: str | None
    fy: int | None
    fp: str | None
    form: str | None
    filed: str | None
    accn: str | None
    frame: str | None
    data_status: str = "REPORTED"


@dataclass
class UnavailableConcept:
    concept: str
    period_end: str
    reason_code: str            # NO_CANDIDATE_TAG


@dataclass
class MappingResult:
    concepts: list[MappedConcept]
    unavailable: list[UnavailableConcept]
    warnings: list[DataQualityEvent]


def map_concepts(selection: SelectionResult, tag_map: dict | None = None) -> MappingResult:
    """Resolve internal concepts from selected facts, per period.

    First candidate tag present for a period wins and is recorded as
    source_tag. A later candidate present at the same period with a DIFFERENT
    value triggers a CANDIDATE_TAG_DISAGREEMENT warning (D17) — equal-value
    co-tagging is routine XBRL practice and stays silent. A concept with no
    candidate present for a period is UNAVAILABLE with NO_CANDIDATE_TAG;
    values are never borrowed from another period or concept.

    Only CURRENT facts are mapped — superseded and duplicate facts are audit
    trail (D17).
    """
    if tag_map is None:
        tag_map = config.tag_map()

    facts_by_tag: dict[str, dict[str, object]] = defaultdict(dict)
    for f in selection.selected:
        facts_by_tag[f.tag][f.end] = f

    concepts: list[MappedConcept] = []
    unavailable: list[UnavailableConcept] = []
    warnings: list[DataQualityEvent] = []

    for concept, candidates in tag_map.items():
        # canonical fiscal year ends, plus any period a candidate actually has,
        # so an odd-period selected fact can never be dropped silently (D17)
        periods = set(selection.fiscal_year_ends)
        for candidate in candidates:
            periods.update(facts_by_tag.get(candidate, {}))

        for end in sorted(periods):
            chosen = None
            for candidate in candidates:
                fact = facts_by_tag.get(candidate, {}).get(end)
                if fact is None:
                    continue
                if chosen is None:
                    chosen = fact
                elif fact.val != chosen.val:
                    warnings.append(
                        DataQualityEvent(
                            code=quality.CANDIDATE_TAG_DISAGREEMENT,
                            concept=concept,
                            tag=chosen.tag,
                            period_end=end,
                            accession=chosen.accn,
                            detail=(
                                f"{concept} {end}: using {chosen.tag}={chosen.val}, "
                                f"but {fact.tag}={fact.val} is also present"
                            ),
                        )
                    )
            if chosen is None:
                unavailable.append(
                    UnavailableConcept(concept, end, "NO_CANDIDATE_TAG")
                )
            else:
                concepts.append(
                    MappedConcept(
                        concept=concept,
                        value=chosen.val,
                        unit=chosen.unit,
                        source_tag=chosen.tag,
                        label=chosen.label,
                        end=chosen.end,
                        start=chosen.start,
                        fy=chosen.fy,
                        fp=chosen.fp,
                        form=chosen.form,
                        filed=chosen.filed,
                        accn=chosen.accn,
                        frame=chosen.frame,
                    )
                )

    return MappingResult(
        concepts=sorted(concepts, key=lambda c: (c.concept, c.end)),
        unavailable=sorted(unavailable, key=lambda u: (u.concept, u.period_end)),
        warnings=warnings,
    )
