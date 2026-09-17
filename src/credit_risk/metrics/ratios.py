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
from datetime import date

from credit_risk import config
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
NO_DEBT = "NO_DEBT"
NON_POSITIVE_CAPITAL = "NON_POSITIVE_CAPITAL"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
INVENTORY_UNKNOWN = "INVENTORY_UNKNOWN"
INTEGRITY_FAILED = "INTEGRITY_FAILED"

_KINDS = {
    NEGATIVE_EBITDA: EVIDENCE,
    NEGATIVE_EARNINGS: EVIDENCE,
    # an unlevered company cannot have a debt ratio — a good thing, not a
    # shortfall, so it must not cap the grade (D42a)
    NO_INTEREST_NO_DEBT: NEITHER,
    NO_DEBT: NEITHER,
    INTEREST_MISSING_WITH_DEBT: GAP,
    ZERO_DENOMINATOR: GAP,
    NEGATIVE_DENOMINATOR: GAP,
    NON_POSITIVE_CAPITAL: GAP,
    # an input is provably wrong, so nothing derived from it is knowable.
    # A gap — we do not know — not evidence about the company (D76).
    INTEGRITY_FAILED: GAP,
    INSUFFICIENT_DATA: GAP,
    INVENTORY_UNKNOWN: GAP,
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


METRICS = (
    # leverage
    "debt_to_ebitda", "net_debt_to_ebitda", "debt_to_capital",
    # coverage
    "ebit_interest_cover", "ebitda_interest_cover",
    # liquidity
    "current_ratio", "quick_ratio", "cash_to_current_liabilities",
    "cash_to_debt",
    # cash flow
    "fcf_margin", "fcf_to_debt", "cfo_to_debt", "capex_to_revenue",
    # business performance
    "revenue_growth", "ebitda_margin", "ebit_margin", "net_margin",
)
# ROA and ROE are deliberately absent: dropped from v1 as equity-holder
# metrics rather than credit-core (docs/credit-methodology.md).


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
    # the offending denominator, so a NEGATIVE_DENOMINATOR warning can name it
    denominator: tuple[str, float] | None = None

    @property
    def kind(self) -> str | None:
        return reason_kind(self.reason_code)


def _calculated(metric, end, value, method, inputs):
    return MetricResult(metric=metric, end=end, value=value, method=method,
                        data_status="CALCULATED", inputs=inputs)


def _unavailable(metric, end, reason_code, denominator=None):
    return MetricResult(metric=metric, end=end, value=None, method=None,
                        data_status="UNAVAILABLE", reason_code=reason_code,
                        denominator=denominator)


def _simple_ratio(metric, end, values, numerator, denominator, method=None):
    """numerator / denominator under the general rules.

    Missing input -> MISSING_INPUT:<concept>; zero denominator ->
    ZERO_DENOMINATOR; negative denominator -> NEGATIVE_DENOMINATOR. Negative
    numerators are allowed and reported as negative.
    """
    for name in (numerator, denominator):
        if name not in values:
            return _unavailable(metric, end, f"MISSING_INPUT:{name}")
    d = values[denominator]
    if d == 0:
        return _unavailable(metric, end, ZERO_DENOMINATOR)
    if d < 0:
        return _unavailable(metric, end, NEGATIVE_DENOMINATOR, (denominator, d))
    return _calculated(metric, end, values[numerator] / d,
                       method or f"{numerator} / {denominator}",
                       [(numerator, end), (denominator, end)])


def _ebitda_ratio(metric, end, values, numerator):
    """An EBITDA-denominated leverage ratio: ebitda <= 0 is evidence.

    The methodology puts *all* EBITDA-based leverage UNAVAILABLE with
    NEGATIVE_EBITDA rather than letting a negative denominator produce a
    negative leverage figure, which would read as low leverage.
    """
    if numerator not in values:
        return _unavailable(metric, end, f"MISSING_INPUT:{numerator}")
    if "ebitda" not in values:
        return _unavailable(metric, end, "MISSING_INPUT:ebitda")
    ebitda = values["ebitda"]
    if ebitda <= 0:
        return _unavailable(metric, end, NEGATIVE_EBITDA)
    return _calculated(metric, end, values[numerator] / ebitda,
                       f"{numerator} / ebitda",
                       [(numerator, end), ("ebitda", end)])


def _debt_denominated(metric, end, values, numerator):
    """cash/fcf/cfo over total_debt: zero debt refuses, never infinite.

    NO_DEBT is kind NEITHER (D42a) — an unlevered company is not a data gap.
    """
    if numerator not in values:
        return _unavailable(metric, end, f"MISSING_INPUT:{numerator}")
    if "total_debt" not in values:
        return _unavailable(metric, end, "MISSING_INPUT:total_debt")
    debt = values["total_debt"]
    if debt == 0:
        return _unavailable(metric, end, NO_DEBT)
    if debt < 0:
        return _unavailable(metric, end, NEGATIVE_DENOMINATOR, ("total_debt", debt))
    return _calculated(metric, end, values[numerator] / debt,
                       f"{numerator} / total_debt",
                       [(numerator, end), ("total_debt", end)])


def _interest_cover(metric, end, values, numerator, negative_code):
    """The coverage gates, shared by both cover ratios.

    The interest gate runs before the numerator check (D41c): a missing
    denominator means the ratio was never computable, while a non-positive
    numerator is a claim about a ratio you could have computed.
    """
    interest = values.get("interest_expense")
    if interest is None or interest <= 0:
        debt = values.get("total_debt")
        if debt is None:
            return _unavailable(metric, end, "MISSING_INPUT:total_debt")
        if debt == 0:
            return _unavailable(metric, end, NO_INTEREST_NO_DEBT)
        return _unavailable(metric, end, INTEREST_MISSING_WITH_DEBT)
    if numerator not in values:
        return _unavailable(metric, end, f"MISSING_INPUT:{numerator}")
    value = values[numerator]
    if value <= 0:
        return _unavailable(metric, end, negative_code)
    return _calculated(metric, end, value / interest,
                       f"{numerator} / interest_expense",
                       [(numerator, end), ("interest_expense", end)])


def _debt_to_capital(end, values):
    """total_debt / (total_debt + equity).

    Negative equity can drive capital to zero or below. That is NOT the
    general zero-denominator case: the denominator is a computed sum, so the
    record names what actually happened (NON_POSITIVE_CAPITAL) rather than
    reporting a bare arithmetic fact.
    """
    for name in ("total_debt", "equity"):
        if name not in values:
            return _unavailable("debt_to_capital", end, f"MISSING_INPUT:{name}")
    capital = values["total_debt"] + values["equity"]
    if capital <= 0:
        return _unavailable("debt_to_capital", end, NON_POSITIVE_CAPITAL)
    return _calculated("debt_to_capital", end, values["total_debt"] / capital,
                       "total_debt / (total_debt + equity)",
                       [("total_debt", end), ("equity", end)])


def _quick_ratio(end, values, company_reports_inventory):
    """(current_assets - inventory) / current_liabilities.

    Missing inventory is zero ONLY for a company that reports no inventory in
    any period (D42b). For a company that does report it, a period without it
    refuses: subtracting an unknown inventory would fabricate a number, and
    treating it as zero would overstate the ratio.
    """
    if "current_assets" not in values:
        return _unavailable("quick_ratio", end, "MISSING_INPUT:current_assets")
    if "current_liabilities" not in values:
        return _unavailable("quick_ratio", end, "MISSING_INPUT:current_liabilities")
    inputs = [("current_assets", end), ("current_liabilities", end)]
    if "inventory" in values:
        inventory = values["inventory"]
        inputs.append(("inventory", end))
    elif company_reports_inventory:
        return _unavailable("quick_ratio", end, INVENTORY_UNKNOWN)
    else:
        inventory = 0.0            # non-inventory business
    d = values["current_liabilities"]
    if d == 0:
        return _unavailable("quick_ratio", end, ZERO_DENOMINATOR)
    if d < 0:
        return _unavailable("quick_ratio", end, NEGATIVE_DENOMINATOR,
                            ("current_liabilities", d))
    return _calculated("quick_ratio", end,
                       (values["current_assets"] - inventory) / d,
                       "(current_assets - inventory) / current_liabilities",
                       inputs)


def _revenue_growth(end, values, prior_end, prior_values, window):
    """revenue_t / revenue_(t-1) - 1, over genuinely consecutive periods.

    Two separate rules, and both are needed (D43):

    - **Eligibility** (D40): the prior period is the most recent one that
      actually *resolves revenue*, not whichever row happens to precede this
      one. A phantom period — one resolving no concepts at all — is not a link
      in the chain, and pairing against it discards a legitimate comparison.
    - **Window** (D42c/D36): that pair must then sit within
      continuity_window_days, so a genuine multi-year gap is never labelled
      one-year growth.

    `prior_end` is supplied already filtered by the caller; the window test
    below is what rejects a pair that is eligible but too far apart.
    """
    if "revenue" not in values:
        return _unavailable("revenue_growth", end, "MISSING_INPUT:revenue")
    if prior_end is None or "revenue" not in (prior_values or {}):
        return _unavailable("revenue_growth", end, INSUFFICIENT_DATA)
    gap = (date.fromisoformat(end) - date.fromisoformat(prior_end)).days
    low, high = window
    if not (low <= gap <= high):
        return _unavailable("revenue_growth", end, INSUFFICIENT_DATA)
    prior = prior_values["revenue"]
    if prior == 0:
        return _unavailable("revenue_growth", end, ZERO_DENOMINATOR)
    if prior < 0:
        return _unavailable("revenue_growth", end, NEGATIVE_DENOMINATOR,
                            ("revenue", prior))
    return _calculated("revenue_growth", end, values["revenue"] / prior - 1,
                       "revenue_t / revenue_(t-1) - 1",
                       [("revenue", end), ("revenue", prior_end)])


@dataclass
class MetricsReport:
    metrics: list[MetricResult]
    events: list[DataQualityEvent]    # NEGATIVE_DENOMINATOR warnings (D41e)


def compute_metrics(mapping, composites, cfg: dict | None = None,
                    failed_periods=()) -> MetricsReport:
    """Every Phase 5 ratio for every period the company has.

    A period in `failed_periods` — one that FAILED a fail-severity integrity
    check — computes no metric at all (D76). Its inputs are not merely
    missing, they are arithmetically impossible, and a figure derived from
    an impossible input must not be reachable: marking it and leaving it in
    place would make every downstream consumer responsible for honouring
    the marker, and one that forgets prints a wrong number.

    `company_reports_inventory` is the one company-wide fact any metric needs
    (D42b), computed once here rather than threaded through as a flag.
    """
    if cfg is None:
        cfg = config.integrity()
    window = cfg["continuity_window_days"]

    by_period: dict[str, dict[str, float]] = {}
    for c in mapping.concepts:
        by_period.setdefault(c.end, {})[c.concept] = c.value
    for c in composites:
        if c.data_status == "CALCULATED":
            by_period.setdefault(c.end, {})[c.concept] = c.value
    for u in mapping.unavailable:
        by_period.setdefault(u.period_end, {})

    # cross-period test, resolved-concept reading (D42b)
    company_reports_inventory = any(
        c.concept == "inventory" for c in mapping.concepts)

    ends = sorted(by_period)
    # Periods that actually resolve revenue, in order. revenue_growth pairs
    # against the most recent of these, never against whichever row precedes
    # it — a phantom period between two real ones is not a link (D43/D40).
    failed = set(failed_periods)
    # A failed period is not a pairing anchor either: growth measured
    # against an impossible base is itself impossible (D76).
    revenue_ends = [e for e in ends
                    if "revenue" in by_period[e] and e not in failed]

    metrics: list[MetricResult] = []
    events: list[DataQualityEvent] = []

    for end in ends:
        if end in failed:
            metrics.extend(_unavailable(m, end, INTEGRITY_FAILED)
                           for m in METRICS)
            continue
        values = by_period[end]
        earlier = [e for e in revenue_ends if e < end]
        prior_end = earlier[-1] if earlier else None
        prior_values = by_period.get(prior_end) if prior_end else None

        results = [
            # leverage
            _ebitda_ratio("debt_to_ebitda", end, values, "total_debt"),
            _ebitda_ratio("net_debt_to_ebitda", end, values, "net_debt"),
            _debt_to_capital(end, values),
            # coverage — two distinct metrics, never presented as the same thing
            _interest_cover("ebit_interest_cover", end, values, "ebit",
                            NEGATIVE_EARNINGS),
            _interest_cover("ebitda_interest_cover", end, values, "ebitda",
                            NEGATIVE_EBITDA),
            # liquidity
            _simple_ratio("current_ratio", end, values,
                          "current_assets", "current_liabilities"),
            _quick_ratio(end, values, company_reports_inventory),
            _simple_ratio("cash_to_current_liabilities", end, values,
                          "cash", "current_liabilities"),
            _debt_denominated("cash_to_debt", end, values, "cash"),
            # cash flow
            _simple_ratio("fcf_margin", end, values, "fcf", "revenue"),
            _debt_denominated("fcf_to_debt", end, values, "fcf"),
            _debt_denominated("cfo_to_debt", end, values, "cfo"),
            _simple_ratio("capex_to_revenue", end, values, "capex", "revenue"),
            # business performance
            _revenue_growth(end, values, prior_end, prior_values, window),
            _simple_ratio("ebitda_margin", end, values, "ebitda", "revenue"),
            _simple_ratio("ebit_margin", end, values, "ebit", "revenue"),
            _simple_ratio("net_margin", end, values, "net_income", "revenue"),
        ]
        metrics.extend(results)

        for r in results:
            if r.reason_code == NEGATIVE_DENOMINATOR:
                # the general rules require the negative denominator itself to
                # be surfaced, not just the refusal (D41e)
                name, value = r.denominator or ("denominator", float("nan"))
                events.append(DataQualityEvent(
                    code=NEGATIVE_DENOMINATOR, concept=r.metric, period_end=end,
                    detail=f"{r.metric}: {name} is {value:,.0f}, negative",
                ))
    return MetricsReport(metrics=metrics, events=events)
