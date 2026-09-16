# Phase 10 demonstration run

**Scope:** the full pipeline over all **43 adopted demonstration companies** (D65), every
period. First time the engine has been exercised at scale — everything demonstrated before
this rested on CCL alone.

**Measurement and reporting only.** No code, config or band changes. Nothing committed.

**State:** `0fa0897`, 816 tests passing. **780 scored company-periods** across 43 companies.

---

## 1. The aggregate picture

### Grade distribution

| Grade | As shown | % | Uncapped basis |
|---|---|---|---|
| 1 Very strong | 51 | 6.5% | 91 |
| 2 Strong | 120 | 15.4% | 186 |
| 3 Moderate | **286** | **36.7%** | 212 |
| 4 Elevated | 202 | 25.9% | 170 |
| 5 High risk | 76 | 9.7% | 76 |
| 6 Very high risk | 45 | 5.8% | 45 |

**The shape is a plausible single-peaked distribution centred on grades 3–4**, with thin
tails at both ends — what a set of large, established US corporates should produce. Crucially
it is **not** the degenerate one-or-two-grade clustering that would indicate non-discriminating
bands. The engine separates its universe.

The capped-versus-uncapped columns differ materially: on an uncapped basis grades 1–2 would
hold **277 periods (36%)** rather than 171 (22%). The cap is doing substantial work, and
D57's visibility requirement is what keeps that from being invisible.

### Caps

**475 of 780 periods (61%) score uncapped** — against **13 of 85** under the old five-company
set. That is the universe adoption paying off directly.

- **305 capped (39%)**, of which **118 binding** — i.e. 187 caps change nothing because the
  score was already at or below the cap.
- **Every cap is `data_gap` caused** (467 absent-category instances). Not one arises from
  `unlevered` or `not_yet_implemented`.
- Absent categories, in order: leverage 118, cash_flow 110, business_performance 101,
  coverage 95, liquidity 43.
- N distribution: N=5 → 475, N=4 → 211, N=3 → 45, N=2 → 30, N=1 → 19.

D46's graduated cap is therefore active on **49 periods** (N ≤ 2) that would previously have
presented at grade 3 with the authority of a 4-of-5 score.

### Integrity

**Zero integrity FAIL periods across all 780.** No company was excluded from scoring.

This is worth stating as a finding rather than a clean bill of health: the four fail-severity
checks (`current_assets_subset`, `current_liabilities_subset`, `cash_subset`, `debt_subset`)
did not fire once in 780 periods of real filings. Either large US filers genuinely never
violate these identities — plausible, since they are accounting tautologies a filer would have
to mis-tag to break — or the checks are positioned where violations cannot reach them. The
pre-Task-9 audit's observation that these paths are **synthetic-only** now holds at 780
periods rather than 87.

### Warnings

**1,539 warnings.**

| Indicator | Count | | Indicator | Count |
|---|---|---|---|---|
| revenue_deterioration | 259 | | negative_equity | 110 |
| debt_increase | 223 | | coverage_below_2x | 64 |
| liquidity_deterioration | 207 | | negative_fcf | 43 |
| coverage_deterioration | 186 | | negative_ebitda | 27 |
| margin_deterioration | 153 | | | |
| cash_flow_deterioration | 147 | | | |
| leverage_deterioration | 120 | | | |

**Escalation fires in 245 of 780 company-periods (31%), escalating 989 of 1,539 warnings
(64%).** That is a high rate for a mechanism meant to mark exceptional periods, and it is a
calibration question rather than a defect: at a threshold of 3, and with seven
trend-deterioration indicators able to fire together, three-at-once is common. Reported, not
changed.

### Trends

**5,544 verdicts**: INSUFFICIENT_DATA 1,764 (32%), Stable 1,344, Deteriorating 1,295,
Improving 1,141. Improving and Deteriorating are near-balanced (1,141 vs 1,295), which is what
a long-horizon sample of surviving large caps should look like — no systematic directional bias
in the classifier.

---

## 2. The four demonstration cases, by measurement

### Strong borrower — **SYK (Stryker)**

| | |
|---|---|
| Mean grade | **1.84** — 84% of periods at grade 1–2 |
| Median leverage | **1.28x** net debt / EBITDA |
| Median coverage | **10.2x** EBIT / interest |
| Uncapped | **17 of 19 periods** |

Chosen over FAST (mean 1.79) deliberately: FAST's coverage median is **125.5x** and its
leverage 0.16x, which makes it a *debt-free* company rather than a strong *borrower* — it
demonstrates the top band but not credit analysis. SYK carries real debt at comfortable
multiples across 19 periods, which is the case the methodology describes. COST and CMI are
credible alternates but both run net-cash medians (−0.31x, −0.35x).

### Deteriorating borrower — **LYB (LyondellBasell)**

| | |
|---|---|
| Window | 2013-12 → 2025-12, **13 consecutive periods** |
| Score | **−62.5 points**, grade **1 → 5** |
| Leverage | **0.23x → 7.70x** |
| EBITDA margin | **13.9% → 3.2%** |
| Deterioration warnings | **36** |

The clearest sustained decline in the set, and it satisfies the specification exactly:
declining margins *and* rising leverage over consecutive periods, visible in both trends and
warnings. Alternates: SBUX 2015–2020 (−57.5, grade 1→5, leverage 0.16→6.73x — the buyback-
driven story), MGM 2011–2015 (−48.8, 3→6), YUM 2017–2022 (−45.0, 1→4).

### Highly leveraged borrower — **CHTR (Charter Communications)**

| | |
|---|---|
| Mean grade | **5.31** — 81% of periods at grade 5–6 |
| Median leverage | **4.69x** |
| Median coverage | **1.1x** — barely covering interest |
| Warnings | 26 |

CZR is the alternate (mean 5.00, 79% at 5–6, median leverage **6.75x**, coverage 1.0x) and is
arguably the more extreme case; CHTR wins on consistency — it sits in the 5–6 band across
nearly its whole history rather than spiking there.

### Resilient borrower — **CHTR again, and that is a finding**

| | |
|---|---|
| Weak base periods (grade ≥ 4) | 16 |
| Holding grade under Severe | **14 of 16** |
| Mean grade move under Severe | **+0.12** |
| Score | 30.8 → 27.2 |

**The same company is both the most leveraged and the most resilient**, which is not a
contradiction but is worth understanding: CHTR is already at grades 5–6, so there is almost
nowhere further to fall. Its "resilience" is **floor effect, not strength.**

**On the specification's own terms — "weak-looking at base but survives Severe without
collapsing" — the best genuine candidate is TXRH (Texas Roadhouse):** 5 of 6 weak periods
hold, mean move +0.17, and the score barely moves (54.5 → 52.4) from a base that is weak
without being saturated. WBD is a close second (7/8 hold, 48.5 → 43.9).

**Stated plainly as a finding:** the resilient-borrower case is the weakest of the four in
this universe. The set contains plenty of companies that are strong, plenty that are
leveraged, and a clear deteriorator — but "weak at base, robust under stress" is rare, and
the obvious candidates by score are companies whose grades cannot fall further. That is a
property of the universe, not of the engine.

---

## 3. Band calibration — real distribution, first time

**Do not change the bands on this report.** Calibration is a decision.

| Metric | n | p10 | median | p90 | Band occupancy |
|---|---|---|---|---|---|
| net_debt_to_ebitda | 547 | −0.19 | 1.76 | 5.69 | [175, 128, 75, 53, 42, 74] |
| **ebit_interest_cover** | 640 | 2.04 | 9.09 | 38.94 | **[23, 41, 42, 88, 92, 354]** |
| debt_to_capital | 658 | 0.22 | 0.52 | 1.19 | [61, 94, 149, 140, 72, 142] |
| current_ratio | 737 | 0.63 | 1.20 | 2.47 | [143, 116, 111, 128, 124, 115] |
| cash_to_current_liabilities | 705 | 0.06 | 0.32 | 0.96 | [118, 108, 140, 109, 109, 121] |
| fcf_to_debt | 579 | 0.03 | 0.23 | 1.07 | [35, 42, 53, 128, 128, 193] |
| fcf_margin | 630 | 0.02 | 0.09 | 0.20 | [37, 85, 91, 136, 128, 153] |
| revenue_growth | 679 | −0.08 | 0.06 | 0.26 | [60, 52, 40, 148, 160, 219] |

### Finding: `ebit_interest_cover`'s top band absorbs 55% of observations

**354 of 640 periods (55%) land in the ≥ 8.0x top band**, which scores 10 points. The
distribution's p90 is **38.9x** — nearly five times the top edge. Inside that band the metric
carries **no information**: a company covering interest 8x and one covering it 39x score
identically.

This is the one clear mis-set edge in the set. The bands discriminate well in the 0–8x range
(23/41/42/88/92 across five buckets) and then stop. If coverage is meant to separate strong
credits from very strong ones, the top edge is in the wrong place for a large-cap universe —
a 15x or 20x edge would restore discrimination among the 354.

Three other bands are mildly top-heavy — `fcf_to_debt` 33%, `revenue_growth` 32%,
`debt_to_capital` 22% in the bottom bucket — but all retain populated intermediate bands.
**No band is empty anywhere.**

### Finding: D48's liquidity effect generalises well beyond cruise

D48 recorded CCL scoring **0 liquidity points in every good year** because cruise operators
carry deferred ticket revenue in current liabilities, and filed it as a sector effect.

**Measured across the universe: 7 of 43 companies (16%) have a median `current_ratio` below
the first band edge of 0.8**, and therefore score zero liquidity points in a typical year:

| Company | Median current_ratio | Sector |
|---|---|---|
| RCL | 0.21 | cruise |
| CCL | 0.29 | cruise |
| CHTR | 0.31 | cable |
| MAR | 0.50 | hotels |
| GIS | 0.72 | packaged food |
| TXRH | 0.74 | restaurants |
| PG | 0.79 | household products |

**This is broader than deferred ticket revenue.** It spans cable, hotels, restaurants,
packaged food and household products — business models that run negative working capital by
design, collecting from customers before paying suppliers. **Procter & Gamble is on this
list**, which is the clearest possible signal that a sub-0.8 current ratio is not a distress
marker in a large-cap universe.

D48's framing should be widened: this is not a cruise-sector quirk but a **negative-working-
capital business-model effect**, and the liquidity bands are calibrated for a working-capital-
intensive manufacturer. Still a decision, not a fix.

### Metrics where banding adds little

None are degenerate. `net_debt_to_ebitda` is the healthiest spread (175/128/75/53/42/74 with
a genuine tail), and `current_ratio` and `cash_to_current_liabilities` are close to uniform
across all six bands — unusually good discrimination.

---

## 4. Stress at scale

**647 stress runs per scenario** across the stressable subset.

| Scenario | Mean grade move | Distribution |
|---|---|---|
| base | **+0.02** | −2: 6, −1: 30, **0: 559**, +1: 52 |
| moderate | **+0.43** | −2: 3, −1: 14, 0: 364, +1: 243, +2: 17, +3: 6 |
| severe | **+0.87** | −2: 2, −1: 8, 0: 236, +1: 271, +2: 87, +3: 43 |

**The central result is economically sensible.** Severe moves 401 of 647 periods (62%) to a
worse grade, Moderate moves 266 (41%), and the severity ordering holds everywhere — Severe is
never kinder than Moderate. A mean of +0.87 grades under a −20% revenue, −5pp margin, +200bps
scenario is a credible magnitude: painful, not catastrophic, for large established borrowers.

### Driver attribution

| Scenario | Metric | Dominant shock | Second | Third |
|---|---|---|---|---|
| moderate | net_debt_to_ebitda | **margin 1.073** | revenue 0.314 | rate **0.000** |
| moderate | ebit_interest_cover | **rate 3.892** | margin 3.095 | revenue 2.025 |
| severe | net_debt_to_ebitda | **margin 2.845** | revenue 0.706 | rate **0.000** |
| severe | ebit_interest_cover | **rate 6.036** | margin 5.324 | revenue 4.081 |

Clean and interpretable: **margin shock dominates leverage, rate shock dominates coverage**,
and the rate shock moves leverage by **exactly zero** — the isolation invariant holding across
647 real runs, not just the synthetic test.

---

## 5. What looks wrong

### 5.1 Impossible EBITDA margins — a flagged-then-used defect (D26's shape, in revenue)

**GIS reports EBITDA margins up to 203.4% across 6 periods; CAG up to 124.3% across 4.** An
EBITDA margin above 100% is arithmetically impossible for an operating company.

Root cause, traced:

```
GIS 2024-05-26:  revenue  2,037,800,000   tag=Revenues
                 ebit     3,431,700,000   tag=OperatingIncomeLoss
                 ebitda   3,984,400,000   -> margin 195.5%
GIS 2025-05-25:  revenue 19,486,600,000   tag=RevenueFromContractWithCustomerExcludingAssessedTax
```

`Revenues` — **first priority in `tag_map.yaml`** — resolves to ~2.0bn for General Mills,
whose actual revenue is ~19.5bn. The correct figure sits under the second-priority tag. In the
adjacent year the first tag is absent and the second resolves correctly, which is why the
margin snaps from 195.5% to 19.7%.

**The engine noticed.** D17's `CANDIDATE_TAG_DISAGREEMENT` fired **6 times** for GIS revenue,
recording exactly this conflict. The metric computed from the higher-priority tag anyway.

**This is precisely the shape D26 rejected for debt**: *"the old rule flagged a number as
suspect and then used it anyway... a plausible-looking wrong number stamped with full
provenance."* D26 replaced compute-and-flag with refuse-to-compute for the components-versus-
aggregate case. **Revenue has the same exposure and still uses compute-and-flag.**

Severity: 10 impossible-margin periods across 2 of 43 companies. Small in count, but the
failure mode is the one CLAUDE.md rule 9 exists to prevent, and no integrity check catches it
— there is no plausibility check on a margin.

**Smallest fix (not applied):** an integrity check asserting `ebitda_margin ≤ 1.0`, or extend
D26's refuse-on-disagreement rule to revenue when candidate tags differ beyond a tolerance.
Either is a decision.

### 5.2 D64's CFO approximation flips grades at scale — including under zero shock

D64 recorded that the base scenario is not a no-op for cash-flow metrics, measured at a
median 59% gap on five companies. **At scale it is larger than that framing suggests.**

**88 of 647 base runs (14%) show a different grade at zero shock** — 52 worse, 36 better. The
base scenario applies no shocks at all; every one of these 88 grade changes is the CFO
approximation (`ebitda − interest − tax` with working capital flat) disagreeing with the base
composite's reported-CFO figure.

Worse, it propagates into the stressed results:

**10 runs show a company's grade IMPROVING under Severe stress**, including **BKNG 2013 and
2014 improving by two full grades (3 → 1)** under a −20% revenue, −5pp margin, +200bps
scenario. That is not economically possible; it is the approximation gap running in the
favourable direction and overwhelming the shock.

**Why it matters more than D64 implied:** a base-versus-stressed comparison is the product's
headline output. If 14% of them contain a grade change caused by a modelling artefact rather
than a scenario, the comparison is not reliable at the grade level for those periods. D64
correctly identified the cause and judged it acceptable; **at 43 companies the frequency
argues for revisiting that judgement.**

**Smallest fix (not applied):** either seed stressed CFO from reported CFO and adjust it (D64
rejected this, reasonably, as importing a real number into a hypothetical), or suppress the
FCF-derived metrics from the stressed grade and state that the stressed grade covers leverage,
coverage and margin only. The second is more honest and does not fabricate anything.

### 5.3 Escalation fires in nearly a third of all periods

**245 of 780 company-periods (31%) trigger escalation**, raising **989 of 1,539 warnings
(64%)** one severity level. A mechanism intended to mark periods of unusual concentration is
firing on roughly one period in three.

Not a defect — the rule is implemented exactly as specified — but at a threshold of 3, with
seven trend-deterioration indicators that can fire together, the bar is low. Rule 12's
principle applies: *a signal that fires constantly is indistinguishable from no signal.*

### 5.4 Zero integrity FAILs in 780 periods

Reported above; restated here because it belongs on this list. The four fail-severity checks
never fire on real data. They may be correct and simply never violated by large filers, but
after 780 periods the honest description is that **they remain unvalidated against real
violations**, and the suite's confidence in them rests entirely on synthetic fixtures.

### 5.5 Sanity checks that passed

Spot-checked against what the market plainly thought at the time, and the engine agrees:
CHTR at grades 5–6 through its leveraged-rollup years; MGM and CZR deteriorating sharply into
2015 and 2020; SBUX's 2015–2020 decline tracking its debt-funded buyback programme; BKNG's
single grade-6 year in 2020 (revenue −54.9%). **No grade was found that contradicts the
obvious contemporaneous view of the company.**

---

## Verdict

**The engine works at scale.** The grade distribution is well-shaped and discriminating, the
stress results are economically sensible with clean driver attribution, and no grade
contradicts the contemporaneous market view of its company. 61% of periods now score uncapped
against 15% under the old five-company set.

**Three things need a decision before this output is shown to anyone as a credit view:**

1. **The revenue tag-priority defect (5.1)** — the only finding that produces a
   *plausible-looking wrong number*, which is the category rule 9 forbids outright.
2. **D64's approximation gap (5.2)** — 14% of base runs and 10 grade *improvements* under
   Severe stress. The base-versus-stressed comparison is the headline output.
3. **`ebit_interest_cover`'s top band (3)** — 55% of observations in one band is a live
   calibration issue, now evidenced rather than suspected.

The liquidity finding (3) and the escalation rate (5.3) are calibration questions worth
recording but not blocking.
