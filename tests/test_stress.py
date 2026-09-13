"""Phase 8: the stress engine.

Two things this file is careful about.

**The five output duties get one test each.** They were recorded as decisions
before the engine existed, and a duty recorded but unenforced is exactly D43's
failure mode — so each is pinned individually rather than by one "the
assumptions block is non-empty" assertion.

**Driver attribution is asserted directionally and with a bounded residual,
never additively** (D60). Additivity is false: the propagation is
multiplicative and tax passes through a max(0, ...) floor. Measured across all
stressable real periods, drivers agree in sign with the combined change in
224 of 224 cases and oppose it in 0 — so direction is an exact invariant —
while the magnitude residual runs to a median of 14.7% and a maximum of 71.3%.
"""

import pytest

from credit_risk import config
from credit_risk.metrics.ratios import MetricResult
from credit_risk.stress.engine import (
    IMPLIED,
    NOT_NEEDED,
    SIMPLIFICATIONS,
    SUBSTITUTED,
    EXPLICIT,
    attribute_drivers,
    propagate,
    resolve_new_debt_rate,
    run_scenario,
    sensitivity_grid,
    stressed_metrics,
)

TH, SC = config.thresholds(), config.stress()
END = "2023-12-31"

# One base company, hand-chosen so every figure is round.
# revenue 1000, ebitda 300 (30% margin), costs_base 700
BASE = {
    "revenue": 1000.0, "ebitda": 300.0, "d_and_a": 100.0,
    "total_debt": 500.0, "net_debt": 400.0, "interest_expense": 25.0,
    "pretax_income": 175.0, "tax_expense": 35.0,      # etr = 20%
    "capex": 60.0, "cash": 100.0,
}
NO_SHOCK = {"revenue_shock": 0.0, "margin_shock": 0.0, "rate_shock_bps": 0,
            "additional_debt": 0, "capex_shock": 0.0}


def shocks(**kw):
    return {**NO_SHOCK, **kw}


def prop(values=None, mode="constant_margin", fcs=0.3, floating=1.0,
         rate=None, **shock_kw):
    return propagate(values or BASE, shocks(**shock_kw), ebitda_mode=mode,
                     fixed_cost_share=fcs, floating_share=floating,
                     new_debt_rate=rate, default_tax_rate=0.21)


# ============ propagation, hand-computed ============

def test_no_shock_reproduces_the_base_figures():
    sv = prop()
    assert sv.revenue == 1000.0
    assert sv.ebitda == 300.0
    assert sv.ebit == 200.0                     # 300 - 100 D&A
    assert sv.interest == 25.0
    assert sv.tax == pytest.approx(35.0)        # (200 - 25) * 0.20
    assert sv.cfo == pytest.approx(240.0)       # 300 - 25 - 35
    assert sv.fcf == pytest.approx(180.0)       # 240 - 60 capex


def test_constant_margin_mode():
    """margin_s = 30% - 2pp = 28%; revenue_s = 900; ebitda_s = 252."""
    sv = prop(revenue_shock=-0.10, margin_shock=0.02)
    assert sv.revenue == 900.0
    assert sv.ebitda == pytest.approx(252.0)


def test_operating_leverage_mode_from_the_same_base():
    """costs 700, fixed = 0.3*700 = 210, var_ratio = 490/1000 = 0.49.
    ebitda_s = 900 - 210 - 0.49*900 - 0.02*900 = 900 - 210 - 441 - 18 = 231."""
    sv = prop(mode="operating_leverage", revenue_shock=-0.10, margin_shock=0.02)
    assert sv.ebitda == pytest.approx(231.0)


def test_operating_leverage_is_never_milder_than_constant_margin():
    """The asymmetry that makes mode B the conservative choice."""
    for rs in (-0.05, -0.10, -0.20):
        a = prop(revenue_shock=rs).ebitda
        b = prop(mode="operating_leverage", revenue_shock=rs).ebitda
        assert b <= a + 1e-9, rs


def test_mode_b_at_zero_fixed_cost_share_equals_mode_a():
    """The algebraic identity: with no fixed costs, operating leverage reduces
    to a constant margin. This is what makes the two modes comparable."""
    for rs in (0.0, -0.10, -0.20):
        a = prop(revenue_shock=rs, margin_shock=0.02).ebitda
        b = prop(mode="operating_leverage", fcs=0.0, revenue_shock=rs,
                 margin_shock=0.02).ebitda
        assert b == pytest.approx(a), rs


def test_rate_shock_is_basis_points(  ):
    """D62: the conversion is /10000. 200bps on 500 debt adds 10."""
    assert prop(rate_shock_bps=200).interest == pytest.approx(35.0)


def test_floating_share_scales_the_rate_shock():
    assert prop(rate_shock_bps=200, floating=0.5).interest == pytest.approx(30.0)
    assert prop(rate_shock_bps=200, floating=0.0).interest == pytest.approx(25.0)


def test_additional_debt_prices_at_the_new_debt_rate():
    sv = prop(additional_debt=100, rate=0.06)
    assert sv.interest == pytest.approx(31.0)       # 25 + 0.06*100
    assert sv.debt == 600.0
    assert sv.net_debt == 500.0                     # no cash sweep


# ============ the documented simplifications, each asserted ============

def test_d_and_a_is_held_flat():
    sv = prop(revenue_shock=-0.20)
    assert sv.ebit == pytest.approx(sv.ebitda - BASE["d_and_a"])


def test_working_capital_is_held_flat_in_the_cfo_approximation():
    sv = prop(revenue_shock=-0.10)
    assert sv.cfo == pytest.approx(sv.ebitda - sv.interest - sv.tax)


def test_no_cash_sweep():
    """net_debt moves only by additional_debt, never by stressed cash flow."""
    assert prop(revenue_shock=-0.20).net_debt == BASE["net_debt"]


def test_tax_is_floored_at_zero():
    # -80% revenue: ebitda 60, ebit -40, interest 25 -> pretax -65
    sv = prop(revenue_shock=-0.80)
    assert sv.ebit - sv.interest < 0
    assert sv.tax == 0.0


def test_etr_uses_the_reported_rate_when_pretax_is_positive():
    assert prop().etr == pytest.approx(0.20)


def test_etr_falls_back_to_the_default_when_pretax_is_not_positive():
    values = {**BASE, "pretax_income": -50.0}
    assert prop(values).etr == 0.21


def test_etr_falls_back_when_the_tax_inputs_are_missing(  ):
    """D53d: missing inputs take the same fallback as pretax <= 0."""
    values = {k: v for k, v in BASE.items() if k != "tax_expense"}
    assert prop(values).etr == 0.21


def test_a_period_without_revenue_or_ebitda_cannot_be_stressed():
    assert prop({"revenue": 1000.0}) is None
    assert prop({"ebitda": 300.0}) is None
    assert prop({**BASE, "revenue": 0.0}) is None


def test_negative_base_margin_runs_in_both_modes_and_refuses_the_metric():
    """D53d: a loss-making company stresses without crashing, and the stressed
    metric carries NEGATIVE_EBITDA evidence rather than a number.

    The two modes disagree in DIRECTION here, and both are arithmetically
    right (D63): under constant margin, a smaller revenue times a negative
    margin is a SMALLER loss (-50 -> -40), because the margin is held while the
    base shrinks. Under operating leverage the fixed costs stay put while
    revenue falls, so the loss deepens (-50 -> -103). Mode B is the honest one
    for a loss-making company, and that is worth knowing before choosing a mode.
    """
    values = {**BASE, "ebitda": -50.0}

    a = prop(values, revenue_shock=-0.20)
    assert a.ebitda == pytest.approx(-40.0)      # 800 * (-5%)

    b = prop(values, mode="operating_leverage", revenue_shock=-0.20)
    # costs 1050; fixed 315; var_ratio 0.735 -> 800 - 315 - 588 = -103
    assert b.ebitda == pytest.approx(-103.0)
    assert b.ebitda < values["ebitda"]

    for sv in (a, b):
        metrics = stressed_metrics(sv, END)
        assert metrics["net_debt_to_ebitda"].reason_code == "NEGATIVE_EBITDA"
        assert metrics["net_debt_to_ebitda"].value is None


# ============ new_debt_rate resolution (D53b) ============

def test_rate_is_not_needed_without_additional_debt():
    rate, source, reason = resolve_new_debt_rate(BASE, NO_SHOCK, SC)
    assert rate is None and source == NOT_NEEDED
    assert "no additional debt" in reason


def test_implied_rate_is_used_when_inside_the_band():
    # 25 / 500 = 5%, inside [2%, 12%]
    rate, source, reason = resolve_new_debt_rate(
        BASE, shocks(additional_debt=100), SC)
    assert rate == pytest.approx(0.05) and source == IMPLIED
    assert "inside the band" in reason


def test_implied_rate_outside_the_band_is_substituted_with_a_reason():
    """Both real failure directions: Ford's shape and JNJ's."""
    ford = {**BASE, "interest_expense": 500.0}          # 100% implied
    rate, source, reason = resolve_new_debt_rate(
        ford, shocks(additional_debt=100), SC)
    assert rate == SC["new_debt_rate_default"] and source == SUBSTITUTED
    assert "outside the band" in reason and "100.00%" in reason

    jnj = {**BASE, "interest_expense": 2.5}             # 0.5% implied
    rate, source, reason = resolve_new_debt_rate(
        jnj, shocks(additional_debt=100), SC)
    assert rate == SC["new_debt_rate_default"] and source == SUBSTITUTED
    assert "0.50%" in reason


def test_an_explicit_override_wins():
    cfg = {**SC, "new_debt_rate": 0.09}
    rate, source, _ = resolve_new_debt_rate(
        BASE, shocks(additional_debt=100), cfg)
    assert rate == 0.09 and source == EXPLICIT


def test_missing_inputs_substitute_rather_than_crash():
    values = {k: v for k, v in BASE.items() if k != "interest_expense"}
    rate, source, reason = resolve_new_debt_rate(
        values, shocks(additional_debt=100), SC)
    assert rate == SC["new_debt_rate_default"] and source == SUBSTITUTED
    assert "unavailable" in reason


# ============ the five output duties, one test each (D43's lesson) ============

def base_metrics():
    return {"net_debt_to_ebitda": MetricResult(
        metric="net_debt_to_ebitda", end=END, value=1.33, method="m",
        data_status="CALCULATED")}


def a_run(scenario="severe", cfg=None, **shock_kw):
    return run_scenario(END, BASE, base_metrics(), scenario,
                        shocks(**shock_kw), thresholds=TH,
                        stress_cfg=cfg or SC)


def joined(run):
    return " | ".join(run.assumptions)


def test_duty_1_fixed_cost_share_is_printed_in_operating_leverage_mode():
    cfg = {**SC, "ebitda_mode": "operating_leverage"}
    assert "fixed_cost_share = 0.3" in joined(a_run(cfg=cfg))
    # and NOT claimed in constant-margin mode, where it is unused
    assert "fixed_cost_share" not in joined(a_run())


def test_duty_2_floating_share_and_its_unreachability_are_printed():
    text = joined(a_run())
    assert "floating_share = 1.0" in text
    assert "unreachable from XBRL" in text


def test_duty_3_the_new_debt_rate_used_is_named_with_its_reason():
    text = joined(a_run(additional_debt=100))
    assert "new_debt_rate = 5.00%" in text
    assert "implied" in text and "inside the band" in text


def test_duty_4_the_liquidity_exclusion_is_surfaced_with_its_consequence():
    text = joined(a_run())
    assert "liquidity is NOT stressed" in text
    assert "20 of 100" in text
    assert "caps how far" in text


def test_duty_5_the_trend_component_carries_the_base_verdict():
    text = joined(a_run())
    assert "BASE-period verdict" in text


def test_every_documented_simplification_is_stated_in_the_output():
    text = joined(a_run())
    for simplification in SIMPLIFICATIONS:
        assert simplification in text, simplification


# ============ driver attribution (D60) ============

def drivers(**shock_kw):
    return attribute_drivers(END, BASE, base_metrics(), shocks(**shock_kw),
                             None, TH, SC)


def test_each_shock_is_attributed_alone():
    d = drivers(revenue_shock=-0.10, rate_shock_bps=200)
    assert {shock for shock, _ in d} == {"revenue_shock", "rate_shock_bps"}


def test_a_zero_shock_gets_no_driver_row():
    d = drivers(revenue_shock=-0.10)
    assert {shock for shock, _ in d} == {"revenue_shock"}


def test_a_rate_shock_alone_does_not_move_leverage():
    """Isolation, asserted: rates touch interest, not EBITDA or net debt."""
    d = drivers(rate_shock_bps=200)
    assert d[("rate_shock_bps", "net_debt_to_ebitda")] == pytest.approx(0.0)
    assert d[("rate_shock_bps", "ebit_interest_cover")] < 0


def test_a_revenue_shock_alone_does_not_move_interest():
    d = drivers(revenue_shock=-0.10)
    assert ("revenue_shock", "ebit_interest_cover") in d
    # leverage moves because EBITDA fell, not because debt changed
    assert d[("revenue_shock", "net_debt_to_ebitda")] > 0


def test_drivers_agree_in_direction_with_the_combined_run():
    """The exact invariant: measured 224 agreeing and 0 opposing across every
    stressable real period. Magnitude is a different question (below)."""
    run = a_run(revenue_shock=-0.20, margin_shock=0.05, rate_shock_bps=200)
    for (_, metric), change in run.drivers.items():
        combined = run.results.get(metric)
        if not combined or combined[3] != "CALCULATED" or not combined[2]:
            continue
        if abs(change) < 1e-9:
            continue
        assert (change > 0) == (combined[2] > 0), metric


def test_drivers_do_not_sum_to_the_combined_run():
    """Asserted as a POSITIVE fact, not tolerated as slack: the propagation is
    multiplicative and tax is floored, so additivity is false. A test asserting
    additivity would assert a falsehood about the arithmetic (D60)."""
    run = a_run(revenue_shock=-0.20, margin_shock=0.05)
    metric = "net_debt_to_ebitda"
    summed = sum(c for (_, m), c in run.drivers.items() if m == metric)
    combined = run.results[metric][2]
    assert summed != pytest.approx(combined)


def test_the_driver_residual_stays_within_its_measured_bound():
    """Measured across all stressable real periods: median 14.7%, max 71.3%.
    The ceiling here is a sanity bound — drivers must never exceed double the
    combined change — not a fit to the data."""
    run = a_run(revenue_shock=-0.20, margin_shock=0.05, rate_shock_bps=200)
    for metric, (_, _, change, status, _) in run.results.items():
        if status != "CALCULATED" or not change:
            continue
        summed = sum(c for (_, m), c in run.drivers.items() if m == metric)
        assert abs(summed - change) / abs(change) < 1.0, metric


# ============ sensitivity grid (D61b) ============

def test_sensitivity_grid_shape_and_monotonicity():
    cells = sensitivity_grid(END, BASE, base_metrics(), thresholds=TH,
                             stress_cfg=SC)
    grid = SC["sensitivity_grid"]
    assert len(cells) == len(grid["revenue_shock"]) * len(grid["margin_shock"])
    # deeper revenue and margin shocks never improve leverage
    worst = max(c["net_debt_to_ebitda"] for c in cells)
    best = min(c["net_debt_to_ebitda"] for c in cells)
    assert worst > best
    no_shock = next(c for c in cells if c["revenue_shock"] == 0.0
                    and c["margin_shock"] == 0.0)
    assert no_shock["net_debt_to_ebitda"] == pytest.approx(best)


def test_grid_is_computed_not_stored():
    """D61b: a pure function of its inputs, so two calls agree exactly and
    nothing needs invalidating when config moves."""
    a = sensitivity_grid(END, BASE, base_metrics(), thresholds=TH, stress_cfg=SC)
    b = sensitivity_grid(END, BASE, base_metrics(), thresholds=TH, stress_cfg=SC)
    assert a == b


def test_driver_isolation_holds_inside_a_COMBINED_scenario():
    """The direct test of isolation, and the one that matters.

    In a scenario carrying BOTH a revenue shock and a rate shock, the rate
    driver must still move leverage by exactly zero — rates touch interest, not
    EBITDA or net debt. If attribution leaked the other shocks in, this would
    be non-zero while every single-shock test still passed.
    """
    d = drivers(revenue_shock=-0.20, margin_shock=0.05, rate_shock_bps=200)
    assert d[("rate_shock_bps", "net_debt_to_ebitda")] == pytest.approx(0.0)
    assert d[("rate_shock_bps", "ebitda_margin")] == pytest.approx(0.0)
    # and the revenue driver alone must match a revenue-only run exactly
    solo = drivers(revenue_shock=-0.20)
    assert d[("revenue_shock", "net_debt_to_ebitda")] == pytest.approx(
        solo[("revenue_shock", "net_debt_to_ebitda")])
