"""Composite concepts (Task 9, docs/credit-methodology.md "Composite concepts").

Consumes MappingResult and produces CALCULATED concept records — total_debt,
total_debt_ex_leases, net_debt, ebitda, fcf, and gross_profit's calculated
fallback — plus UNAVAILABLE records where the methodology refuses to compute.

The four total_debt branches are mutually exclusive by construction: one
if/elif chain per period, first match wins, and a refusal is a terminal
outcome of its branch, never a fall-through to the next (D26, D27, D32, D33).
Composition toggles and the reconciliation tolerance come only from
config/composites.yaml — exactly the keys the D18 fingerprint covers.
"""

from dataclasses import dataclass, field

from credit_risk.normalise.mapping import MappingResult
from credit_risk.store.fingerprint import composite_config_values

# method strings recorded on total_debt rows (methodology: "the method is
# always recorded")
DEBT_FROM_COMPONENTS = "debt_from_components"
DEBT_FROM_AGGREGATE = "debt_from_aggregate"
DEBT_FROM_LEASE_INCLUSIVE_LTD = "debt_from_lease_inclusive_ltd"

# D78: a component must never be added to a figure that may already contain it.
# D32 established this for DebtCurrent vs current_ltd; these are the same
# mechanism in the other two branches, found by the golden set rather than by
# an audit.
LEASE_CONTAINMENT_UNVERIFIABLE = "LEASE_CONTAINMENT_UNVERIFIABLE"


@dataclass
class CompositeConcept:
    concept: str
    end: str
    value: float | None
    method: str | None
    data_status: str                      # CALCULATED | UNAVAILABLE
    reason_code: str | None = None
    detail: str | None = None             # zero-by-absence notes; both figures on refusals
    inputs: list[tuple[str, str]] = field(default_factory=list)  # (concept, end)
    unit: str = "USD"
    fy: int | None = None
    fp: str | None = None
    label: str | None = None


def _calculated(concept, end, value, method, inputs, per, detail=None):
    fy, fp = _period_meta(per, inputs)
    return CompositeConcept(concept=concept, end=end, value=value, method=method,
                            data_status="CALCULATED", detail=detail,
                            inputs=inputs, fy=fy, fp=fp)


def _unavailable(concept, end, reason_code, detail=None, method=None):
    return CompositeConcept(concept=concept, end=end, value=None, method=method,
                            data_status="UNAVAILABLE", reason_code=reason_code,
                            detail=detail)


def _period_meta(per, inputs):
    for name, end in inputs:
        c = per.get(name)
        if c is not None:
            return c.fy, c.fp
    return None, None


def _deviation(components: float, aggregate: float) -> float:
    """Relative deviation between the summed components and the reported
    aggregate, compared against component_aggregate_tolerance.

    The caller treats `deviation <= tolerance` as agreement. D26's measured
    percentages (CCL 2010: |8,624 - 9,364| / 9,364 = 7.9%) fix the ordinary
    case: absolute difference relative to the aggregate. The edge cases are a
    genuine design decision, not arithmetic:

    Edge semantics (owner decision, D34) — the test applied to each: could it
    produce a plausible-looking wrong number (forbidden), or only an
    unnecessary refusal (acceptable)?

    - both zero -> 0.0: the sources agree ("no long-term debt"); that
      agreement is detectable directly even though 0/0 has no value.
    - aggregate zero, components non-zero -> inf: a contradiction no
      percentage can express; proceeding would pick a side with no basis.
    - either value negative -> inf: debt cannot be negative; a deviation
      computed from a tagging error would launder bad input into a
      plausible number.

    Signs are checked BEFORE any abs(); abs() applies only to the
    difference. abs() on the inputs would turn components=-8,624 against
    aggregate=8,624 into 0.0 — perfect agreement from contradictory data.
    """
    if components < 0 or aggregate < 0:
        return float("inf")
    if aggregate == 0:
        return 0.0 if components == 0 else float("inf")
    return abs(components - aggregate) / aggregate


def compute_composites(mapping: MappingResult, cfg: dict | None = None) -> list[CompositeConcept]:
    """All composite concepts for every period the mapping knows about."""
    if cfg is None:
        cfg = composite_config_values()
    include_leases = cfg["include_operating_leases"]
    include_sti = cfg["include_st_investments"]
    tolerance = cfg["component_aggregate_tolerance"]

    by_concept: dict[str, dict[str, object]] = {}
    for c in mapping.concepts:
        by_concept.setdefault(c.concept, {})[c.end] = c
    periods = sorted(
        {c.end for c in mapping.concepts}
        | {u.period_end for u in mapping.unavailable}
    )

    out: list[CompositeConcept] = []
    for end in periods:
        per = {name: ends.get(end) for name, ends in by_concept.items()}
        per = {k: v for k, v in per.items() if v is not None}
        total_debt, ex_leases = _total_debt(per, end, include_leases, tolerance)
        out.append(total_debt)
        out.append(ex_leases)
        out.append(_net_debt(per, end, total_debt, include_sti))
        out.append(_ebitda(per, end))
        out.append(_fcf(per, end))
        gp = _gross_profit_fallback(per, end)
        if gp is not None:
            out.append(gp)
    return out


def _pair_sum(per, current_name, noncurrent_name):
    """Sum a current/noncurrent split, missing halves as zero (D33).

    Returns (value, inputs, zeroed) or (None, [], []) when neither half
    resolves — absence of the whole component, which each caller treats per
    its own zero-by-absence rule.
    """
    cur = per.get(current_name)
    non = per.get(noncurrent_name)
    if cur is None and non is None:
        return None, [], []
    value, inputs, zeroed = 0.0, [], []
    for name, c in ((current_name, cur), (noncurrent_name, non)):
        if c is None:
            zeroed.append(name)
        else:
            value += c.value
            inputs.append((name, c.end))
    return value, inputs, zeroed


def _lease_containment(per, base, fin, tolerance=0.02):
    """Does `base` already contain the finance-lease liabilities (D78b)?

    Cross-check only, never a value source (D27(4)). `ltd_incl_leases_aggregate`
    is debt INCLUDING leases, so if it sits at `base` the leases are already in
    `base`; if it sits at `base + fin` they are separate. Returns None when no
    cross-check is available — the caller must then refuse rather than guess.
    """
    agg2 = per.get("ltd_incl_leases_aggregate")
    if agg2 is None or not base:
        return None
    return _deviation(base, agg2.value) < _deviation(base + fin, agg2.value)


def _total_debt(per, end, include_leases, tolerance):
    """One period's total_debt and total_debt_ex_leases (methodology branches)."""
    current = per.get("current_ltd")
    noncurrent = per.get("noncurrent_ltd")
    aggregate = per.get("total_ltd_aggregate")
    std = per.get("short_term_debt")

    plain_resolves = current is not None or noncurrent is not None or aggregate is not None

    if plain_resolves:
        # DebtCurrent guard (D32): its scope is filer-dependent, so its overlap
        # with current_ltd cannot be verified. Checked before assembly — a
        # refused period must not fall through to another branch.
        if std is not None and std.source_tag == "DebtCurrent" and current is not None:
            detail = (f"short_term_debt via DebtCurrent={std.value} may already "
                      f"contain current_ltd={current.value}; overlap unverifiable")
            return (_unavailable("total_debt", end, "ST_DEBT_SCOPE_UNCERTAIN", detail),
                    _unavailable("total_debt_ex_leases", end,
                                 "ST_DEBT_SCOPE_UNCERTAIN", detail))

        if current is not None or noncurrent is not None:
            ltd, ltd_inputs, ltd_zeroed = _pair_sum(per, "current_ltd", "noncurrent_ltd")
            if aggregate is not None:
                # D26: reconcile BEFORE using either. Missing pair member is
                # zero for this comparison — that is the point of the check.
                dev = _deviation(ltd, aggregate.value)
                if dev > tolerance:
                    detail = (f"components current_ltd+noncurrent_ltd={ltd} vs "
                              f"total_ltd_aggregate={aggregate.value} "
                              f"deviates {dev:.1%} > {tolerance:.0%}")
                    return (_unavailable("total_debt", end,
                                         "COMPONENT_AGGREGATE_MISMATCH", detail),
                            _unavailable("total_debt_ex_leases", end,
                                         "COMPONENT_AGGREGATE_MISMATCH", detail))
            method = DEBT_FROM_COMPONENTS
        else:
            # aggregate only: it substitutes for the pair in the same formula
            ltd, ltd_inputs, ltd_zeroed = aggregate.value, [("total_ltd_aggregate", end)], []
            method = DEBT_FROM_AGGREGATE

        # optional components, zero-by-absence (recorded)
        zeroed = list(ltd_zeroed)
        value, inputs = ltd, list(ltd_inputs)
        if std is not None:
            value += std.value
            inputs.append(("short_term_debt", end))
        else:
            zeroed.append("short_term_debt")
        fin, fin_inputs, fin_zeroed = _pair_sum(
            per, "finance_lease_liab_current", "finance_lease_liab_noncurrent")
        if fin is not None and method == DEBT_FROM_AGGREGATE:
            # D78(b). `LongTermDebt` is filer-dependent on whether it already
            # contains finance leases: measured across the adopted 43, where a
            # cross-check exists it says "already contained" 6 times and
            # "separate" 7 — a coin flip, so it cannot be assumed either way.
            # The component pair tags (LongTermDebtCurrent/Noncurrent) do NOT
            # have this problem: 1 anomaly in 81, so only this branch is guarded.
            contained = _lease_containment(per, aggregate.value, fin)
            if contained is None:
                detail = (f"total_ltd_aggregate={aggregate.value} may already "
                          f"contain finance_lease_liab={fin}; no "
                          f"ltd_incl_leases_aggregate to reconcile against")
                return (_unavailable("total_debt", end,
                                     LEASE_CONTAINMENT_UNVERIFIABLE, detail),
                        _unavailable("total_debt_ex_leases", end,
                                     LEASE_CONTAINMENT_UNVERIFIABLE, detail))
            if contained:
                fin = None          # already inside the aggregate; do not add
                zeroed.append("finance_lease_liab[already in aggregate]")
        if fin is None:
            if not any(z.startswith("finance_lease_liab") for z in zeroed):
                zeroed.append("finance_lease_liab")
        else:
            value += fin
            inputs += fin_inputs
            zeroed += fin_zeroed
        ex_value, ex_inputs = value, list(inputs)  # before operating leases
        if include_leases:
            op, op_inputs, op_zeroed = _pair_sum(
                per, "operating_lease_liab_current", "operating_lease_liab_noncurrent")
            if op is None:
                zeroed.append("operating_lease_liab")
            else:
                value += op
                inputs += op_inputs
                zeroed += op_zeroed
        detail = f"zero_by_absence: {', '.join(zeroed)}" if zeroed else None

        # total_debt_ex_leases excludes BOTH lease kinds (D33):
        # short_term_debt + current_ltd + noncurrent_ltd only.
        if method == DEBT_FROM_COMPONENTS:
            ex_v = ltd + (std.value if std is not None else 0.0)
            ex_in = list(ltd_inputs) + ([("short_term_debt", end)] if std is not None else [])
            ex_row = _calculated("total_debt_ex_leases", end, ex_v, method, ex_in, per,
                                 detail=detail)
        else:
            # the aggregate is LTD only, so ex-leases is aggregate + STD
            ex_v = aggregate.value + (std.value if std is not None else 0.0)
            ex_in = [("total_ltd_aggregate", end)] + (
                [("short_term_debt", end)] if std is not None else [])
            ex_row = _calculated("total_debt_ex_leases", end, ex_v, method, ex_in, per,
                                 detail=detail)
        return (_calculated("total_debt", end, value, method, inputs, per,
                            detail=detail), ex_row)

    # lease-inclusive branch (D27): BOTH pair members must resolve (D33)
    li_cur = per.get("ltd_incl_leases_current")
    li_non = per.get("ltd_incl_leases_noncurrent")
    if li_cur is not None and li_non is not None:
        pair = li_cur.value + li_non.value
        li_agg = per.get("ltd_incl_leases_aggregate")
        if li_agg is not None:
            # D27(4): cross-check only, never a value source
            dev = _deviation(pair, li_agg.value)
            if dev > tolerance:
                detail = (f"ltd_incl_leases pair={pair} vs "
                          f"ltd_incl_leases_aggregate={li_agg.value} "
                          f"deviates {dev:.1%} > {tolerance:.0%}")
                return (_unavailable("total_debt", end,
                                     "COMPONENT_AGGREGATE_MISMATCH", detail),
                        _unavailable("total_debt_ex_leases", end,
                                     "COMPONENT_AGGREGATE_MISMATCH", detail))
        # D78(a). `ltd_incl_leases_current` IS a current-maturities figure, so
        # adding short_term_debt to it can count the same debt twice — YUM's
        # Note 11 shows its "Short-term borrowings 53" IS the 56 of current
        # maturities net of issuance costs, and 13 periods (MPC x7, RCL x4,
        # WBD x2) carry the two as IDENTICAL values.
        #
        # Three tests, most reliable first. Refusing whenever the overlap is
        # merely *possible* was tried and over-refuses badly: KHC carries
        # short_term_debt at 0.6% of its current maturities, and one period at
        # zero, none of which can double-count anything.
        if std is not None and std.value != 0:
            contained = _lease_containment(per, pair, std.value)
            if contained is True:
                std = None                      # verifiably already inside
            elif contained is None and _deviation(std.value, li_cur.value) <= tolerance:
                # No aggregate to reconcile against, and the two agree closely
                # enough to be the same figure. There is no measured threshold
                # available here — the deviation runs continuously from 0% to
                # 100% across 95 periods with no bimodal gap, unlike D69 — so
                # this reuses the existing component/aggregate tolerance rather
                # than inventing a second constant (D36's precedent).
                detail = (f"short_term_debt={std.value} agrees with "
                          f"ltd_incl_leases_current={li_cur.value} within "
                          f"{tolerance:.0%} and no ltd_incl_leases_aggregate "
                          f"reconciles them; the same current maturities "
                          f"tagged twice, overlap unverifiable")
                return (_unavailable("total_debt", end,
                                     "ST_DEBT_SCOPE_UNCERTAIN", detail),
                        _unavailable("total_debt_ex_leases", end,
                                     "ST_DEBT_SCOPE_UNCERTAIN", detail))
        inputs = [("ltd_incl_leases_current", end), ("ltd_incl_leases_noncurrent", end)]
        value, zeroed = pair, []
        if std is not None:
            value += std.value
            inputs.append(("short_term_debt", end))
        else:
            zeroed.append("short_term_debt")
        detail = f"zero_by_absence: {', '.join(zeroed)}" if zeroed else None
        return (_calculated("total_debt", end, value,
                            DEBT_FROM_LEASE_INCLUSIVE_LTD, inputs, per, detail=detail),
                _unavailable("total_debt_ex_leases", end, "LEASES_NOT_SEPARABLE",
                             method=DEBT_FROM_LEASE_INCLUSIVE_LTD))

    # nothing LTD-shaped resolves — never assume zero debt. A half-resolved
    # lease-inclusive pair deliberately lands here too (D33).
    return (_unavailable("total_debt", end, "NO_DEBT_DATA"),
            _unavailable("total_debt_ex_leases", end, "NO_DEBT_DATA"))


def _net_debt(per, end, total_debt: CompositeConcept, include_sti):
    if total_debt.data_status == "UNAVAILABLE":
        return _unavailable("net_debt", end, "MISSING_INPUT:total_debt")
    cash = per.get("cash")
    if cash is None:
        return _unavailable("net_debt", end, "MISSING_INPUT:cash")
    value = total_debt.value - cash.value
    inputs = [("total_debt", end), ("cash", end)]
    detail = None
    if include_sti:
        sti = per.get("short_term_investments")
        if sti is not None:
            value -= sti.value
            inputs.append(("short_term_investments", end))
        else:
            # zero-by-absence (D33): STI is a refinement, cash is the substance
            detail = "zero_by_absence: short_term_investments"
    return _calculated("net_debt", end, value, "total_debt - cash - short_term_investments",
                       inputs, per, detail=detail)


def _ebitda(per, end):
    ebit = per.get("ebit")
    dna = per.get("d_and_a")
    if ebit is None:
        return _unavailable("ebitda", end, "MISSING_INPUT:ebit")
    if dna is None:
        # never fall back to EBIT
        return _unavailable("ebitda", end, "MISSING_INPUT:d_and_a")
    row = _calculated("ebitda", end, ebit.value + dna.value, "ebit + d_and_a",
                      [("ebit", end), ("d_and_a", end)], per)
    row.label = "EBITDA (EBIT + D&A)"   # methodology: labelled everywhere; no "adjusted"
    return row


def _fcf(per, end):
    cfo = per.get("cfo")
    capex = per.get("capex")
    if cfo is None:
        return _unavailable("fcf", end, "MISSING_INPUT:cfo")
    if capex is None:
        return _unavailable("fcf", end, "MISSING_INPUT:capex")
    return _calculated("fcf", end, cfo.value - capex.value, "cfo - capex",
                       [("cfo", end), ("capex", end)], per)


def _gross_profit_fallback(per, end):
    """revenue - cost_of_revenue, only where the GrossProfit tag did not resolve.

    Returns None when the tag resolved (mapping's REPORTED row stands) or when
    an input is missing (mapping's NO_CANDIDATE_TAG row stands — a calculated
    UNAVAILABLE would say less than the existing one).
    """
    if "gross_profit" in per:
        return None
    revenue = per.get("revenue")
    cost = per.get("cost_of_revenue")
    if revenue is None or cost is None:
        return None
    return _calculated("gross_profit", end, revenue.value - cost.value,
                       "revenue - cost_of_revenue",
                       [("revenue", end), ("cost_of_revenue", end)], per)
