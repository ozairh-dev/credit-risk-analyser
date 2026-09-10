"""Structured data-quality events (Task 8).

Pipeline warnings are first-class records, not free-text notes: they are
stored in the data_quality_events table, counted per code, and drive the
data-quality panel. Selection and mapping both emit these.
"""

from dataclasses import dataclass

# Codes. Phase 4 adds INTEGRITY_* codes alongside these.
FYE_DISAGREEMENT = "FYE_DISAGREEMENT"                      # D13: most common end wins
FYE_TIE = "FYE_TIE"                                        # D16(2): no anchor chosen
SAME_DAY_REFILING_TIEBREAK = "SAME_DAY_REFILING_TIEBREAK"  # D16(4)
CANDIDATE_TAG_DISAGREEMENT = "CANDIDATE_TAG_DISAGREEMENT"  # D17(1)


@dataclass
class DataQualityEvent:
    code: str
    detail: str                      # human-readable message
    tag: str | None = None
    concept: str | None = None
    period_end: str | None = None
    accession: str | None = None
