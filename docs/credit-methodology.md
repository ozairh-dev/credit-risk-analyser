# Credit methodology

Every formula, edge case and threshold the engine uses. If it isn't written here, the
engine shouldn't be doing it. Numbers in `config/thresholds.yaml` and `config/stress.yaml`
are **project assumptions** — see "Calibration" at the end.

## General rules for every calculation

- Inputs must be from the **same fiscal period** and the **same filing**, unless the
  formula is explicitly a period-over-period comparison.
- Any input `UNAVAILABLE` → output `UNAVAILABLE`, `reason_code = MISSING_INPUT:<concept>`.
- Denominator `== 0` → `UNAVAILABLE`, `reason_code = ZERO_DENOMINATOR`.
- Denominator `< 0` → `UNAVAILABLE`, `reason_code = NEGATIVE_DENOMINATOR`, **and** the
  negative denominator is itself surfaced as a warning (negative EBITDA, negative equity).
- Negative numerators are allowed and reported as negative.
- Every result records `method` (formula version) and `inputs`.

## Composite concepts

### Total debt

```
total_debt = short_term_debt + current_ltd + noncurrent_ltd + finance_lease_liab
           + operating_lease_liab            (if config include_operating_leases: true)
```

- Default `include_operating_leases: true`. Post-ASC 842 these are real fixed obligations;
  credit analysts and rating agencies treat them as debt-like. Always show
  `total_debt_ex_leases` alongside so the effect is visible.
- Missing components are treated as zero **only** for `short_term_debt`,
  `finance_lease_liab` and `operating_lease_liab`, and only when at least one of
  `current_ltd` / `noncurrent_ltd` is present. Record which components were zero-by-absence.
- If neither `current_ltd` nor `noncurrent_ltd` is present but `total_ltd_aggregate`
  (`LongTermDebt`) is, use the aggregate and set `method = debt_from_aggregate`.
- If both components and the aggregate are present, use the components (avoids double
  counting) and flag if they differ from the aggregate by more than 5%.
- If nothing is present → `UNAVAILABLE`, `reason_code = NO_DEBT_DATA`. Do **not** assume
  zero debt.

### Net debt

```
net_debt = total_debt − cash − short_term_investments   (short_term_investments included
                                                          when config include_st_investments: true, default true)
```

Negative net debt (net cash) is valid and reported as negative.

### EBITDA

There is no standard us-gaap EBITDA tag, so v1 EBITDA is always `CALCULATED`:

```
ebitda = ebit + d_and_a
```

- Both inputs must be from the same period; `d_and_a` almost always comes from the
  cash-flow statement.
- Label it everywhere as **"EBITDA (EBIT + D&A)"**. No "adjusted EBITDA" in v1. If a
  company-defined adjusted figure is ever added it is a separate concept and never
  substitutes for this one.
- If `d_and_a` is missing → EBITDA `UNAVAILABLE`. Do not fall back to EBIT.

### Free cash flow

```
fcf = cfo − capex
```

`capex` is stored as a positive outflow. No other definition in v1.

## Metrics

| Metric | Formula | Notes |
|---|---|---|
| debt_to_ebitda | total_debt / ebitda | |
| net_debt_to_ebitda | net_debt / ebitda | primary leverage metric |
| debt_to_capital | total_debt / (total_debt + equity) | negative equity → capital may be ≤ 0 → UNAVAILABLE + warning |
| ebit_interest_cover | ebit / interest_expense | primary coverage metric |
| ebitda_interest_cover | ebitda / interest_expense | secondary; never presented as the same thing |
| current_ratio | current_assets / current_liabilities | |
| quick_ratio | (current_assets − inventory) / current_liabilities | missing inventory → treat as 0 only if the company reports no `InventoryNet` tag in any period (non-inventory business); otherwise UNAVAILABLE |
| cash_to_current_liabilities | cash / current_liabilities | |
| cash_to_debt | cash / total_debt | zero debt → UNAVAILABLE, reason NO_DEBT (not infinite) |
| fcf_margin | fcf / revenue | |
| fcf_to_debt | fcf / total_debt | zero debt → UNAVAILABLE, reason NO_DEBT |
| cfo_to_debt | cfo / total_debt | zero debt → UNAVAILABLE, reason NO_DEBT |
| capex_to_revenue | capex / revenue | |
| revenue_growth | revenue_t / revenue_(t−1) − 1 | needs two consecutive fiscal years |
| ebitda_margin | ebitda / revenue | |
| ebit_margin | ebit / revenue | |
| net_margin | net_income / revenue | |

Dropped from v1: ROA, ROE (equity-holder metrics, not credit-core).

### Coverage edge cases (must be handled, must be tested)

| Situation | Result |
|---|---|
| interest_expense missing, total_debt == 0 | coverage `UNAVAILABLE`, reason `NO_INTEREST_NO_DEBT`; coverage category weight is redistributed (see scoring) |
| interest_expense missing, total_debt > 0 | coverage `UNAVAILABLE`, reason `INTEREST_MISSING_WITH_DEBT`; data-quality flag; category treated as **missing**, not neutral |
| interest_expense == 0, total_debt > 0 | same as above — almost certainly a tag gap, not free debt |
| ebit ≤ 0, interest_expense > 0 | coverage `UNAVAILABLE`, reason `NEGATIVE_EARNINGS`, **but scored in the worst band** — this is evidence, not a data gap |
| ebitda ≤ 0 | all EBITDA-based leverage `UNAVAILABLE`, reason `NEGATIVE_EBITDA`, scored in the worst band |

## Trends

Requires at least three consecutive fiscal years. Otherwise `INSUFFICIENT_DATA`.

For each trended metric compute:
- `change_1y` = latest − prior
- `change_3y` = latest − three years ago

Classification, using per-metric materiality thresholds from `config/thresholds.yaml`:

| Metric | Material change (defaults) | Deteriorating means |
|---|---|---|
| net_debt_to_ebitda | ≥ 0.5x | rising |
| ebit_interest_cover | ≥ 1.0x | falling |
| ebitda_margin | ≥ 2 percentage points | falling |
| revenue_growth | growth < 0, or growth fell ≥ 5pp | falling |
| fcf | ≥ 20% | falling |
| cash_to_current_liabilities | ≥ 0.1 | falling |
| total_debt | ≥ 15% | rising |

- **Deteriorating**: `change_1y` material in the bad direction, or `change_3y` material and
  monotonic (each year worse than the last).
- **Improving**: the same, in the good direction.
- **Stable**: neither.

## Early warnings

Each warning is a row: `indicator, current_value, previous_value, change, threshold,
severity, evidence (input concepts + sources)`.

| Indicator | Trigger | Base severity |
|---|---|---|
| Leverage deterioration | net_debt_to_ebitda Deteriorating | Medium |
| Coverage deterioration | ebit_interest_cover Deteriorating | Medium |
| Cash-flow deterioration | fcf Deteriorating | Medium |
| Margin deterioration | ebitda_margin Deteriorating | Low |
| Revenue deterioration | revenue_growth Deteriorating | Low |
| Liquidity deterioration | cash_to_current_liabilities Deteriorating | Medium |
| Debt increase | total_debt Deteriorating | Low |
| Negative FCF | fcf < 0 | Medium |
| Negative EBITDA | ebitda ≤ 0 | High |
| Negative equity | equity ≤ 0 | High |
| Coverage below 2.0x | ebit_interest_cover < 2.0 | High |

**Escalation:** if three or more warnings fire in the same period, raise every warning
one severity level (Low→Medium→High). Record that escalation was applied and why.

## Scoring

### Categories and weights (config defaults)

| Category | Weight | Component metrics |
|---|---|---|
| Leverage | 25 | net_debt_to_ebitda (primary), debt_to_capital |
| Coverage | 20 | ebit_interest_cover |
| Liquidity | 20 | current_ratio, cash_to_current_liabilities |
| Cash flow | 20 | fcf_to_debt, fcf_margin |
| Business performance | 15 | revenue_growth, ebitda_margin trend |

### Bands

Each component metric maps to 0–10 points via band edges in `config/thresholds.yaml`.
Defaults for the two primary metrics (others follow the same shape):

**net_debt_to_ebitda** (lower is better)

| Value | Points | Label |
|---|---|---|
| < 1.0x | 10 | Very low |
| 1.0–2.0x | 8 | Low |
| 2.0–3.0x | 6 | Moderate |
| 3.0–4.0x | 4 | Elevated |
| 4.0–5.0x | 2 | High |
| ≥ 5.0x, or NEGATIVE_EBITDA | 0 | Very high |
| net cash (negative) | 10 | |

**ebit_interest_cover** (higher is better)

| Value | Points |
|---|---|
| ≥ 8.0x | 10 |
| 5.0–8.0x | 8 |
| 3.0–5.0x | 6 |
| 2.0–3.0x | 4 |
| 1.0–2.0x | 2 |
| < 1.0x, or NEGATIVE_EARNINGS | 0 |

### Aggregation

```
component_points   = band lookup (0–10)
category_score     = mean(component_points across available components) / 10 × weight
total_score        = sum(category_score)          → 0–100
```

### Missing data in scoring

- A component `UNAVAILABLE` for a **data-gap** reason (`MISSING_INPUT`, `INTEREST_MISSING_WITH_DEBT`)
  is dropped and the category is the mean of the remaining components. If a whole category
  is unavailable, `total_score` is rescaled over the available categories **and**:
  - the output states "score based on N of 5 categories";
  - the grade is capped at `config max_grade_with_missing_category` (default: Grade 3).
- A component `UNAVAILABLE` for an **evidence** reason (`NEGATIVE_EARNINGS`,
  `NEGATIVE_EBITDA`) scores 0 points. It is not dropped.
- `NO_INTEREST_NO_DEBT` (unlevered company): Coverage category is dropped and its weight
  redistributed pro rata. No grade cap — this is a good thing, not a gap.

### Grades

| Score | Grade | Label |
|---|---|---|
| 85–100 | 1 | Very strong |
| 70–84 | 2 | Strong |
| 55–69 | 3 | Moderate |
| 40–54 | 4 | Elevated |
| 25–39 | 5 | High risk |
| 0–24 | 6 | Very high risk |

Always described as an **internal analytical grade for this project**. Never mapped to
S&P/Moody's/Fitch letters or to any bank's internal scale.

### Explain output (required for every score)

- Category breakdown: points, weight, contribution
- Per component: metric, value, band, points, trend, source
- Strongest two categories, weakest two categories
- Deteriorating metrics (from trends)
- Positive mitigants (metrics in top band)
- Top drivers: the three components that cost the most points versus a perfect score

## Stress testing

All stress inputs are `ASSUMED` and go in the assumption register. All stress outputs are
`CALCULATED` with `method = stress_v1`.

### Inputs

| Shock | Unit | Presets (config/stress.yaml) |
|---|---|---|
| revenue_shock | % | −5, −10, −15, −20 |
| margin_shock | percentage points of EBITDA margin | −1, −3, −5 |
| rate_shock | basis points | +100, +200, +300 |
| additional_debt | currency | 0 |
| capex_shock | % | 0 |

Preset scenarios: **Base** (nothing), **Moderate** (rev −10%, margin −2pp, rates +100bps),
**Severe** (rev −20%, margin −5pp, rates +200bps), **Custom**.

### Propagation rules (the part that must be explicit)

```
revenue_s   = revenue × (1 + revenue_shock)

# EBITDA — mode A (default, "constant margin"):
margin_s    = ebitda_margin_base − margin_shock
ebitda_s    = revenue_s × margin_s

# EBITDA — mode B ("operating leverage", config stress.ebitda_mode: operating_leverage):
costs_base  = revenue − ebitda
fixed       = fixed_cost_share × costs_base            # fixed_cost_share is ASSUMED, default 0.3
var_ratio   = (1 − fixed_cost_share) × costs_base / revenue
ebitda_s    = revenue_s − fixed − var_ratio × revenue_s
ebitda_s    = ebitda_s − margin_shock × revenue_s      # margin shock applied after

d_and_a_s   = d_and_a                                  # held constant
ebit_s      = ebitda_s − d_and_a_s

debt_s      = total_debt + additional_debt
interest_s  = interest_expense
            + rate_shock × floating_share × total_debt  # floating_share ASSUMED, default 1.0
            + new_debt_rate × additional_debt           # new_debt_rate ASSUMED, default = interest_expense / total_debt if > 0 else config default

etr         = tax_expense / pretax_income   if pretax_income > 0, else config default_tax_rate (ASSUMED)
tax_s       = max(0, ebit_s − interest_s) × etr
net_inc_s   = ebit_s − interest_s − tax_s

cfo_s       = ebitda_s − interest_s − tax_s            # approximation: working-capital change held at zero, ASSUMED
capex_s     = capex × (1 + capex_shock)
fcf_s       = cfo_s − capex_s

net_debt_s  = net_debt + additional_debt               # no cash sweep, ASSUMED
```

Then recompute `net_debt_to_ebitda`, `debt_to_ebitda`, `ebit_interest_cover`,
`ebitda_interest_cover`, `fcf_to_debt`, `fcf_margin`, `ebitda_margin`, and re-score to get
the **stressed grade**. Liquidity ratios are **not** stressed in v1 (balance-sheet
liquidity is held at base); say so in the output.

Documented simplifications (state them in every stress output): D&A held flat; whole debt
stack reprices if `floating_share = 1.0`; working capital held flat; no cash sweep; tax
floored at zero.

### Stress output

Table of base vs stressed for each metric above plus grade, and a **driver attribution**:
run each shock **alone** against base and report the metric change it causes on its own.
That is how "which assumption caused the change" is answered — deterministically, not by
narrative.

### Sensitivity grid (v1, simple)

Two-variable grid, revenue_shock × margin_shock, reporting `net_debt_to_ebitda` and grade
in each cell. Nothing more elaborate in v1.

## Integrity checks (run on every ingested period)

| Check | Rule | On failure |
|---|---|---|
| Balance sheet balances | abs(total_assets − (total_liabilities + equity)) / total_assets ≤ 1% | warn (minority-interest presentation differs; don't reject) |
| Current ⊆ total | current_assets ≤ total_assets; current_liabilities ≤ total_liabilities | fail |
| Cash ⊆ current assets | cash ≤ current_assets | fail |
| Debt ⊆ liabilities | total_debt_ex_leases ≤ total_liabilities | fail |
| Non-negative revenue | revenue ≥ 0 | fail |
| Period continuity | consecutive fiscal years with no gap for trend use | warn, trend INSUFFICIENT_DATA |
| Abnormal movement | any core concept moves > 300% year-on-year | warn, surface for review |

"Fail" means the period is stored but marked `integrity = FAIL` and excluded from scoring
until reviewed. Never silently accepted.

## Assumption register

Every `ASSUMED` value is a row: `assumption, value, unit, reason, source (user/config),
date, status, affects (list of outputs)`.

## Analyst overrides

An analyst may override a reported or assumed input. Store `original_value,
override_value, reason, user, timestamp`. The original is never modified; outputs computed
from an override carry `override_applied = true` and list which one.

## Calibration

The band edges and weights above are **starting assumptions for this project**. When
reviewing them, use these public reference points — and describe them as reference points,
not as the source of the bands:

- Rating agencies publish sector methodology grids showing the leverage and coverage
  ranges they associate with each rating category. Use them to sanity-check band shape.
- The 2013 US interagency Leveraged Lending Guidance flags total debt / EBITDA above 6.0x
  as raising concern for most industries — a useful upper anchor for the "very high" band.

Record any change to a band or weight in `DECISIONS.md` with the reason.
