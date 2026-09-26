# Credit Risk Analyser

A deterministic credit-analysis engine over SEC XBRL data that computes seventeen credit
metrics, an explainable score and grade, trend classifications, early warnings and stress
scenarios for 43 US-listed non-financial companies — **and refuses to produce a number
whenever its inputs are missing, contradictory or ambiguous, with a recorded reason for
every refusal.** Every figure traces to a filing and an XBRL tag. Every scoring and
methodology choice is recorded with its evidence in a 76-entry decision log, including the
ones that turned out to be wrong and why. A manual AI workflow exports an evidence pack and
validates a drafted memo against it, with the validator's own limitations printed above its
results.

> The thresholds, weights and stress parameters are **documented project assumptions, not
> calibrated values** — the grades are an internal analytical scale, and nothing maps them
> to ratings, defaults or spreads.

That second paragraph is not boilerplate and should never be dropped when this project is
summarised. The engine's refusal behaviour is measured; its calibration is not, because the
project has no default, loss or rating data to calibrate against and cannot acquire any at
£0 cost. Everything below is written to keep those two facts distinguishable.

No LLM anywhere in the calculation path. Not a bank rating model, not a regulatory capital
model, not investment or credit advice.

## What the grades are, and what they are not

A grade is an integer 1–6 on an **internal analytical scale defined by this project**,
produced by summing weighted points across five categories — leverage 25, coverage 20,
liquidity 20, cash flow 20, business performance 15 — and reading the total against band
edges in `config/thresholds.yaml`.

**They are:**
- reproducible — the same filing and the same config always produce the same grade, and
  every run records the config fingerprints it used
- fully attributed — every grade decomposes to components, points, weights and the tag and
  filing each input came from
- honest about their own coverage — a grade computed on fewer than five categories is
  **capped** and says so, with the missing categories and their causes named on the same
  line

**They are not:**
- a credit rating, and are never mapped to an agency scale
- validated against any outcome — no default, loss, spread or rating data was used to set
  or check a single band edge
- comparable across config changes — a figure computed under different settings is a
  different measurement, which is why fingerprints travel with every result
- a portfolio-representative sample — the 43 companies are screened for **data adequacy**,
  not sampled for representativeness

## What it does

Nine stages, in the one order that is correct (`src/credit_risk/pipeline.py`):

| Stage | What it does |
|---|---|
| **select** | picks one fact per concept-period from companyfacts, by form, filing date and period type |
| **map** | resolves 46 XBRL tags to 34 internal concepts via `config/tag_map.yaml`, in rank order |
| **compose** | builds `total_debt`, `net_debt`, `ebitda`, `fcf` — refusing when components and aggregate disagree |
| **integrity** | 8 checks per period, 6 of them fail-severity; a fail-severity failure suppresses every metric for that period |
| **ratios** | 17 credit metrics, each with its formula, inputs and unit |
| **trends** | classifies each metric's direction over an eligible window |
| **warnings** | 11 early-warning indicators with severity and escalation |
| **score** | weighted points to a total, total to a grade, with a cap when coverage is short |
| **stress** | three scenarios with driver attribution, propagated deterministically |

Then, outside the engine, a manual AI workflow: **export** an evidence pack and
**validate** a memo written from it.

## Measured behaviour

**Basis for every figure below: the 43 adopted companies, capped grades, all periods of
each company's filing history, measured at commit `a5035a6` on 2026-09-20 (after D78-D80
fixed the five defects the golden set found).** Where a number is scoped to the larger
screened set, it says so.

The basis is stated because it is load-bearing rather than pedantic. The same pipeline over
the same filings has produced three different grade distributions in five commits:
**51/120/286/202/76/45** over 780 periods before D69 and D71, **38/98/273/221/98/48** after
them, and the figures below after D78-D80. None of the three is wrong — they answer the
same question at different commits, as a band rebase, a refusal rule and five engine fixes
landed. **A distribution quoted without its commit and its population is a true statement
that means something other than it appears to.**

| | |
|---|---|
| Companies screened end to end | **105** (43 adopted, a 41% pass rate) |
| Company-periods analysed | **792** (**777** with at least one computed metric) |
| Metric values computed | **10,975** |
| Metric values **refused** | **2,489** |
| Distinct reason codes with real witnesses | **15** on the adopted set |
| Periods scored | **776**, of which **267** carry a cap |
| Grade distribution 1→6 (capped grades) | **43 / 110 / 259 / 217 / 101 / 46** |
| Trend verdicts | **5,544** |
| Early warnings | **1,522** across **11** indicators |
| Stressable periods | **630**, each run under 3 scenarios (**1,890** runs) |
| Integrity check results | **6,336**, of which **4** are fail-severity failures |
| Tests | **936** — 892 pass, 44 skip by design. **17 of them are the golden set**: four company-years checked against the filing documents rather than against the engine |

The refusal count is the number worth looking at. `MISSING_INPUT` (2,419) and
`NO_CANDIDATE_TAG` (9,772 at the mapping layer) dominate, but the informative ones are
smaller and deliberate: **70** `COMPONENT_AGGREGATE_MISMATCH`, **141**
`LEASES_NOT_SEPARABLE`, **68** `INTEGRITY_FAILED`, **42** `ST_DEBT_SCOPE_UNCERTAIN` and
`LEASE_CONTAINMENT_UNVERIFIABLE` together, **13** `CANDIDATE_TAG_MISMATCH`. Each is a case
where a plausible number could have been produced and was not.

## Tested against real credit outcomes

The engine was run against **18 US non-financial filers that later filed Chapter 11**,
using only filings available at least 12 months before the petition — and compared, at the
same cutoff, against the 43 adopted companies as a survivor panel. Every event is sourced
from the filer's own 8-K under Item 1.03, with the petition date read from the document
text. Full basis, method and limits: `benchmark/results/a2_baseline.md`.

**The two findings that need no threshold, stated with their limits in the same breath:**

- **Failures ranked below survivors in 89% of failure-survivor pairs** (AUC 0.893 on the
  0–100 score; 0.882 computed on the grade, which is coarser). Dev 0.902, held-out 0.882.
  The figure was computed twice by independent derivations that agree — a pairwise count
  and the Mann-Whitney rank identity. **This is discrimination on 18 events. It is not
  calibration**, and nothing here maps a grade to a default rate, a spread or a loss.
- **All 18 of 18 failures scored below the median of their own survivor panel.** Median
  grade 5.5 against 3.0; median score 26.1 against 59.0; no failure graded 1, 2 or 3 at any
  cutoff. **18 is a small number and the events are not independent of each other** — 11 of
  the 18 are 2020.

Lead times from the scored period end to the petition run **14 to 26 months** (median 18),
all at or beyond the 12-month minimum. The spread comes from fiscal calendars not lining up
with petition dates; longer lead makes the test harder, so it biases against the engine —
but "a 12-month horizon" would misdescribe what was measured.

**The cohort cannot reach the 2008–09 credit cycle.** Measured: Charter's companyfacts
begins 2011-05-03, so a 2008 cutoff yields zero facts — XBRL did not exist. Every event
therefore falls in 2019–2023, and the cohort is confined to two shocks: COVID and the
2022–23 rate rise. It is 8 retail/consumer, 5 energy, 3 transport/industrial, 2 telecom,
which reflects which sectors actually defaulted rather than any sampling choice.

**On a `grade >= 5` flag rule** — frozen before the run, chosen on band semantics rather
than from the trade-off table (D82) — sensitivity is **78% (14/18)** at a **21%**
false-positive rate per survivor company-cutoff. That second figure needs its denominator
read carefully:

| | value | what it counts |
|---|---|---|
| false positives per company-cutoff | **21%** (166/774) | 43 survivors × 18 admitted cutoffs |
| **distinct survivor companies flagged ≥ once** | **21/43 = 49%** | how many real businesses the rule would surface |

**The 774 and 817 observation counts come from 43 distinct companies, so the precision of
any rate here is governed by 43 and 18 — not by the pair count.** A company weak at one
cutoff is usually weak at the next, so these are pseudo-replicated observations and the
pooled 21% reads far more precise than it is. Both figures describe the same rule. (817 is
19 cutoffs × 43 over all verified cases; 774 is 18 × 43 after Hertz leaves the
discrimination set, and its cutoff is shared with no other case.)

### The engine is blind to Hertz, and the grade does not say so

`total_debt` refuses with `NO_DEBT_DATA` for one of 2020's most leveraged filers. No
`ebit`, `cash`, `current_assets` or `current_liabilities` concept resolves either. Hertz's
securitised fleet debt sits in **dimensioned contexts the companyfacts endpoint does not
return**, behind an **unclassified balance sheet** with no current/non-current split.
**This recurs D25's Ford finding on a second company.**

The absence is not the serious part. Hertz's grade 4 rests on a **single computed number** —
revenue grew 8% — which gives business performance 8/10, rescales to 80.0, and caps from an
uncapped grade 2 down to 4. So sixteen months before Chapter 11 the engine rates Hertz
**better than every failure it could actually see**, all of which sit at grade 5 or 6.

The architectural point: **the graduated cap is a ceiling, never a floor, so the system
cannot express "we know nothing about this borrower."** It can only decline to call such a
borrower strong. A credit analyst in that position records no opinion; this engine records a
mid-scale grade. Hertz is reported as a coverage failure in its own row rather than counted
as a miss — counting it would blame the ranking for a coverage defect, and hiding it would
overstate coverage.

### Escalated warnings are close to decorative

| | failures | survivor company-cutoffs |
|---|---|---|
| ≥ 1 escalated warning | 50% | 37% |
| ≥ 1 High-severity warning | 72% | 45% |

**Thirteen points of separation on escalation is close to none.** D72b parked the escalation
threshold on the stated grounds that firing in 31% of periods "feels high" with no evidence
base for changing it. **That justification no longer holds — this is the evidence base.**
What it shows is stronger than a threshold question: the escalated-warning layer barely
distinguishes companies that failed from companies that did not. It does not identify a
better threshold, and none is claimed here.

### What the four misses and the false positives actually show

The rule misses four failures, all at grade 4: **Tailored Brands, Whiting Petroleum,
Denbury, Extraction Oil & Gas**. Their scores put them below most survivors (percentiles
0.22–0.40 of their panels), just not below a band edge. **None of the four raised a single
warning of any kind** — no escalated warning, no High-severity warning — which is the more
serious half: the trend and warning layer contributed nothing precisely where the grade fell
short.

**Three of the four are oil and gas assessed on FY2018 financials, and they failed in the
March–April 2020 commodity collapse.** That is partly a limit on what financial-statement
analysis can see at all: a 2018 balance sheet cannot contain a future price shock, and no
ratio computed from it will. The honest reading is that the engine ranked them below their
peers and did not rank them as distressed, and that a materially better answer would have
required information the filings do not carry.

The flagged survivors read the same way. They are dominated by travel, leisure and gaming —
CCL, RCL, MAR, MGM, LVS, WYNN, PENN, CZR, HLT — flagged largely at COVID-era cutoffs. **A
cruise operator or a casino in 2020 genuinely did look like a default candidate on its
financials.** Those are defensible on their own facts rather than arbitrary, which also
means the false-positive rate is period-dependent and would differ in a calmer window.

## What is validated against real data, and what is not

**Validated on real filings:** ingestion and normalisation for arbitrary US filers; the 17
metrics with full provenance; refusal behaviour across 14 witnessed reason codes; scoring
and the attributed cap; trends and warnings; stress with driver attribution; a known class
of tagging error caught two independent ways (a 90% revenue disagreement between two tags,
and a single-tag error caught by an EBITDA-margin plausibility check); the evidence pack
and memo validator.

**Exercised by fixtures only** — real, but no adopted company reaches them: five of the six
fail-severity integrity checks (`current_assets_subset`, `current_liabilities_subset`,
`cash_subset`, `debt_subset`, `revenue_non_negative`) ran hundreds of times each and never
failed; `NO_DEBT`, `ZERO_DENOMINATOR`, `NEGATIVE_DENOMINATOR`, `NO_INTEREST_NO_DEBT`; the
operating-leverage EBITDA mode; `new_debt_rate` resolution, since every preset carries
`additional_debt: 0` by design.

**Assumptions, not validated behaviour:** every band edge, every category weight, the
graduated grade cap, every stress parameter (`fixed_cost_share` 0.3, `floating_share` 1.0 —
forced, because the fixed/floating split is unreachable from XBRL — `default_tax_rate` 0.21,
`new_debt_rate_default` 0.06, and the preset shock magnitudes), the trend materiality
thresholds, and the liquidity bands for negative-working-capital businesses — 7 of the 43
companies (CHTR, GIS, MAR, PG, RCL, SBUX, WMT) score **zero** liquidity points in their most
recent scored period, re-measured at `a5035a6`. That is a business model the bands do not
model, not a finding about those companies. See `docs/risk-scoring.md`, which also records
D72a's separate seven — a different set, on a different measurement.

**936 tests is not 936 units of real-world validation.** Most assert engine behaviour
against hand-computed or fixture data. The real-data assertions are narrower, and they are
the ones that carry the claims above. The 44 skips are not gaps: they are tests
parameterised over the five fixture companies that apply to one of them and skip for the
other four — a witness-specific assertion, not an unrun one.

## The AI workflow, and what the validator cannot do

AI is used **manually and outside the engine** (`docs/ai-governance.md`). The engine exports
an evidence pack — the complete and exclusive basis for a memo, carrying every figure, its
source tag, its filing URL, the assumption register, the stress duties and an explicit list
of what the pack does *not* contain. A drafted memo is then validated against that pack.

The validator checks that every figure in the memo **appears** in the pack, at the memo's
own stated precision, and that the memo claims no grade other than the pack's. It prints its
own limitations above every result, because:

- **a figure cited under the wrong label passes** — it reads numbers, not labels
- **true figures assembled into a false claim pass** — it reads numbers, not arguments
- **a fabricated source passes** — no numeric check catches it

A clean validation is not a clean memo. A human still has to read it.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env               # then put your real name and email in it
```

The SEC requires a User-Agent header identifying you on every request; requests without one
are blocked. That is what `.env` is for. There are no other credentials, and no paid
services — the project runs at £0.

```bash
pytest                             # 892 passed, 44 skipped
credit-risk version
```

## Using it

```bash
credit-risk fetch AZO                              # cache companyfacts to data/raw/
credit-risk metrics AZO --all-periods              # every ratio, with its provenance chain
credit-risk score AZO --period 2023-08-26          # grade, cap line first, fully decomposed
credit-risk stress AZO --scenario severe --grid    # base vs stressed, with driver attribution
credit-risk export-evidence AZO --out evidence     # the pack a memo must be written from
credit-risk validate-memo memo.md evidence/AZO_2023-08-26.md
```

`fetch` is the only command that touches the network. Everything else runs from the cache,
so the whole engine works offline once a company is cached.

## Where things are

| Path | What it is |
|---|---|
| `DECISIONS.md` | 76 decisions with evidence, alternatives and consequences — the most useful file here |
| `CLAUDE.md` | Project rules: 13 non-negotiables and 14 working rules, several of them earned the hard way and carrying the finding that produced them |
| `docs/case-study.md` | The write-up — readable without opening the repo |
| `docs/architecture.md` | How it fits together, and where each kind of decision lives |
| `docs/risk-scoring.md` | Bands, weights, missing-data treatments, the graduated cap |
| `docs/credit-methodology.md` | Every formula, threshold and edge case |
| `docs/data-sources.md` | Where the data comes from and how facts are selected |
| `docs/ai-governance.md` | Where AI is and is not allowed |
| `docs/interview-notes.md` | Per-component notes, including what went wrong and why |
| `docs/audits/` | Point-in-time audits; corrections appended, never rewritten |
| `config/*.yaml` | Thresholds, weights, stress presets, XBRL tag map |
| `src/credit_risk/pipeline.py` | The nine stages in their one correct order |
| `PROJECT_STATE.md` / `TODO.md` | Where the build has got to, and what is next |

## Status

**v1 complete.** All eleven phases are built, run on real data and are committed:
ingestion, normalisation, composites, integrity checks, ratios, scoring, trends and
warnings, stress, the evidence export with its memo validator, and the documentation set.

Deliberately not built in v1: any web or graphical interface, a database beyond SQLite, any
paid data source, and any runtime AI. Those are v2 questions and are recorded as such in
`docs/build-plan.md`.

The three parked calibration items — the warning escalation threshold, sector-specific
thresholds, and the four never-firing integrity checks — are documented with their evidence
in the v1 final audit. Sector thresholds are the item to take up first if the universe
grows: it began as one company and is now three independent instances.
