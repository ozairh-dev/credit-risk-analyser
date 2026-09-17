"""Deterministic stress scenarios (Phase 8, docs/credit-methodology.md).

Implements the propagation rules exactly as written, both EBITDA modes, and
answers "which assumption caused the change" by **driver attribution** — each
shock run alone against base — rather than by narrative.

Five output duties were recorded as decisions BEFORE this code existed, and
every one is carried in the assumptions block rather than left to the docs:

    D53a  print the fixed_cost_share used (operating-leverage mode)
    D54   print the floating_share used, and that the split is unreachable
    D53b  name which new_debt_rate was used and why
    D57b  liquidity is unstressed: 20 of 100 weight cannot move
    D57a  the trend component carries the base-period verdict

A duty recorded but unenforced is exactly D43's failure mode, so each is also
pinned by its own test.
"""

from dataclasses import dataclass, field

from credit_risk import config
from credit_risk.metrics.ratios import MetricResult
from credit_risk.scoring.engine import score_period

SHOCKS = ("revenue_shock", "margin_shock", "rate_shock_bps",
          "additional_debt", "capex_shock")

# metrics the methodology recomputes under stress. Liquidity is deliberately
# absent — balance-sheet liquidity is held at base (D57b).
STRESSED_METRICS = (
    "net_debt_to_ebitda", "debt_to_ebitda", "ebit_interest_cover",
    "ebitda_interest_cover", "fcf_to_debt", "fcf_margin", "ebitda_margin",
)

# FCF-derived metrics are REPORTED in the stress results but excluded from the
# stressed GRADE (D70). The propagation approximates CFO as
# ebitda - interest - tax with working capital flat, while the base composite
# uses reported CFO — so at zero shock they are different quantities, not the
# same quantity unshocked (D64). Measured at 43 companies: 88 of 647 base runs
# changed grade at ZERO shock, and 10 runs IMPROVED under Severe, BKNG by two
# grades. Scoring them means scoring the approximation gap.
#
# Re-measured after D75's refusal inheritance landed, to check whether this rule
# had become redundant: it has NOT. With inheritance in place but this
# suppression disabled, 71 base runs still change grade at zero shock. The two
# rules address different causes — D75 stops the engine inventing a metric the
# base refused, this stops D64's CFO approximation gap moving a grade — and
# neither subsumes the other. Do not remove it on the assumption that D75
# covers it.
FCF_DERIVED = ("fcf_to_debt", "fcf_margin")

EXPLICIT, IMPLIED, SUBSTITUTED, NOT_NEEDED = (
    "explicit", "implied", "default_substituted", "not_needed")

SIMPLIFICATIONS = (
    "D&A held flat",
    "whole debt stack reprices at floating_share = 1.0",
    "working capital held flat (CFO approximated as ebitda - interest - tax)",
    "no cash sweep",
    "tax floored at zero",
    "liquidity held at base",
    "the trend component carries its base-period verdict",
)


@dataclass
class StressedValues:
    """Every propagated figure, so tests and drivers read one shape."""
    revenue: float
    ebitda: float
    ebit: float | None
    interest: float | None
    tax: float | None
    net_income: float | None
    cfo: float | None
    capex: float | None
    fcf: float | None
    debt: float | None
    net_debt: float | None
    etr: float


@dataclass
class StressRun:
    scenario: str
    period_end: str
    shocks: dict
    ebitda_mode: str
    fixed_cost_share: float
    floating_share: float
    new_debt_rate_used: float | None
    new_debt_rate_source: str
    new_debt_rate_reason: str
    base_score: float | None
    base_grade: int | None
    stressed_score: float | None
    stressed_grade: int | None
    results: dict = field(default_factory=dict)    # metric -> (base, stressed, change, status, reason)
    drivers: dict = field(default_factory=dict)    # (shock, metric) -> change
    assumptions: list = field(default_factory=list)


def resolve_new_debt_rate(values, shocks, stress_cfg):
    """The D53b ladder: explicit -> implied-if-in-band -> default.

    Returns (rate, source, reason). The reason is stored and printed, so a
    substitution is never silent.
    """
    if not shocks.get("additional_debt"):
        return None, NOT_NEEDED, "no additional debt in this scenario"
    explicit = stress_cfg.get("new_debt_rate")
    if explicit is not None:
        return explicit, EXPLICIT, "explicit config override"
    interest, debt = values.get("interest_expense"), values.get("total_debt")
    default = stress_cfg["new_debt_rate_default"]
    low, high = stress_cfg["new_debt_rate_band"]
    if interest is None or not debt:
        return default, SUBSTITUTED, (
            f"implied rate unavailable (interest or debt missing); "
            f"using default {default:.2%}")
    implied = interest / debt
    if low <= implied <= high:
        return implied, IMPLIED, (
            f"implied rate {implied:.2%} = interest_expense / total_debt, "
            f"inside the band [{low:.0%}, {high:.0%}]")
    return default, SUBSTITUTED, (
        f"implied rate {implied:.2%} is outside the band "
        f"[{low:.0%}, {high:.0%}]; using default {default:.2%}")


def propagate(values, shocks, *, ebitda_mode, fixed_cost_share, floating_share,
              new_debt_rate, default_tax_rate) -> StressedValues | None:
    """The methodology's propagation block, exactly as written."""
    revenue, ebitda = values.get("revenue"), values.get("ebitda")
    if revenue is None or ebitda is None or revenue <= 0:
        return None

    revenue_s = revenue * (1 + shocks["revenue_shock"])
    margin_shock = shocks["margin_shock"]
    if ebitda_mode == "constant_margin":
        ebitda_s = revenue_s * (ebitda / revenue - margin_shock)
    else:
        costs_base = revenue - ebitda
        fixed = fixed_cost_share * costs_base
        var_ratio = (1 - fixed_cost_share) * costs_base / revenue
        ebitda_s = revenue_s - fixed - var_ratio * revenue_s
        ebitda_s = ebitda_s - margin_shock * revenue_s

    dna = values.get("d_and_a")                      # held flat
    ebit_s = ebitda_s - dna if dna is not None else None

    debt, interest = values.get("total_debt"), values.get("interest_expense")
    additional = shocks["additional_debt"]
    debt_s = debt + additional if debt is not None else None
    interest_s = None
    if interest is not None and debt is not None:
        # NOTE THE CONVERSION: the shock is in basis points (D62)
        interest_s = (interest
                      + shocks["rate_shock_bps"] / 10000 * floating_share * debt
                      + (new_debt_rate or 0.0) * additional)

    pretax, tax_expense = values.get("pretax_income"), values.get("tax_expense")
    if pretax is not None and tax_expense is not None and pretax > 0:
        etr = tax_expense / pretax
    else:
        etr = default_tax_rate                        # D53d
    tax_s = (max(0.0, ebit_s - interest_s) * etr
             if (ebit_s is not None and interest_s is not None) else None)
    net_income_s = (ebit_s - interest_s - tax_s
                    if None not in (ebit_s, interest_s, tax_s) else None)

    cfo_s = (ebitda_s - interest_s - tax_s
             if None not in (interest_s, tax_s) else None)
    capex = values.get("capex")
    capex_s = capex * (1 + shocks["capex_shock"]) if capex is not None else None
    fcf_s = cfo_s - capex_s if None not in (cfo_s, capex_s) else None

    net_debt = values.get("net_debt")
    net_debt_s = net_debt + additional if net_debt is not None else None

    return StressedValues(revenue_s, ebitda_s, ebit_s, interest_s, tax_s,
                          net_income_s, cfo_s, capex_s, fcf_s, debt_s,
                          net_debt_s, etr)


def _metric(name, end, value, reason=None):
    if reason is not None:
        return MetricResult(metric=name, end=end, value=None, method=None,
                            data_status="UNAVAILABLE", reason_code=reason)
    return MetricResult(metric=name, end=end, value=value, method="stress_v1",
                        data_status="CALCULATED")


def stressed_metrics(sv: StressedValues, end: str, base_metrics=None) -> dict:
    """The seven recomputed metrics. Liquidity is absent by design (D57b).

    **A metric UNAVAILABLE at base is UNAVAILABLE under stress, carrying the
    same reason code (D75).** The stress engine must not be able to manufacture
    availability: its gates are necessarily weaker than the metric engine's —
    it works from propagated figures, not from the resolved concepts and the
    D41 coverage gates — so without this it computes values the base pipeline
    refused, and a stressed grade scores a category the base grade could not.
    """
    out = {}
    neg_ebitda = sv.ebitda <= 0
    for name, numerator in (("net_debt_to_ebitda", sv.net_debt),
                            ("debt_to_ebitda", sv.debt)):
        if numerator is None:
            continue
        out[name] = (_metric(name, end, None, "NEGATIVE_EBITDA") if neg_ebitda
                     else _metric(name, end, numerator / sv.ebitda))
    if sv.interest:
        if sv.ebit is not None:
            out["ebit_interest_cover"] = (
                _metric("ebit_interest_cover", end, None, "NEGATIVE_EARNINGS")
                if sv.ebit <= 0
                else _metric("ebit_interest_cover", end, sv.ebit / sv.interest))
        out["ebitda_interest_cover"] = (
            _metric("ebitda_interest_cover", end, None, "NEGATIVE_EBITDA")
            if neg_ebitda
            else _metric("ebitda_interest_cover", end, sv.ebitda / sv.interest))
    if sv.fcf is not None and sv.debt:
        out["fcf_to_debt"] = _metric("fcf_to_debt", end, sv.fcf / sv.debt)
    if sv.fcf is not None and sv.revenue > 0:
        out["fcf_margin"] = _metric("fcf_margin", end, sv.fcf / sv.revenue)
    if sv.revenue > 0:
        out["ebitda_margin"] = _metric("ebitda_margin", end,
                                       sv.ebitda / sv.revenue)

    # Inherit every base refusal (D75). Applied last so no branch above can
    # bypass it, and carrying the base reason code so the stressed result says
    # why rather than inventing a stress-specific explanation.
    for name, base in (base_metrics or {}).items():
        if name in out and base is not None and base.data_status == "UNAVAILABLE":
            out[name] = _metric(name, end, None, base.reason_code)
    return out


def _assumptions(mode, fcs, floating, rate, source, reason):
    """The five output duties, each recorded as a decision before this code
    existed. Emitted with every run, never left to the documentation."""
    lines = []
    if mode == "operating_leverage":
        lines.append(f"fixed_cost_share = {fcs} (ASSUMED, D53a)")
    lines.append(
        f"floating_share = {floating} (ASSUMED, D54) — the fixed/floating debt "
        f"split is unreachable from XBRL, so the whole stack is assumed to "
        f"reprice")
    lines.append(f"new_debt_rate = "
                 f"{'n/a' if rate is None else format(rate, '.2%')} "
                 f"[{source}] — {reason} (D53b)")
    lines.append(
        "liquidity is NOT stressed: the liquidity category's 20 of 100 weight "
        "is immovable, which caps how far the stressed grade can fall (D57b)")
    lines.append(
        "the trend component carries its BASE-period verdict — a trend is "
        "history, not a hypothetical (D57a)")
    lines.append(
        "the stressed GRADE covers leverage, coverage and margin only: "
        "FCF-derived metrics are reported below but excluded from it, because "
        "the CFO approximation makes them incomparable with their base values "
        "(D70)")
    lines.extend(f"simplification: {s}" for s in SIMPLIFICATIONS)
    return lines


def run_scenario(period_end, values, base_metrics, scenario, shocks,
                 trends=None, thresholds=None, stress_cfg=None,
                 fingerprint=None, base_score=None) -> StressRun | None:
    """One scenario for one period. None when the period cannot be stressed."""
    thresholds = thresholds or config.thresholds()
    stress_cfg = stress_cfg or config.stress()
    mode = stress_cfg["ebitda_mode"]
    fcs = stress_cfg["fixed_cost_share"]
    floating = stress_cfg["floating_share"]
    rate, source, reason = resolve_new_debt_rate(values, shocks, stress_cfg)

    sv = propagate(values, shocks, ebitda_mode=mode, fixed_cost_share=fcs,
                   floating_share=floating, new_debt_rate=rate,
                   default_tax_rate=stress_cfg["default_tax_rate"])
    if sv is None:
        return None

    stressed = stressed_metrics(sv, period_end, base_metrics)
    # base metrics carry through for anything stress does not touch, so the
    # stressed score uses the same category structure as the base one.
    # FCF-derived metrics are excluded from the GRADE (D70) but still reported
    # in the results table below — the figures are informative, the grade
    # contribution is not.
    merged = dict(base_metrics)
    merged.update({k: v for k, v in stressed.items() if k not in FCF_DERIVED})
    score = score_period(period_end, merged, thresholds, trends=trends)

    results = {}
    for name in STRESSED_METRICS:
        base_m = base_metrics.get(name)
        base_value = base_m.value if base_m and base_m.data_status == "CALCULATED" else None
        s = stressed.get(name)
        if s is None:
            continue
        if s.data_status == "UNAVAILABLE":
            results[name] = (base_value, None, None, "UNAVAILABLE", s.reason_code)
        else:
            change = (s.value - base_value) if base_value is not None else None
            results[name] = (base_value, s.value, change, "CALCULATED", None)
    return StressRun(
        scenario=scenario, period_end=period_end, shocks=dict(shocks),
        ebitda_mode=mode, fixed_cost_share=fcs, floating_share=floating,
        new_debt_rate_used=rate, new_debt_rate_source=source,
        new_debt_rate_reason=reason,
        base_score=base_score.total_score if base_score else None,
        base_grade=base_score.grade if base_score else None,
        stressed_score=score.total_score if score else None,
        stressed_grade=score.grade if score else None,
        results=results,
        drivers=attribute_drivers(period_end, values, base_metrics, shocks,
                                  trends, thresholds, stress_cfg),
        assumptions=_assumptions(mode, fcs, floating, rate, source, reason),
    )


def attribute_drivers(period_end, values, base_metrics, shocks, trends,
                      thresholds, stress_cfg) -> dict:
    """Each shock alone against base: the deterministic answer to "which
    assumption caused the change".

    Drivers do NOT sum to the combined run and must never be asserted to
    (D60): the propagation is multiplicative and interest reaches net income
    through a max(0, ...) floor.
    """
    zero = {s: 0 for s in SHOCKS}
    baseline = propagate(values, zero, ebitda_mode=stress_cfg["ebitda_mode"],
                         fixed_cost_share=stress_cfg["fixed_cost_share"],
                         floating_share=stress_cfg["floating_share"],
                         new_debt_rate=None,
                         default_tax_rate=stress_cfg["default_tax_rate"])
    if baseline is None:
        return {}
    base_vals = stressed_metrics(baseline, period_end, base_metrics)

    drivers = {}
    for shock in SHOCKS:
        if not shocks.get(shock):
            continue
        alone = dict(zero)
        alone[shock] = shocks[shock]
        rate, _, _ = resolve_new_debt_rate(values, alone, stress_cfg)
        sv = propagate(values, alone, ebitda_mode=stress_cfg["ebitda_mode"],
                       fixed_cost_share=stress_cfg["fixed_cost_share"],
                       floating_share=stress_cfg["floating_share"],
                       new_debt_rate=rate,
                       default_tax_rate=stress_cfg["default_tax_rate"])
        for name, m in stressed_metrics(sv, period_end,
                                        base_metrics).items():
            b = base_vals.get(name)
            if (m.data_status == "CALCULATED" and b is not None
                    and b.data_status == "CALCULATED"):
                drivers[(shock, name)] = m.value - b.value
    return drivers


def sensitivity_grid(period_end, values, base_metrics, trends=None,
                     thresholds=None, stress_cfg=None) -> list:
    """revenue_shock x margin_shock, reporting net_debt_to_ebitda and grade.

    Computed on demand, never stored (D61b): a pure function of inputs already
    stored, and storing it would need invalidating on every config move.
    """
    thresholds = thresholds or config.thresholds()
    stress_cfg = stress_cfg or config.stress()
    grid = stress_cfg["sensitivity_grid"]
    cells = []
    for revenue_shock in grid["revenue_shock"]:
        for margin_shock in grid["margin_shock"]:
            shocks = {"revenue_shock": revenue_shock,
                      "margin_shock": margin_shock, "rate_shock_bps": 0,
                      "additional_debt": 0, "capex_shock": 0.0}
            sv = propagate(values, shocks,
                           ebitda_mode=stress_cfg["ebitda_mode"],
                           fixed_cost_share=stress_cfg["fixed_cost_share"],
                           floating_share=stress_cfg["floating_share"],
                           new_debt_rate=None,
                           default_tax_rate=stress_cfg["default_tax_rate"])
            if sv is None:
                continue
            merged = dict(base_metrics)
            merged.update(stressed_metrics(sv, period_end, base_metrics))
            score = score_period(period_end, merged, thresholds, trends=trends)
            leverage = merged.get("net_debt_to_ebitda")
            cells.append({
                "revenue_shock": revenue_shock, "margin_shock": margin_shock,
                "net_debt_to_ebitda": (leverage.value if leverage
                                       and leverage.data_status == "CALCULATED"
                                       else None),
                "grade": score.grade if score else None,
            })
    return cells


def stress_company(mapping, composites, metrics_report, scores,
                   thresholds=None, stress_cfg=None, trend_report=None,
                   fingerprint=None) -> list:
    """Every preset scenario for every stressable period."""
    thresholds = thresholds or config.thresholds()
    stress_cfg = stress_cfg or config.stress()

    series = {}
    for c in mapping.concepts:
        series.setdefault(c.end, {})[c.concept] = c.value
    for c in composites:
        if c.data_status == "CALCULATED":
            series.setdefault(c.end, {})[c.concept] = c.value

    base_by_period = {}
    for m in metrics_report.metrics:
        base_by_period.setdefault(m.end, {})[m.metric] = m
    scores_by_period = {s.period_end: s for s in scores}
    trends_by_period = {}
    if trend_report is not None:
        for t in trend_report.trends:
            trends_by_period.setdefault(t.period_end, {})[t.metric] = t.verdict

    runs = []
    for period_end in sorted(series):
        if period_end not in scores_by_period:
            continue           # no base score: integrity FAIL or unscoreable
        for scenario, shocks in stress_cfg["presets"].items():
            run = run_scenario(
                period_end, series[period_end],
                base_by_period.get(period_end, {}), scenario, shocks,
                trends=trends_by_period.get(period_end),
                thresholds=thresholds, stress_cfg=stress_cfg,
                fingerprint=fingerprint,
                base_score=scores_by_period[period_end])
            if run is not None:
                runs.append(run)
    return runs
