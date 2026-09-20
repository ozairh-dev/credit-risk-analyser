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
| Tests | **930** — 886 pass, 44 skip by design. **17 of them are the golden set**: four company-years checked against the filing documents rather than against the engine |

The refusal count is the number worth looking at. `MISSING_INPUT` (2,419) and
`NO_CANDIDATE_TAG` (9,772 at the mapping layer) dominate, but the informative ones are
smaller and deliberate: **70** `COMPONENT_AGGREGATE_MISMATCH`, **141**
`LEASES_NOT_SEPARABLE`, **68** `INTEGRITY_FAILED`, **42** `ST_DEBT_SCOPE_UNCERTAIN` and
`LEASE_CONTAINMENT_UNVERIFIABLE` together, **13** `CANDIDATE_TAG_MISMATCH`. Each is a case
where a plausible number could have been produced and was not.

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

**930 tests is not 930 units of real-world validation.** Most assert engine behaviour
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
pytest                             # 886 passed, 44 skipped
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
