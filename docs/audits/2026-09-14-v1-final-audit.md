# v1 final audit

**Scope:** Phases 6–9, the universe adoption, the demonstration run and its three fixes,
and decisions **D43–D74**. The Tasks 1–8 and Phases 5 baselines are assumed sound — both
had prior audits whose findings were cleared.

**Second purpose:** establishing what can honestly be claimed before the project is
described to other people.

**Report only.** Nothing changed, nothing committed.

**State audited:** `41fcd1b`, 844 passing / 45 skipped, working tree clean. Evidence base:
43 adopted companies, **781 company-periods**†, 780 scored†, 647 stressable†.

---

> ### † Correction appended 2026-09-20 — the evidence base predates D69 and D71
>
> **The figures in this audit are left exactly as written.** They were accurate for the
> state they were measured at; the error is that the state is not the one the header
> names. This note records the discrepancy rather than editing the report around it.
>
> The four evidence-base figures below — and the grade distribution in §"What can honestly
> be claimed" — were **carried forward from the 2026-09-13 demonstration run at `0fa0897`**,
> which is *before* commit `8828aef` (D69–D72). The header says `41fcd1b`, which is after
> it. Every figure was reproduced exactly at `0fa0897` on 2026-09-20 by re-running the
> pipeline in a worktree at that commit, so the attribution is measured, not inferred:
>
> | Figure | As printed (`0fa0897`) | Current (`ce0fc56`) | What moved it |
> |---|---|---|---|
> | company-periods with ≥1 computed metric | **781** | **777** | D76 — CAG's 4 integrity-FAIL periods now compute nothing |
> | scored periods | **780** | **776** | D69 — the same 4 periods now FAIL a fail-severity check, and D45 excludes a FAIL period from scoring |
> | stressable periods | **647** | **630** | D69 — revenue refuse-on-disagreement means revenue and EBITDA no longer co-resolve in 17 periods |
> | capped grade distribution 1→6 | **51/120/286/202/76/45** | **38/98/273/221/98/48** | D71 — the coverage-band rebase moves **114** periods, every one by exactly one grade worse |
>
> **D75 and D76 changed no grade at all**: the distribution measured at `8828aef` is
> identical to the one at `ce0fc56`.
>
> **This audit's own finding 5 is the finding it fell to.** Finding 5 says a decision's
> recorded measurement can go stale while its reasoning stays sound, and recommends
> treating in-sample counts as provisional. The audit then reported a carried-forward
> evidence base under a newer commit hash. The rule that prevents it is the one D32's
> status note now states: **a count is only meaningful with its population and its commit
> attached.**

---

## BLOCKERS

### 1. The stress engine computes metrics the base engine refused
**HIGH · makes base and stressed grades incomparable, which is the product's headline output**

**What:** `stress/engine.py::stressed_metrics` applies weaker availability gates than
`metrics/ratios.py`. Where the base pipeline **refuses** a metric, the stress engine
computes one anyway from propagated values. Measured at **zero shock** across the adopted
universe:

| Metric | Occurrences | Base refusal it overrode |
|---|---|---|
| `fcf_to_debt` | 55 | `MISSING_INPUT:fcf` |
| `fcf_margin` | 55 | `MISSING_INPUT:fcf` |
| `ebit_interest_cover` | 4 | `INTEREST_MISSING_WITH_DEBT` |
| `ebitda_interest_cover` | 4 | `INTEREST_MISSING_WITH_DEBT` |
| **Total** | **118** | |

**How found:** verifying D70 independently. One base run still changed grade (AZO
2011-08-27, 4 → 5); the changed metrics were the two D70 excludes, which should have made
a grade move impossible. Tracing it showed the cause was not FCF at all — AZO's
`ebit_interest_cover` is `UNAVAILABLE` at base and `CALCULATED` under stress, so the
**coverage category is absent at base and present under stress**. The base score is capped
on 4 categories; the stressed score is uncapped on 5.

**Why it matters:** this is the same class of defect D70 fixed, arriving from a different
direction. A stressed grade computed on a category the base grade could not score is not
comparable with it, and base-vs-stressed comparison is what the stress output exists for.
The 110 FCF cases are contained by D70's exclusion from the grade — but **they still appear
in the stress results table and therefore in the evidence pack**, where a model may quote a
figure the base engine refused to produce.

**Smallest fix:** `stressed_metrics` inherits the base refusal — if the base metric is
`UNAVAILABLE`, the stressed one is too, carrying the same reason code. The stress engine
should not be able to manufacture availability.

### 2. `export/evidence.py` has no test at all
**HIGH · 0% coverage on the artefact the entire AI workflow depends on**

**What:** 96 statements, **zero executed by the suite**. The validator was tested heavily
(91%, 28 tests, a five-violation reality test) but the exporter that produces the pack it
validates against has no assertion of any kind.

**How found:** branch coverage over the newer modules.

**Why it matters:** the pack is the *exclusive* input to the manual AI workflow. A silent
error in it — a section dropped, a filing URL malformed, the cap line omitted, the stress
duties missing — would be invisible, and would propagate into every memo written from it.
D73 records five distinct duties the pack must carry; **not one is asserted**. The
five-violation test exercised the exporter incidentally by generating a real pack, but
that test asserts nothing about the pack's contents.

**Smallest fix:** one test per D73 duty — the cap line present, the five stress
assumptions present, a derived filing URL per REPORTED row, the register populated from
config, the "does not contain" boundary present — plus one asserting the pack contains no
`None`/`nan` artefacts.

---

## NON-BLOCKERS

### 3. CAG's impossible EBITDA margins still reach the evidence pack
**MEDIUM**

**What:** D69's integrity check correctly FAILs CAG's 4 periods and excludes them from
scoring. But the **metric is still computed and stored** at 122.5%–124.3%, and the evidence
pack for those periods carries it:

```
| ebitda_margin | 1.2250 | ebitda / revenue | ebitda, revenue | — |
| ebitda_margin_plausible | FAIL | ebitda=1,960,000,000 exceeds revenue=1,600,000,000 ... |
```

**Why it matters:** the pack carries the FAIL alongside, so the evidence is complete and a
careful reader sees both. But **the validator would verify a memo citing "122.5%"** — the
figure genuinely appears in the pack. An arithmetically impossible number is reachable
through a clean validation.

**How found:** independently verifying D69 rather than trusting the fix report, which said
"impossible margins remaining: 0" — true for GIS, not for CAG.

**Smallest fix:** either suppress metrics for a period that FAILs a fail-severity integrity
check, or mark them in the pack as `FAILED_INTEGRITY` so the validator can refuse them.
The second preserves the evidence; the first is cleaner. A decision either way.

### 4. Reason codes and checks still without real witnesses
**MEDIUM · unchanged in kind, sharpened by scale**

Across 43 companies and 781 periods, **18 reason codes now have real witnesses**, including
several previously synthetic-only. Still unwitnessed in the adopted set:

| Code | Status |
|---|---|
| `NO_DEBT` | Witnessed only by QCOM, a **fixture**, not an adopted company |
| `ZERO_DENOMINATOR` | No real witness |
| `NEGATIVE_DENOMINATOR` | No real witness |
| `NO_INTEREST_NO_DEBT` | No real witness |
| `AMBIGUOUS_FYE`, `FYE_TIE`, `NO_FYE_ANCHOR` | No real witness |

And the **fail-severity integrity checks**: only `ebitda_margin_plausible` has ever failed
(4 times). The other five ran between 287 and 737 times each and **never failed once**.

**Notable change:** `debt_subset` went from 21 runnable periods to **287** after the
universe adoption — a 13× increase in exposure — and still never fails. That materially
strengthens the D72c finding rather than weakening it: it is not that the check lacked
opportunity.

### 5. D32's characterisation is now outdated
**LOW · decision drift of a kind the sweep does not catch**

D32 records `ST_DEBT_SCOPE_UNCERTAIN` as firing "**zero times on the five cached
companies** — a latent-hole guard in the D29 mould". Measured across the adopted universe:
it now fires **18 times**. The decision's reasoning is unaffected and the code is correct;
its *evidence statement* is stale.

**Why it matters:** the sweep in §1 checks that decisions are implemented, not that their
recorded measurements still hold. A reader of D32 today would conclude the path is
unexercised when it is well exercised. Several D28–D42 decisions carry in-sample counts
from the five-company era.

**Smallest fix:** a one-line status note on D32; and, more generally, treat "measured at
five companies" statements as provisional wherever they appear.

### 6. README.md describes a project two phases into its build
**LOW to fix, HIGH if shown to anyone**

README says **"Phase 1 complete — project skeleton, configuration and setup tests. Next:
Phase 2, SEC ingestion"** and **"pytest # 6 passed"**. The actual state is all ten phases
built, 844 tests, 43 companies adopted, 74 decisions recorded.

**Why it matters for this audit specifically:** the brief asks what a README reader would
wrongly conclude. They would conclude the project is **barely started**. That is the
opposite of overstatement, but it is equally a mismatch between document and evidence —
and it is the first file anyone opens.

---

## Clean categories, stated plainly

**Decision drift D43–D74: clean. 32 of 32 implemented as recorded.** Every decision was
checked against code, config, schema and tests. Two apparent misses in the automated sweep
(D56, D63) were verified false positives — a docstring mention and a test under a different
name. **No decision exists only in DECISIONS.md, none is implemented differently from how
it is recorded, and no superseded decision was left unamended** — D64 carries an amendment
pointer to D70, D8 to D54, D10 to D46, D20 to D53, D42c to D43, D30(b) is marked discharged.

**The three demonstration-run fixes verified independently against current data:**

| Fix | Claimed | Verified |
|---|---|---|
| D69 GIS impossible margins | 0 remaining | **0** ✓ (CAG's 4 remain — finding 3) |
| D69 refusals | GIS 6 | **13 across GIS 6, PG 3, HAS 3, DVN 1** ✓ |
| D70 zero-shock grade changes | 88 → 1 | **1** ✓ (cause is finding 1, not FCF) |
| D70 Severe improvements | 10 → 0 | **0** ✓ |
| D71 band occupancy | [23,59,112,156,143,147], 24% | **exact match** ✓ |

**Rule 14 / D68's split at scale: clean.** `FIXTURE_CIKS` is the five fixtures; all six
pinned dictionaries (`METRIC_COVERAGE`, `CCL_SCORES`, `SCORE_SHAPE`,
`TREND_WARNINGS_SHAPE`, `STRESSABLE`, `INTEGRITY_OUTCOMES`) are keyed to fixture CIKs only,
with **no non-fixture CIK in any of them**. One test parametrises over `ALL_CACHED` (105
payloads) asserting structural invariants with no pinned numbers, plus a thin-path
assertion. **Nothing was pinned from unexamined output**: the universe adoption forced
D68's split precisely to prevent ~100 unexamined expectations, and every re-baseline in the
demonstration-run fixes was measured and inspected before pinning — the 0.05→0.50 tolerance
correction is the clearest case, where the first guess would have discarded 65 legitimate
concept-periods.

---

## What can honestly be claimed

### Fully validated against real data

| Claim | Evidence |
|---|---|
| Ingests and normalises SEC XBRL for arbitrary US filers | 105 companies fetched and run end to end; 43 adopted after screening |
| Computes 17 credit metrics with full provenance to tag and filing | 781 company-periods†; every metric traceable through `metric_inputs → concepts → concept_inputs → facts` |
| Refuses rather than guessing when inputs conflict or are missing | **18 distinct reason codes with real witnesses**, 2,241 `MISSING_INPUT` refusals, 70 `COMPONENT_AGGREGATE_MISMATCH`, 13 `CANDIDATE_TAG_MISMATCH` |
| Scores and grades with a visible, attributed cap | 780 scored periods†; grade distribution 51/120/286/202/76/45† across grades 1–6 — see the † correction note at the top |
| Classifies trends and raises early warnings | 5,544 trend verdicts, 1,539 warnings across 11 indicators |
| Runs deterministic stress with driver attribution | 647 stressable periods† × 3 scenarios; driver isolation verified on real runs |
| Detects a known class of tagging error | GIS 90% revenue disagreement caught; CAG single-tag error caught by the margin check |
| Produces an evidence pack and validates a memo against it | One real pack (334 lines, 541 numeric tokens); five-violation test |

### Works, but on synthetic validation only

- **Five fail-severity integrity checks.** `current_assets_subset`, `current_liabilities_subset`, `cash_subset`, `debt_subset`, `revenue_non_negative` ran 287–737 times each and **never failed on real data**. Their failure paths are exercised only by fixtures.
- **`NO_DEBT`, `ZERO_DENOMINATOR`, `NEGATIVE_DENOMINATOR`, `NO_INTEREST_NO_DEBT`.** Unit-tested; no adopted company reaches them.
- **The FYE-derivation edge cases** `AMBIGUOUS_FYE`, `FYE_TIE`, `NO_FYE_ANCHOR`. `FYE_DISAGREEMENT` has 6 real witnesses; the others none.
- **The operating-leverage EBITDA mode.** `constant_margin` is the default and everything measured uses it; mode B is tested but has never run on a real scenario in anger.
- **Custom stress scenarios and `new_debt_rate` resolution.** Every preset carries `additional_debt: 0` by design (D53c), so the rate ladder is unit-tested only.
- **The evidence exporter.** See finding 2 — no test at all.

### Documented assumptions, not validated behaviour

These are **project assumptions the methodology explicitly labels as such**, and no claim
should imply they are calibrated:

- **Every band edge.** `ebit_interest_cover` was re-edged on observed distribution (D71) — that is *distributional* evidence, not evidence the bands map to credit outcomes. No band has ever been tested against defaults, losses or agency ratings, because the project has no such data.
- **Category weights** 25/20/20/20/15, and the **graduated grade cap** (D46).
- **Every stress parameter**: `fixed_cost_share` 0.3, `floating_share` 1.0 (forced — the split is unreachable from XBRL), `default_tax_rate` 0.21 (statutory, deliberately not the 16.31% in-sample median), `new_debt_rate_default` 0.06, and the preset shock magnitudes.
- **Trend materiality thresholds** and `warning_escalation_count` 3.
- **The liquidity bands for negative-working-capital businesses** — 7 of 43 companies including P&G score zero liquidity points structurally (D48/D72a).

### Claims a reader would form that the evidence does not support

1. **That the grades mean something externally.** They are an internal analytical scale. Nothing maps them to agency ratings, defaults or spreads, and no such validation is possible with the data the project uses. The methodology says this; a casual reader of a grade table might not absorb it.
2. **That a validated memo is a checked memo.** The validator confirms numbers *appear*; it cannot confirm they are used correctly, and a fabricated source passes cleanly. The tool states this above every result — the risk is in summarising the tool, not in the tool.
3. **That 43 companies is a validated universe.** They are screened for *data adequacy*, not sampled for representativeness. All are large US filers; the set over-indexes on hotels, gaming and restaurants.
4. **That "844 tests" implies breadth of real-world validation.** Most assert engine behaviour against hand-computed or fixture data. The real-data assertions are narrower and are the ones that matter for this claim.
5. **From the README specifically: that the project is at Phase 1** (finding 6).

---

## The three parked calibration items

**(a) Escalation at 31% of periods — parking is still correct, but the number moved.**
Re-measured across the adopted 43: **1,539 warnings**, escalation still firing broadly.
Rule 12's principle continues to apply. Parking remains right because changing the
threshold changes every historical warning severity, and there is no evidence base for
choosing 4 over 3 — only an intuition that 31% feels high. **Unchanged: park it.**

**(b) Sector thresholds — the picture has strengthened, and this is now the most
evidence-backed of the three.** It began as one company (D48, CCL liquidity). It is now
**three independent instances**: CCL's liquidity, CCL's ~0.19% tonnage-tax effective rate
(D55), and the 7-of-43 negative-working-capital liquidity finding including P&G (D72a).
Still correctly parked — a sector framework for 43 companies across 21 SIC groups would be
fitting noise — but it has crossed from anecdote to pattern, and should be the **first**
calibration item taken up if the universe grows.

**(c) The four never-firing integrity checks — parking is still correct and the evidence is
now much stronger.** `debt_subset` went from 21 runnable periods to **287** and still never
fails. That is the outcome that would have changed the call, and it did not: these are
accounting identities a filer would have to mis-tag to break. **The honest description is
unchanged — they remain validated by synthetic fixtures only — but the case for leaving
them alone is now empirical rather than assumed.**

One thing did change: **`ebitda_margin_plausible` (D69) is the first fail-severity check
with a real witness**, failing 4 CAG periods. That demonstrates the check mechanism works
end to end on real data, which none of the other five had shown.

---

## Verdicts

### Is v1 complete and correct as it stands?

**Complete: yes.** All ten phases are built. Every capability the build plan lists exists,
runs on real data, and is committed. The decision record is unusually clean — 32 of 32
recent decisions implemented as recorded, with every superseded decision amended.

**Correct: with two qualifications, and they are not cosmetic.** Finding 1 means
base-versus-stressed grade comparison is unreliable for the 4 periods where stress
manufactures a coverage category, and the FCF equivalent leaks refused figures into
evidence packs in 110 more. Finding 2 means the artefact the AI workflow depends on is
untested. Both are small fixes — inherit the base refusal; write the pack tests — and
neither is structural. **I would not describe v1 as correct until finding 1 is fixed**,
because it silently produces an incomparable comparison, which is the failure mode this
project has spent seventy-four decisions trying to avoid.

### The strongest honest description

> A deterministic credit-analysis engine over SEC XBRL data that computes seventeen credit
> metrics, an explainable score and grade, trend classifications, early warnings and stress
> scenarios for 43 US-listed non-financial companies — **and refuses to produce a number
> whenever its inputs are missing, contradictory or ambiguous, with a recorded reason for
> every refusal.** Every figure traces to a filing and an XBRL tag. Every scoring and
> methodology choice is recorded with its evidence in a 74-entry decision log, including
> the ones that turned out to be wrong and why. A manual AI workflow exports an evidence
> pack and validates a drafted memo against it, with the validator's own limitations
> printed above its results.
>
> The thresholds, weights and stress parameters are **documented project assumptions, not
> calibrated values** — the grades are an internal analytical scale, and nothing maps them
> to ratings, defaults or spreads.

**What makes that description defensible is the refusal behaviour**, which is measured
rather than asserted: 18 distinct reason codes with real witnesses across 781
company-periods, a tagging error caught in two independent ways, and a validator that
states what it cannot check. **The weakest part of any claim is calibration**, and the
description above should never be shortened in a way that drops that sentence.
