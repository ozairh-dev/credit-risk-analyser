"""Credit ratios (Task 11, docs/credit-methodology.md "Metrics").

Task 11 implements three of the seventeen — net_debt_to_ebitda,
ebit_interest_cover and current_ratio — to prove the whole path works with
provenance intact before the pattern is replicated across the rest.

Ratios read the per-period concept values that mapping and composites
produced; they never touch facts. Provenance therefore runs
metric_inputs -> concepts -> concept_inputs -> facts, a chain Tasks 9 and 10
already built.
"""

from dataclasses import dataclass, field

from credit_risk.normalise.quality import DataQualityEvent

# Reason kinds (D9, D41a). Derived from the reason code, never stored: a
# second copy could only drift, and Phase 6 reads this mapping directly.
EVIDENCE = "EVIDENCE"   # the company's real condition — scores 0, worst band
GAP = "GAP"             # we do not know — dropped, grade capped
NEITHER = "NEITHER"     # a good thing, not a shortfall — weight redistributed

NEGATIVE_EBITDA = "NEGATIVE_EBITDA"
NEGATIVE_EARNINGS = "NEGATIVE_EARNINGS"
NO_INTEREST_NO_DEBT = "NO_INTEREST_NO_DEBT"
INTEREST_MISSING_WITH_DEBT = "INTEREST_MISSING_WITH_DEBT"
ZERO_DENOMINATOR = "ZERO_DENOMINATOR"
NEGATIVE_DENOMINATOR = "NEGATIVE_DENOMINATOR"

_KINDS = {
    NEGATIVE_EBITDA: EVIDENCE,
    NEGATIVE_EARNINGS: EVIDENCE,
    NO_INTEREST_NO_DEBT: NEITHER,
    INTEREST_MISSING_WITH_DEBT: GAP,
    ZERO_DENOMINATOR: GAP,
    NEGATIVE_DENOMINATOR: GAP,
}


def reason_kind(reason_code: str | None) -> str | None:
    """EVIDENCE | GAP | NEITHER for a reason code, or None if it has no code.

    `MISSING_INPUT:<concept>` is always a gap — the concept name varies, so it
    is matched by prefix rather than listed.
    """
    if reason_code is None:
        return None
    if reason_code.startswith("MISSING_INPUT:"):
        return GAP
    return _KINDS[reason_code]


METRICS = ("net_debt_to_ebitda", "ebit_interest_cover", "current_ratio")


@dataclass
class MetricResult:
    metric: str
    end: str
    value: float | None
    method: str | None
    data_status: str                      # CALCULATED | UNAVAILABLE
    reason_code: str | None = None
    inputs: list[tuple[str, str]] = field(default_factory=list)  # (concept, end)
    unit: str = "ratio"

    @property
    def kind(self) -> str | None:
        return reason_kind(self.reason_code)


def _calculated(metric, end, value, method, inputs):
    return MetricResult(metric=metric, end=end, value=value, method=method,
                        data_status="CALCULATED", inputs=inputs)


def _unavailable(metric, end, reason_code):
    return MetricResult(metric=metric, end=end, value=None, method=None,
                        data_status="UNAVAILABLE", reason_code=reason_code)


def _net_debt_to_ebitda(end, values):
    """net_debt / ebitda. Negative net debt (net cash) is valid and negative."""
    if "net_debt" not in values:
        return _unavailable("net_debt_to_ebitda", end, "MISSING_INPUT:net_debt")
    if "ebitda" not in values:
        return _unavailable("net_debt_to_ebitda", end, "MISSING_INPUT:ebitda")
    ebitda = values["ebitda"]
    if ebitda <= 0:
        # zero takes this code too: it names the worst band, not the sign (D41d)
        return _unavailable("net_debt_to_ebitda", end, NEGATIVE_EBITDA)
    return _calculated("net_debt_to_ebitda", end, values["net_debt"] / ebitda,
                       "net_debt / ebitda",
                       [("net_debt", end), ("ebitda", end)])


def _ebit_interest_cover(end, values):
    """ebit / interest_expense, with the coverage table's gates.

    The interest gate runs before the earnings check (D41c): a missing
    denominator means the ratio was never computable, while negative earnings
    is a statement about a ratio you could have computed.
    """
    interest = values.get("interest_expense")
    # negative interest is a tagging artefact, not free money — same as zero (D41f)
    if interest is None or interest <= 0:
        debt = values.get("total_debt")
        if debt is None:
            # the gate itself could not be evaluated (D41b)
            return _unavailable("ebit_interest_cover", end, "MISSING_INPUT:total_debt")
        if debt == 0:
            return _unavailable("ebit_interest_cover", end, NO_INTEREST_NO_DEBT)
        return _unavailable("ebit_interest_cover", end, INTEREST_MISSING_WITH_DEBT)
    if "ebit" not in values:
        return _unavailable("ebit_interest_cover", end, "MISSING_INPUT:ebit")
    ebit = values["ebit"]
    if ebit <= 0:
        return _unavailable("ebit_interest_cover", end, NEGATIVE_EARNINGS)
    return _calculated("ebit_interest_cover", end, ebit / interest,
                       "ebit / interest_expense",
                       [("ebit", end), ("interest_expense", end)])


def _current_ratio(end, values):
    """current_assets / current_liabilities, under the general denominator rules."""
    if "current_assets" not in values:
        return _unavailable("current_ratio", end, "MISSING_INPUT:current_assets")
    if "current_liabilities" not in values:
        return _unavailable("current_ratio", end, "MISSING_INPUT:current_liabilities")
    denominator = values["current_liabilities"]
    if denominator == 0:
        return _unavailable("current_ratio", end, ZERO_DENOMINATOR)
    if denominator < 0:
        return _unavailable("current_ratio", end, NEGATIVE_DENOMINATOR)
    return _calculated("current_ratio", end, values["current_assets"] / denominator,
                       "current_assets / current_liabilities",
                       [("current_assets", end), ("current_liabilities", end)])


@dataclass
class MetricsReport:
    metrics: list[MetricResult]
    events: list[DataQualityEvent]    # NEGATIVE_DENOMINATOR warnings (D41e)


def compute_metrics(mapping, composites) -> MetricsReport:
    """The three Task 11 ratios for every period the company has."""
    by_period: dict[str, dict[str, float]] = {}
    for c in mapping.concepts:
        by_period.setdefault(c.end, {})[c.concept] = c.value
    for c in composites:
        if c.data_status == "CALCULATED":
            by_period.setdefault(c.end, {})[c.concept] = c.value
    for u in mapping.unavailable:
        by_period.setdefault(u.period_end, {})

    metrics: list[MetricResult] = []
    events: list[DataQualityEvent] = []
    for end in sorted(by_period):
        values = by_period[end]
        results = [
            _net_debt_to_ebitda(end, values),
            _ebit_interest_cover(end, values),
            _current_ratio(end, values),
        ]
        metrics.extend(results)
        for r in results:
            if r.reason_code == NEGATIVE_DENOMINATOR:
                # the general rules require the negative denominator itself to
                # be surfaced, not just the refusal (D41e)
                events.append(DataQualityEvent(
                    code=NEGATIVE_DENOMINATOR, concept=r.metric, period_end=end,
                    detail=(f"{r.metric}: denominator "
                            f"{values['current_liabilities']:,.0f} is negative"),
                ))
    return MetricsReport(metrics=metrics, events=events)
