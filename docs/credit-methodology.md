# Credit methodology

Every formula, edge case and threshold the engine uses. If it isn't written here, the
engine shouldn't be doing it. Numbers in `config/thresholds.yaml` and `config/stress.yaml`
are **project assumptions** — see "Calibration" at the end.

## General rules for every calculation

- Inputs must be from the **same fiscal period** and the **same filing**, unless the
  formula is explicitly a period-over-period comparison. "Same filing" means what
  selection already enforces — no mixing of quarterly and annual data or of different
  fiscal periods — not literal accession equality: D15 deliberately keeps an
  equal-value fact at its original filing's provenance, so the CURRENT facts for one
  period legitimately span accessions after a restatement, and composites accept them
  (D33).
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

That formula is the **plain-components** composition. Two other branches exist and are
defined below: `debt_from_aggregate` and `debt_from_lease_inclusive_ltd`. Exactly one
branch applies per period, and the method is always recorded.

- Default `include_operating_leases: true` (set in `config/composites.yaml`, never in
  code — D28). Post-ASC 842 these are real fixed obligations; credit analysts and rating
  agencies treat them as debt-like. Show `total_debt_ex_leases` alongside so the effect is
  visible **wherever it can be computed** — the one exception is the lease-inclusive LTD
  branch below, where the filer bundles debt and leases into one figure, leases are not
  separable, and `total_debt_ex_leases` is `UNAVAILABLE` with
  `reason_code = LEASES_NOT_SEPARABLE` (D27). It is never estimated.
- Missing components are treated as zero **only** for `short_term_debt`,
  `finance_lease_liab` and `operating_lease_liab`, and only when at least one of
  `current_ltd` / `noncurrent_ltd` is present. Within the `current_ltd` /
  `noncurrent_ltd` pair itself, the missing member is likewise treated as zero when the
  other is present — this is the composition D26's consequences were measured under, and
  the reconciliation rule below is what polices it where an aggregate exists (D33).
  Record which components were zero-by-absence.
- The lease composites are sums of their split concepts:
  `finance_lease_liab = finance_lease_liab_current + finance_lease_liab_noncurrent`,
  and likewise for `operating_lease_liab`; a missing half counts as zero under the same
  zero-by-absence recording.
- `total_debt_ex_leases = short_term_debt + current_ltd + noncurrent_ltd` — it excludes
  **both** lease kinds, finance and operating (D33). The figure must mean the same thing
  on every branch, and the lease-inclusive bundle contains finance leases; an
  operating-only reading would make it change definition by branch.
- **`DebtCurrent` guard (D32).** When `short_term_debt` resolves via the `DebtCurrent`
  tag **and** `current_ltd` resolves in the same period, `total_debt` is `UNAVAILABLE`,
  `reason_code = ST_DEBT_SCOPE_UNCERTAIN`, both values recorded. The taxonomy defines
  `DebtCurrent` as including current LTD maturities, but filers deviate (JNJ's excludes
  them), so the overlap with `current_ltd` cannot be verified from the data and the sum
  may double-count. The reconciliation rule below does **not** police this — its
  comparison basis is long-term components only. When `current_ltd` does not resolve, no
  overlap is possible and `DebtCurrent` is usable.
- If neither `current_ltd` nor `noncurrent_ltd` is present but `total_ltd_aggregate`
  (`LongTermDebt`) is, use the aggregate and set `method = debt_from_aggregate`. The
  aggregate substitutes for `current_ltd + noncurrent_ltd` in the same formula:
  `short_term_debt` and the lease components (per the toggle) are still added.
- **If the aggregate and at least one component are both present, reconcile them before
  using either** (DECISIONS D26):
  - Compare `current_ltd + noncurrent_ltd` against `total_ltd_aggregate`. A missing
    component counts as zero **for this comparison only** — that is the point of the
    check, since a silently absent component is what makes the components wrong.
  - The comparison basis is the long-term components **only**. `short_term_debt` is
    excluded: `LongTermDebt` is a long-term-debt tag, so this is the apples-to-apples
    comparison. Be aware the tag's scope varies by filer — some include short-term
    borrowings in it, which shows up as a real deviation rather than an exact match.
  - Deviation **within** `config/composites.yaml: component_aggregate_tolerance`
    (default 0.05) → use the components, `method = debt_from_components`, as before.
  - Deviation **above** tolerance → `total_debt` is `UNAVAILABLE`,
    `reason_code = COMPONENT_AGGREGATE_MISMATCH`. It is **not** computed-and-flagged.
    Two mutually contradictory figures for the same quantity mean we do not know the
    debt; emitting one of them with a warning attached produces a plausible-looking
    wrong number with full provenance, which rule 9 forbids. Record both figures on the
    UNAVAILABLE record so the disagreement is reviewable.
- **Lease-inclusive LTD branch** (DECISIONS D27). Some filers report long-term debt only
  bundled with capital/finance lease obligations, mapped to `ltd_incl_leases_current` and
  `ltd_incl_leases_noncurrent`. **Both members of the pair must resolve** — a
  half-resolved pair falls through to `NO_DEBT_DATA`: half of an already-weaker branch,
  with no reconciliation available on that half, is the least-trustworthy input in the
  tree (D33). When both resolve:

  ```
  total_debt = ltd_incl_leases_current + ltd_incl_leases_noncurrent + short_term_debt
  method     = debt_from_lease_inclusive_ltd
  ```

  Lease components are **not** added on this branch — they are already inside the bundled
  figures, and adding them would double-count.
  - **Precedence: the plain path wins.** If `current_ltd`, `noncurrent_ltd` or
    `total_ltd_aggregate` resolves for the same period, this branch is **not** taken. The
    plain concepts are debt alone, so they keep leases separable; and the plain path can
    be policed by the reconciliation rule above, which this branch often cannot.
  - **Consistency check, same tolerance.** Where `ltd_incl_leases_aggregate` resolves,
    compare it against `ltd_incl_leases_current + ltd_incl_leases_noncurrent`; beyond
    `component_aggregate_tolerance` → `UNAVAILABLE`,
    `reason_code = COMPONENT_AGGREGATE_MISMATCH`. `ltd_incl_leases_aggregate` is a
    **cross-check only and never a value source** — comparing against a second source is
    reliable, deriving a value from it is not.
  - `total_debt_ex_leases` → `UNAVAILABLE`, `reason_code = LEASES_NOT_SEPARABLE`. It is
    **never** approximated by subtracting the standalone lease tags: nothing guarantees
    those cover the same obligations as the bundled figure, so the subtraction would be a
    fabricated number.
  - `include_operating_leases` is **inoperative** on this branch — the composition is
    fixed by what the filer reported, and there is no separable lease figure to include or
    omit. A row on this branch still records the config fingerprint in effect when it was
    written (D18), including a lease toggle that had no effect on it; the
    `LEASES_NOT_SEPARABLE` record on `total_debt_ex_leases` is what makes that visible,
    so a fingerprint change must not be read as implying the value should have moved.
- If nothing is present → `UNAVAILABLE`, `reason_code = NO_DEBT_DATA`. Do **not** assume
  zero debt.

### Net debt

```
net_debt = total_debt − cash − short_term_investments   (short_term_investments included
                                                          when config include_st_investments: true, default true)
```

Negative net debt (net cash) is valid and reported as negative.

- `cash` missing → `UNAVAILABLE`, `MISSING_INPUT:cash` — it is the substantive input.
- `short_term_investments` missing → treated as **zero-by-absence** and recorded as
  such, like `total_debt`'s optional components (D33). It is a refinement, not the
  substance: enforcing `MISSING_INPUT` for it would kill `net_debt` in 61 of the 87
  cash-periods across the five validated companies, including every LUMN and KHC period.
- `total_debt` `UNAVAILABLE` → `net_debt` `UNAVAILABLE`, `MISSING_INPUT:total_debt`.

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
| net_debt_to_ebitda | net_debt / ebitda | headline leverage metric — **no arithmetic weighting**, see Scoring (D45a) |
| debt_to_capital | total_debt / (total_debt + equity) | negative equity → capital may be ≤ 0 → UNAVAILABLE + warning |
| ebit_interest_cover | ebit / interest_expense | headline coverage metric — **no arithmetic weighting**, see Scoring (D45a) |
| ebitda_interest_cover | ebitda / interest_expense | secondary; never presented as the same thing. Carries every coverage edge case `ebit_interest_cover` does; `ebitda ≤ 0` gives `NEGATIVE_EBITDA`, kind EVIDENCE (D42d) |
| current_ratio | current_assets / current_liabilities | |
| quick_ratio | (current_assets − inventory) / current_liabilities | missing inventory → treat as 0 only if the company reports no `InventoryNet` tag in any period (non-inventory business); otherwise UNAVAILABLE. "In any period" means **no `inventory` concept resolves in any period** (D42b), not the tag's presence in the raw payload |
| cash_to_current_liabilities | cash / current_liabilities | |
| cash_to_debt | cash / total_debt | zero debt → UNAVAILABLE, reason `NO_DEBT` (not infinite). `NO_DEBT` is kind **NEITHER** — an unlevered company is not a data gap (D42a) |
| fcf_margin | fcf / revenue | |
| fcf_to_debt | fcf / total_debt | zero debt → UNAVAILABLE, reason NO_DEBT |
| cfo_to_debt | cfo / total_debt | zero debt → UNAVAILABLE, reason NO_DEBT |
| capex_to_revenue | capex / revenue | |
| revenue_growth | revenue_t / revenue_(t−1) − 1 | needs two consecutive fiscal years. **Two rules, both required** (D43): the prior period is the most recent one that *resolves revenue* (eligibility, D40), and that pair must then fall within `continuity_window_days` (the window, D36). Otherwise `INSUFFICIENT_DATA`. Applying only the window lets a period resolving nothing swallow a legitimate comparison; applying only eligibility lets a genuine multi-year gap pass as one-year growth |
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
| interest_expense < 0, total_debt > 0 | same as above (D41f) — negative interest expense is a tagging artefact, not free money, and never produces a negative coverage ratio |
| interest_expense missing, total_debt `UNAVAILABLE` | coverage `UNAVAILABLE`, reason `MISSING_INPUT:total_debt` (D41b) — the gate itself could not be evaluated, so this is a gap about the gate, not a claim about the company |
| ebit ≤ 0, interest_expense > 0 | coverage `UNAVAILABLE`, reason `NEGATIVE_EARNINGS`, **but scored in the worst band** — this is evidence, not a data gap |
| ebitda ≤ 0 | all EBITDA-based leverage `UNAVAILABLE`, reason `NEGATIVE_EBITDA`, scored in the worst band |

**Rule order: the interest gate runs before the earnings check** (D41c). When `ebit ≤ 0`
*and* interest is missing or zero with debt present, both rows apply and the interest row
wins. The reason is substantive, not the order they appear in: a missing denominator means
the ratio was **never computable**, whereas negative earnings is a statement **about a
ratio you could have computed**. The evidence claim presupposes a working comparison, so
the gap is reported first.

**`ebitda == 0` takes `NEGATIVE_EBITDA`** (D41d). The rule is `≤ 0`, so zero takes this
code despite the name. The code names the **band** — worst — rather than the sign, and a
company whose EBITDA is exactly zero belongs in that band for the same reason a negative
one does: it covers none of its debt from earnings. Not a bug.

### Reason kinds

Every `UNAVAILABLE` reason is one of three kinds. The split is what D9 makes load-bearing
for scoring, and it lives in one place — the `REASON_KIND` mapping in `metrics/ratios.py`
— rather than in a stored column, because it is fully derivable from the reason code
(D41a).

| Kind | Reasons | Scoring treatment (Phase 6) |
|---|---|---|
| **EVIDENCE** | `NEGATIVE_EBITDA`, `NEGATIVE_EARNINGS` | scores 0, worst band — this is the company's real condition |
| **GAP** | `MISSING_INPUT:*`, `INTEREST_MISSING_WITH_DEBT`, `ZERO_DENOMINATOR`, `NEGATIVE_DENOMINATOR` | dropped; grade capped (see "Missing data in scoring") |
| **NEITHER** | `NO_INTEREST_NO_DEBT`, `NO_DEBT` | category weight redistributed, **no grade cap** — an unlevered company is not a data gap |

`INSUFFICIENT_DATA` (from `revenue_growth`) is a **GAP**: the prior period was not
available to compare against.

**A negative-revenue period produces two signals, and that is not double-counting**
(D42e): the integrity check asks whether the data is *possible*, and the margin metrics
ask whether they can be *computed*. Both answers are wanted — one marks the period unfit
for scoring, the other explains why a particular number is absent.

A negative denominator additionally emits a `NEGATIVE_DENOMINATOR` row in
`data_quality_events` (D41e), following the same split as the integrity checks: a
per-value warning is an event, a check outcome is an `integrity_results` row.

## Trends

Requires at least three consecutive fiscal years. Otherwise `INSUFFICIENT_DATA`.

**Consecutive means what D36 and D40 mean by it, applied to the metric being trended
(D49).** A period is eligible for a trend on metric M when **M itself resolves there** —
a period that resolves nothing, or resolves other metrics but not M, is not a link in M's
chain — and a window is valid only when **every** consecutive day-gap in it falls inside
`continuity_window_days`. Eligibility is per rule, determined by the series that rule
actually reads; it is not a property of the period in general.

For each trended metric compute:
- `change_1y` = latest − prior
- `change_over_window` = latest − **earliest of the three-period window**

*(Renamed from `change_3y`, which was wrong: three consecutive years give t, t−1, t−2, so
the earliest point is **two** intervals back, not three. The label implied three intervals
where the stated minimum gives two. Requiring a fourth period to match the old name would
have cost 12% of available windows — measured — to satisfy a name. The name was what was
wrong, not the arithmetic. D49.)*

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

- **Deteriorating**: `change_1y` material in the bad direction, or `change_over_window`
  material and monotonic (each year worse than the last).
- **Improving**: the same, in the good direction.
- **Stable**: neither.

**Monotonic is strict** (D49): a flat year breaks it. A stalled series is not "each year
worse than the last".

**Materiality units are mixed**, and `config/thresholds.yaml` marks which is which. Five
thresholds are absolute changes in the metric's own units; `fcf` and `total_debt` are
**relative** — proportions of the base period — and are listed under `relative:` in the
config. A relative change with a **zero base** yields `INSUFFICIENT_DATA` rather than an
undefined proportion, the same refusal shape as D34.

**`revenue_growth`'s verdict does not mean the same thing as the other six** (D49). Its
trigger is "growth < 0, **or** growth fell ≥ 5pp" — an absolute level test OR a change
test, where every other metric uses change alone. And because it trends a growth *rate*,
its `change_1y` is an **acceleration**, not a change in level. A "Deteriorating"
`revenue_growth` therefore asserts something different from a "Deteriorating"
`net_debt_to_ebitda`, and output that presents the seven verdicts together must not imply
they are the same kind of claim.

**Trend verdicts score** through `config/thresholds.yaml: trend_points`
(Improving 10, Stable 6, Deteriorating 0) — Stable sits just above the midpoint because
holding steady is better than drifting, and mid-band values elsewhere are reserved for
genuinely middling performance. `INSUFFICIENT_DATA` is a data gap, not a verdict, and is
treated as one in scoring (D50).

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

**Escalation:** if `config warning_escalation_count` (default 3) or more warnings fire in
the same period, raise every warning one severity level (Low→Medium→High). High stays
High. Record that escalation was applied **and why** — the stored reason names the count
that fired and the threshold that triggered it (D51).

Warning rows carry a fingerprint of the trend and escalation settings in force (D52): a
warning that stopped firing because a threshold moved must be distinguishable from one
that stopped because the company improved. That fingerprint is **disjoint from the score
fingerprint** — these settings change warnings, not scores — with the single exception of
`trend_points`, which moves scores and belongs to the score fingerprint instead.

## Scoring

### Categories and weights (config defaults)

| Category | Weight | Component metrics |
|---|---|---|
| Leverage | 25 | net_debt_to_ebitda, debt_to_capital |
| Coverage | 20 | ebit_interest_cover |
| Liquidity | 20 | current_ratio, cash_to_current_liabilities |
| Cash flow | 20 | fcf_to_debt, fcf_margin |
| Business performance | 15 | revenue_growth, ebitda_margin trend |

Components within a category are **equally weighted** — the category score is their plain
mean. No component is "primary" in any arithmetic sense; the word was removed from this
table because it implied a weighting the spec never defines (D45a).

`ebitda_margin trend` is scored from a trend verdict rather than a metric value, through
`config/thresholds.yaml: trend_points` (D50). Before Phase 7 it carried the treatment
`not_yet_implemented` and was excluded from all counting — treating an unbuilt feature as a
data gap would have capped every company in every period. That mechanism remains for any
future component that must join the row shape before it can be scored; nothing uses it
today.

### Bands

Each component metric maps to 0–10 points via band edges in `config/thresholds.yaml`.
Defaults for the two headline metrics (others follow the same shape):

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
  - the grade is capped by **how many categories scored** (D46), from
    `config max_grade_by_categories_scored`: **N ≤ 2 → grade 4**, **N = 3–4 → grade 3**,
    N = 5 uncapped. A 2-of-5 score must not present with the same authority as a 4-of-5
    one, and a graduated cap keeps every period scoreable while making the confidence
    difference visible in the grade itself.
- A component `UNAVAILABLE` for an **evidence** reason (`NEGATIVE_EARNINGS`,
  `NEGATIVE_EBITDA`) scores 0 points. It is not dropped.
- `NO_INTEREST_NO_DEBT` (unlevered company): Coverage category is dropped and its weight
  redistributed pro rata. No grade cap — this is a good thing, not a gap.

### Grades

Grade boundaries are **half-open intervals on the lower bound**: `[70, 85)` is grade 2, so
a score of 84.9 is grade 2 and 85.0 is grade 1 (D45b). The integers below are bounds, not
truncation.

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
- **The cap line, always, when a cap applied**: the final grade, the uncapped grade, how
  many of the five categories scored, and which categories were absent **with their cause**
  (data gap vs unlevered vs not-yet-implemented). This is a correctness constraint, not a
  presentation choice: capped grades are systematic rather than exceptional — four of the
  five current demonstration companies can never produce a five-category score — and a
  capped grade must never be indistinguishable from a judged one. It is generated from
  stored columns (`grade_uncapped`, `cap_binding`, `categories_available`) so a consumer
  cannot omit it by accident.

## Stress testing

All stress inputs are `ASSUMED` and go in the assumption register. All stress outputs are
`CALCULATED` with `method = stress_v1`.

### Inputs

| Shock | Unit | Presets (config/stress.yaml) |
|---|---|---|
| revenue_shock | % | −5, −10, −15, −20 |
| margin_shock | percentage points of EBITDA margin | see presets table below — sign convention: positive value reduces margin |
| rate_shock | basis points | +100, +200, +300 |
| additional_debt | currency | 0 |
| capex_shock | % | 0 |

Preset scenarios: **Base** (nothing), **Moderate** (rev −10%, margin −2pp, rates +100bps),
**Severe** (rev −20%, margin −5pp, rates +200bps), **Custom**.

**The presets deliberately do not model incremental borrowing** — `additional_debt` is 0
in every preset (D53c). How much a company borrows in a downturn is company-specific, and
a global scenario cannot assert it; incremental debt is a custom-scenario lever. The
absence is a design choice, not an omission.

### Propagation rules (the part that must be explicit)

```
revenue_s   = revenue × (1 + revenue_shock)

# EBITDA — mode A (default, "constant margin"):
margin_s    = ebitda_margin_base − margin_shock
ebitda_s    = revenue_s × margin_s

# EBITDA — mode B ("operating leverage", config stress.ebitda_mode: operating_leverage):
costs_base  = revenue − ebitda
fixed       = fixed_cost_share × costs_base            # fixed_cost_share is ASSUMED, default 0.3;
                                                        # overridable per custom scenario, and every
                                                        # operating-leverage output PRINTS the value
                                                        # used (D53a) — the grade moves ≤1 level across
                                                        # [0.2, 0.7] at preset shocks, but the stressed
                                                        # figures swing widely and can flip sign
var_ratio   = (1 − fixed_cost_share) × costs_base / revenue
ebitda_s    = revenue_s − fixed − var_ratio × revenue_s
ebitda_s    = ebitda_s − margin_shock × revenue_s      # margin shock applied after

d_and_a_s   = d_and_a                                  # held constant
ebit_s      = ebitda_s − d_and_a_s

debt_s      = total_debt + additional_debt
interest_s  = interest_expense
            + rate_shock × floating_share × total_debt  # floating_share ASSUMED, default 1.0
            + new_debt_rate × additional_debt           # new_debt_rate ASSUMED (D53b): explicit config
                                                        # override if set; else the implied rate
                                                        # interest_expense / total_debt IF it falls inside
                                                        # config new_debt_rate_band; else
                                                        # new_debt_rate_default. The band exists because
                                                        # both failure directions occur in real data —
                                                        # Ford's captive-finance 287-860% and JNJ's
                                                        # ZIRP-era 0.51-0.67% — and every substitution is
                                                        # surfaced in the output: which rate, and why

etr         = tax_expense / pretax_income   if pretax_income > 0, else config default_tax_rate (ASSUMED).
                                             # Missing tax_expense or pretax_income falls back to the
                                             # same default_tax_rate, recorded as ASSUMED (D53d)
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

Both EBITDA modes run correctly from a **negative base margin**: a company already at
negative EBITDA stresses to deeper-negative EBITDA, which carries `NEGATIVE_EBITDA`
evidence into the stressed metrics and saturates the stressed grade at 6. Designed, not
incidental (D53d).

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

| Check (stored name) | Rule | On failure |
|---|---|---|
| `balance_sheet_balances` | abs(total_assets − (total_liabilities + equity)) / total_assets ≤ 1% | warn (minority-interest presentation differs; don't reject) |
| `current_assets_subset` | current_assets ≤ total_assets | fail |
| `current_liabilities_subset` | current_liabilities ≤ total_liabilities | fail |
| `cash_subset` | cash ≤ current_assets | fail |
| `debt_subset` | total_debt_ex_leases ≤ total_liabilities | fail |
| `revenue_non_negative` | revenue ≥ 0 | fail |
| `period_continuity` | consecutive periods with no gap for trend use | warn, trend INSUFFICIENT_DATA |
| Abnormal movement | any **core concept** (defined below) moves > 300% year-on-year | warn, surface for review |

"Current ⊆ total" is **two** stored checks, not one (D39b): the asset and liability
comparisons have independent inputs, so one can run while the other skips, and a single
row could not say which produced the outcome.

Thresholds come from `config/integrity.yaml`, never from code — deliberately a separate
file from the D18-fingerprinted `config/composites.yaml`, because these change verdicts
rather than values (D38).

### Outcomes

Every check yields exactly one of four outcomes per period:

| Outcome | Meaning |
|---|---|
| `PASS` | the comparison ran and held |
| `WARN` | it ran and did not hold, but the rule says don't reject |
| `FAIL` | it ran and did not hold; the period is excluded from scoring |
| `SKIP` | an input was `UNAVAILABLE`, so the comparison could not run |

**`SKIP` is not a pass.** A missing input is a data gap, not a violation — the same
evidence-versus-gap split as D9 — so a company whose inputs never resolved must not read
as clean as one that genuinely passed. The per-period verdict is FAIL if any check
failed, else WARN if any warned, else PASS; it is **derived, never stored** (D37), and
the summary reports how many checks actually ran so a period that passed on zero evidence
is visible as such.

A zero or negative `total_assets` makes the balance-sheet check `SKIP`, not a division
(D39a; general rule 4).

"Fail" means the period is stored but marked `integrity = FAIL` and **excluded from
scoring until the underlying data is corrected and re-ingested** — v1 has no interactive
review path, and a FAIL period gets no score row at all (D45). Never silently accepted.
The `overrides` table is value-scoped by design; overriding a *verdict* would be a new
table and a new workflow, and is a v2 feature if ever wanted.

### What counts as consecutive

Two periods are consecutive when the **gap between their `period_end` dates** falls in
`config/integrity.yaml: continuity_window_days` (350–380), matching selection rule 2's
duration window. It is **never** a calendar-year step: a 52/53-week filer's FY2009 can end
2010-01-03, so calendar arithmetic invents gaps that do not exist (D36).

Continuity runs over **trend-eligible periods only** — those with at least one resolved
concept. A period where nothing resolved is not a trend period, so it is not a link in the
chain; it still receives every other check, all skipping, so it is recorded rather than
hidden (D40).

### Core concepts (abnormal-movement scope)

The abnormal-movement check runs over these 16 concepts only — not all 31 in
`config/tag_map.yaml`. A large move in something like `dividends` is ordinary corporate
behaviour and would only generate noise.

**Composites:** `total_debt`, `net_debt`, `ebitda`, `fcf`.

**Reported concepts feeding the composites and the ratios:** `revenue`, `ebit`,
`d_and_a`, `interest_expense`, `cash`, `total_assets`, `total_liabilities`, `equity`,
`current_assets`, `current_liabilities`, `cfo`, `capex`.

Composites are in scope deliberately: they aggregate several tags, so a single
mis-mapped input surfaces in the composite before it surfaces in any individual
reported concept (DECISIONS D23).

### Abnormal-movement edge cases

A percentage move is not always defined. These two cases flag rather than being skipped,
the same way a ratio with a bad denominator returns `UNAVAILABLE` with a reason code
instead of a misleading number:

| Situation | Result |
|---|---|
| Sign change between periods (e.g. EBITDA positive → negative) | flag, reason `ABNORMAL_SIGN_CHANGE`, **regardless of magnitude** — it is not a percentage move in any meaningful sense |
| Prior-period value is zero | flag, reason `ABNORMAL_FROM_ZERO` — never compute an undefined or infinite percentage |
| Otherwise | flag, reason `ABNORMAL_MOVEMENT`, when `abs(value_t / value_(t−1) − 1) > 3.0` |

Neither edge case silently skips the concept. A concept `UNAVAILABLE` in either period is
not an abnormal movement — it is already recorded as a data gap.

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
