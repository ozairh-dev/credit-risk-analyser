# Risk scoring

The scoring model in one place: how seventeen metrics become five category scores, a total
out of 100, and a grade 1–6 that says how much of itself is missing.

**Every number in this document is a documented project assumption, not a calibrated
value.** No band edge, weight or grade boundary has been tested against defaults, losses or
agency ratings, because the project has no such data and cannot acquire any at £0. What
*is* evidence-backed is stated as such and carries its basis. See `credit-methodology.md`
for the formulas and `DECISIONS.md` for why each choice was made.

## What a grade is

An integer 1–6 on an **internal analytical scale defined by this project**. It is not a
credit rating and is never mapped to an agency scale. A grade computed on fewer than five
categories is **capped**, and the cap line names the missing categories and their causes.

| Score | Grade | Label |
|---|---|---|
| 85–100 | 1 | Very strong |
| 70–84 | 2 | Strong |
| 55–69 | 3 | Moderate |
| 40–54 | 4 | Elevated |
| 25–39 | 5 | High risk |
| 0–24 | 6 | Very high risk |

Boundaries are **half-open on the lower bound**: `[70, 85)` is grade 2, so 84.9 is grade 2
and 85.0 is grade 1 (D45b). The integers above are bounds, not truncation.

## Categories, weights and components

| Category | Weight | Components |
|---|---|---|
| Leverage | 25 | `net_debt_to_ebitda`, `debt_to_capital` |
| Coverage | 20 | `ebit_interest_cover` |
| Liquidity | 20 | `current_ratio`, `cash_to_current_liabilities` |
| Cash flow | 20 | `fcf_to_debt`, `fcf_margin` |
| Business performance | 15 | `revenue_growth`, `ebitda_margin_trend` |

Components within a category are **equally weighted** — the category score is their plain
mean. No component is "primary" in any arithmetic sense; the word was deliberately removed
because it implied a weighting the model never defines (D45a).

```
component_points  = band lookup (0–10)
category_score    = mean(points across counted components) / 10 × weight
total_score       = Σ category_score            → 0–100
```

**Nine of the seventeen metrics feed the grade** — the eight above, plus `ebitda_margin`,
which enters through its *trend* rather than its level. The other eight —
`debt_to_ebitda`, `ebitda_interest_cover`, `quick_ratio`, `cash_to_debt`, `cfo_to_debt`,
`capex_to_revenue`, `ebit_margin`, `net_margin` — are computed, stored with full provenance
and shown in the evidence pack, but do not score.

The methodology designates the scored ones as headline metrics per category and calls
`ebitda_interest_cover` explicitly "secondary, never presented as the same thing" as
`ebit_interest_cover` (D42d). **Beyond that, no decision entry records why each of the
other seven is excluded** — the component list came from the methodology's category table
and was never revisited. That is an undocumented assumption, listed as one below rather
than given a rationale here after the fact.

## Bands

Every band edge lives in `config/thresholds.yaml`; none is hard-coded (CLAUDE.md rule 6).
**The tables below are generated from that file**, so they cannot drift from the engine, and
each was checked against `scoring.engine.band_points` before publication.


**`net_debt_to_ebitda`** — lower is better (leverage)

| Value | Points |
|---|---|
| < 1x | 10 |
| 1x – 2x | 8 |
| 2x – 3x | 6 |
| 3x – 4x | 4 |
| 4x – 5x | 2 |
| ≥ 5x | 0 |

**`debt_to_capital`** — lower is better (leverage)

| Value | Points |
|---|---|
| < 20% | 10 |
| 20% – 35% | 8 |
| 35% – 50% | 6 |
| 50% – 65% | 4 |
| 65% – 80% | 2 |
| ≥ 80% | 0 |

**`ebit_interest_cover`** — higher is better (coverage)

| Value | Points |
|---|---|
| ≥ 20x | 10 |
| 10x – 20x | 8 |
| 5x – 10x | 6 |
| 2.5x – 5x | 4 |
| 1x – 2.5x | 2 |
| < 1x | 0 |

**`current_ratio`** — higher is better (liquidity)

| Value | Points |
|---|---|
| ≥ 2x | 10 |
| 1.5x – 2x | 8 |
| 1.2x – 1.5x | 6 |
| 1x – 1.2x | 4 |
| 0.8x – 1x | 2 |
| < 0.8x | 0 |

**`cash_to_current_liabilities`** — higher is better (liquidity)

| Value | Points |
|---|---|
| ≥ 0.75x | 10 |
| 0.5x – 0.75x | 8 |
| 0.35x – 0.5x | 6 |
| 0.2x – 0.35x | 4 |
| 0.1x – 0.2x | 2 |
| < 0.1x | 0 |

**`fcf_to_debt`** — higher is better (cash flow)

| Value | Points |
|---|---|
| ≥ 35% | 10 |
| 20% – 35% | 8 |
| 10% – 20% | 6 |
| 5% – 10% | 4 |
| 0% – 5% | 2 |
| < 0% | 0 |

**`fcf_margin`** — higher is better (cash flow)

| Value | Points |
|---|---|
| ≥ 15% | 10 |
| 10% – 15% | 8 |
| 6% – 10% | 6 |
| 3% – 6% | 4 |
| 0% – 3% | 2 |
| < 0% | 0 |

**`revenue_growth`** — higher is better (business performance)

| Value | Points |
|---|---|
| ≥ 10% | 10 |
| 5% – 10% | 8 |
| 0% – 5% | 6 |
| -3% – 0% | 4 |
| -10% – -3% | 2 |
| < -10% | 0 |

**`ebitda_margin_trend`** — scored from a trend verdict, not a value (D50)

| Verdict | Points |
|---|---|
| Improving | 10 |
| Stable | 6 |
| Deteriorating | 0 |

*10/6/0 rather than 10/5/0: a stable margin is a neutral fact, not a mild failure, and
5 of 10 reads as the latter.*

### The one band with distributional evidence behind it

`ebit_interest_cover` was re-edged from `[1, 2, 3, 5, 8]` to `[1, 2.5, 5, 10, 20]` on
measurement (D71). Across **640 observations from the 43 adopted companies**, the old top
band held **354 of 640 (55%)** while p90 sits at **38.9x** — above 8x the metric carried no
information, scoring a company covering interest 8x identically to one covering it 39x.
New occupancy `[23, 59, 112, 156, 143, 147]`, max share 24%.

**This is distributional evidence, not calibration.** It shows the band now discriminates
between companies; it does not show that the discrimination predicts anything. Moving the
top edge alone was insufficient — `[1, 2, 3, 5, 20]` still left 47% in one band — so the
intermediates moved with it.

## Missing data

This is where most of the model's design sits. Every refused metric carries a reason code,
every code has one **kind**, and the kind decides the treatment (D9, D41a, D45).

| Reason kind | Treatment | Effect on the category | Effect on the grade |
|---|---|---|---|
| **EVIDENCE** — we know, and it is bad | `evidence_zero` | scores **0**, counted | none directly |
| **GAP** — we do not know | `dropped_data_gap` | dropped from the mean | **caps** the grade |
| **NEITHER** — a good thing | `dropped_unlevered` | category dropped, weight redistributed pro rata | **no cap** |

The three-way split is what stops the model lying in either direction. A company with
negative EBITDA scores zero on leverage — that is a fact about the company. A company whose
filing never tags interest expense is *unknown*, not bad, so its coverage component is
dropped and the grade is capped instead. An unlevered company has no coverage ratio because
it has no debt; that is not a shortfall and must not cap anything.

A fifth treatment, `not_yet_implemented`, exists and is empty. It is the mechanism that
lets a future component join the row shape before it can be scored — treating an unbuilt
feature as a data gap would have capped every company in every period.

### The graduated cap

When whole categories are unavailable, `total_score` is rescaled over the categories that
did score, the output states "scored on N of 5", and the grade is capped by **how many
categories scored** (D46, `config: max_grade_by_categories_scored`):

| Categories scored | Grade capped at |
|---|---|
| ≤ 2 | 4 |
| 3–4 | 3 |
| 5 | uncapped |

A 2-of-5 score must not present with the same authority as a 4-of-5 one. A graduated cap
keeps every period scoreable while making the confidence difference visible **in the grade
itself**, rather than in a footnote a reader can skip. The cap line is generated by the
engine and travels with the grade everywhere it appears — CLI, evidence pack, stress output
(D57, D73b).

Capping is **systematic here, not exceptional**: 267 of 776 scored periods carry a cap.

### A period with an integrity failure scores nothing

If a period fails a fail-severity integrity check, an input is provably wrong — so every
metric refuses with `INTEGRITY_FAILED` (kind GAP), and the period gets no score row at all
(D45, D76). Not marked and included: an arithmetically impossible figure must not be
*reachable*.

## What this produces on real data

**Basis: the 43 adopted companies, capped grades, 776 scored periods, measured at commit
at commit `a5035a6` on 2026-09-20, after D78-D80.** Stated in full because the same
pipeline over the same filings
produced a different distribution three commits earlier, and a distribution without its
basis is a true statement that means something other than it appears to.

| Grade | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| Periods | 43 | 110 | 259 | 217 | 101 | 46 |

Single-peaked at grade 3, all six bands populated, 267 of 776 capped. Nothing about that
shape validates the model — it shows the bands discriminate, not that they discriminate
*correctly*.

## What is not calibrated, stated plainly

- **Every band edge.** `ebit_interest_cover` has distributional evidence (above); the rest
  are reasoned defaults from the methodology.
- **The category weights** 25/20/20/20/15.
- **The graduated cap thresholds** — why ≤2 caps at 4 rather than 5.
- **The trend points** 10/6/0.
- **The grade boundaries** 85/70/55/40/25.
- **Which nine of the seventeen metrics score at all.** Only `ebitda_interest_cover`'s
  exclusion has a recorded argument (D42d). The remaining seven were simply not in the
  methodology's category table, and no entry examines whether any of them should be.
- **The liquidity bands for negative-working-capital businesses** — the strongest open
  calibration item in the project. Two separate measurements point at it, and they are
  **not the same seven companies**, which is worth stating because both come to seven:
  - **Median `current_ratio` below the first band edge of 0.8**: 7 of 43 — RCL 0.21,
    CCL 0.29, CHTR 0.31, MAR 0.50, GIS 0.72, TXRH 0.74, PG 0.79 (D72a, measured at
    adoption).
  - **Zero liquidity points in the most recent scored period**: 7 of 43 — CHTR, GIS, MAR,
    PG, RCL, SBUX, WMT (measured at `a5035a6`, 2026-09-20). Five companies appear on both
    lists; CCL and TXRH only on the first, SBUX and WMT only on the second.

  Either way the effect is the same: these are negative-working-capital businesses that
  collect from customers before paying suppliers. **Procter & Gamble appearing on both
  lists is the clearest evidence that a sub-0.8 current ratio is not a distress marker in
  this universe** — it is a business model the bands do not model (D48, widened by D72a).

Nothing above was fitted to an outcome, because no outcome data exists here. Calibrating
any of it needs default, loss or rating data the project does not have and cannot buy at
£0 — which makes it a v2 question, recorded as such in `build-plan.md`.
