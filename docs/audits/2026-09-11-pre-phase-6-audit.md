# Pre-Phase-6 audit

**Scope:** Tasks 9, 10, 11 and the Phase 5 completion; decisions D28–D42. The
Tasks 1–8 baseline is assumed sound — the pre-Task-9 audit covered it and its
blockers were cleared in `261ab85`.

**Method:** every decision from D28 checked against code and docs; all seventeen
metrics measured across all five cached companies for both value coverage and
*joint input availability*; coverage mapped onto Phase 6's five scoring
categories; branch coverage read for the modules built in Tasks 9–11; newer
tests read for rule-14 failure modes.

**State audited:** `4f5c258`, 424 passing / 8 skipped, working tree clean.

*(Filename carries the date given in the request; the audit was run 2026-09-12.)*

---

## BLOCKERS

### 1. Four of five demonstration companies can never produce a five-category score
**CRITICAL · fitness of the company set, not of the code**

**What:** Phase 6 scores five categories — leverage, coverage, liquidity, cash
flow, business performance — and caps the grade at 3 (D10) whenever a whole
category is missing. Mapping measured metric coverage onto those categories:

| Company | Periods with all 5 categories | Categories never available |
|---|---|---|
| **CCL** | **13 / 19** | — |
| LUMN | **0 / 19** | — (best period reaches 4/5) |
| F | **0 / 19** | **cash_flow** |
| JNJ | **0 / 19** | — (best period reaches 4/5) |
| KHC | **0 / 13** | **business_performance** |

**Only CCL can ever be scored without triggering the grade cap.** Ford can never
score cash flow in any period; KHC can never score business performance. LUMN and
JNJ reach 4 of 5 at best, so every period of theirs is grade-capped at 3
regardless of actual credit quality.

**How found:** joining the seventeen-metric coverage measurement to the category
table in `credit-methodology.md` and applying D10's cap rule.

**Why it matters:** Phase 6 will produce grades that look like credit judgements
but are in fact artefacts of tag-map coverage. A company capped at Grade 3 for a
missing category is indistinguishable, in the output, from one genuinely rated 3.
Worse, it is *systematic* — four of five companies, every period — so the defect
will not look like an anomaly during review.

**Smallest fix:** none available in code; this is a company-set problem. Either
(a) adopt companies selected against joint availability before Phase 6 ships
grades, or (b) have Phase 6 state the capped-category list in every explain
output so a capped grade is never mistaken for a judged one. **(b) is required
regardless; (a) is what makes the demonstration meaningful.**

---

### 2. `revenue_growth` loses a legitimate value to a phantom period — D40's hazard, unfixed where D42c named it
**HIGH · a correct value silently absent**

**What:** `_revenue_growth` pairs each period with `ends[i - 1]`, the immediately
preceding entry in the **full** period list, which includes D40's phantom periods.
LUMN's phantom `2014-02-20` sits between `2013-12-31` and `2014-12-31`, so
`2014-12-31` pairs against a period with no revenue and returns
`INSUFFICIENT_DATA`. The true pair `2013-12-31 → 2014-12-31` is **365 days**,
comfortably inside `continuity_window_days`.

Measured: LUMN resolves revenue in 18 periods — 17 possible pairs — and produces
**16**. One legitimate value lost.

**How found:** tracing the D40-phantom interaction into the only sequence-dependent
metric, then confirming the true prior period's gap by hand.

**Why it matters:** D40 established that a period resolving no concepts is not a
link in a sequence, and D42c explicitly named `revenue_growth` as inheriting that
topology. The lesson was recorded but **not applied**: D40 excluded phantoms from
continuity, and D42c reused D36's *window* without reusing D40's *eligibility
filter*. The failure is fail-safe (a missing value, not a wrong one) but it is the
precise bug both decisions were written to prevent, and Phase 7 is entirely
sequence-based.

**Smallest fix:** pair against the most recent prior period that resolves
`revenue`, not `ends[i - 1]` — then apply the window test to that pair. One line,
plus a real-data assertion that LUMN produces 17.

---

### 3. Three dead functions duplicate live logic and have already diverged
**HIGH · rule 13 violation, materialised**

**What:** `_net_debt_to_ebitda`, `_ebit_interest_cover` and `_current_ratio` —
the Task 11 originals — remain in `ratios.py` with **zero call sites**. The Phase 5
completion replaced them with `_ebitda_ratio`, `_interest_cover` and
`_simple_ratio` but did not delete them.

They have **already drifted**: the live `_simple_ratio` carries the offending
figure on a `NEGATIVE_DENOMINATOR` refusal (`('current_liabilities', -5)`); the
dead `_current_ratio` returns `None` for it, so a warning raised through the dead
path would lose its number.

**How found:** branch coverage showed `ratios.py` at 82% with lines 113–121,
133–148 and 155–164 unexecuted; call-site grep confirmed zero callers; a direct
comparison confirmed the divergence.

**Why it matters:** CLAUDE.md rule 13 — the `NEGATIVE_EBITDA` gate, the interest
gate and the denominator rules now each exist in two places. The copies agree on
reason codes today and already disagree on payload. A future edit to one is
exactly the D18(a)/D21 shape that rule 13 exists to prevent, and the duplicates are
close enough to be edited by mistake.

**Smallest fix:** delete the three functions. Nothing references them; the suite
should stay green.

---

## NON-BLOCKERS

### 4. Three edge branches are neither witnessed nor tested
**MEDIUM**

**What:** three refusal paths have no real-data witness *and* no synthetic
assertion:
- `_debt_denominated`: `total_debt < 0` → `NEGATIVE_DENOMINATOR` (line 227)
- `_revenue_growth`: prior revenue `== 0` → `ZERO_DENOMINATOR` (line 327)
- `_revenue_growth`: prior revenue `< 0` → `NEGATIVE_DENOMINATOR` (line 329)

**How found:** cross-referencing branch coverage against the measured real-data
reason-code census.

**Why it matters:** every *other* witness-less code is synthetically asserted —
`NO_DEBT` (9 assertions), `NON_POSITIVE_CAPITAL` (3), `INVENTORY_UNKNOWN` (3),
`NO_INTEREST_NO_DEBT` (3), `ZERO_DENOMINATOR` (4), `NEGATIVE_DENOMINATOR` (3). These
three are the only genuinely undefended branches in the Task 9–11 modules. Each is
reachable (a filer tagging error produces negative debt or negative prior revenue).

**Smallest fix:** three unit tests in the shape already used in `test_ratios.py`.

---

### 5. The Task 11 deliverable — the `metrics` CLI command — has no test at all
**MEDIUM**

**What:** `cli.py` sits at **29%** branch coverage; lines 57–141, the whole
`metrics` command and its recursive provenance printer, are unexecuted by the
suite. `pipeline.py` is at **42%** — `analyse`, `analyse_and_store` and
`load_cached` are untested.

**How found:** `pytest --cov`.

**Why it matters:** the provenance chain is the task's stated deliverable, and the
recursion bug found during Task 11 (the display stopping one level short) was
caught by eye, not by a test — so the same class of defect would recur silently.
`pipeline.py` is the only place asserting the **six stages run in the correct
order**; nothing tests that assembly, and `test_real_companies.py` rebuilds the
order by hand in its fixture rather than calling it.

**Smallest fix:** one CLI test asserting a known ratio and one filing accession
appear in the output for a cached company, plus one test calling
`pipeline.analyse_and_store` and asserting the stage outputs are all present.
The second also closes the end-to-end gap in finding 8.

---

### 6. `debt_subset` still has one usable witness, and its coverage has not improved
**MEDIUM · carried forward, re-measured**

**What:** the `Debt ⊆ liabilities` integrity check ran in **21** company-periods
total: JNJ 18, Ford 3. Unchanged since Task 10. LUMN and KHC contribute zero
because every lease-inclusive period has `total_debt_ex_leases` UNAVAILABLE (D27),
and CCL reports no `Liabilities` tag at all (D25).

**Why it matters:** Ford's 3 periods come from the company D25 retired as unusable,
so in practice one filer's conventions validate the check. Already logged as a
Phase 10 selection criterion; re-stated here because Phase 6 excludes FAIL periods
from scoring, making the check's correctness load-bearing for grades.

**Smallest fix:** none in code — it is the same company-selection item as finding 1.

---

### 7. `D30(b)` records behaviour that no code implements
**LOW**

**What:** D30(b) says `source_url` is "derived from `(cik, accession)` at export".
No exporter exists, and nothing in `src/` derives a URL.

**How found:** decision-drift sweep — the only D28+ decision with no implementation.

**Why it matters:** not drift today (there is nothing to export), but the decision
reads as describing existing behaviour. A reader looking for the derivation will not
find it.

**Smallest fix:** one clause in D30(b) marking it an obligation on the first
exporter rather than a description of current code.

---

### 8. No test exercises the full six-stage pipeline as one call
**LOW · overlaps finding 5**

**What:** `test_real_companies.py`'s fixture assembles select → map → compose →
check → ratios → store by hand. `pipeline.analyse` — the module whose entire
purpose is to hold that order — is never called by a test.

**Why it matters:** if `pipeline.py` and the test fixture ever disagree about stage
order, every test still passes while the CLI produces different results. The
specific cross-stage dependencies *are* individually covered — D27's lease branch
reaching leverage ratios (LUMN/KHC coverage pins), D41's kinds reaching the store
(`test_every_reason_code_classifies`), D40's phantoms reaching metrics (finding 2,
which is how the defect surfaced) — so this is a structural gap, not an untested
behaviour.

**Smallest fix:** have the `stored` fixture call `pipeline.analyse`.

---

## Categories that came back clean

**Decision drift (D28–D42): clean, one exception.** All 22 checkable decisions are
implemented as recorded and reflected in the documents that should carry them.
`component_aggregate_tolerance` is in the D18 allowlist as D26 required; the
integrity thresholds are correctly *outside* it per D38; D39b's split, D40's
`trend_ends`, D41's mapping and D42's four calls are all live. The only exception
is finding 7, which is an unimplemented obligation rather than a divergence. **No
decision was found implemented differently from how it is recorded, and no
superseded decision was left unamended** — D37 explicitly supersedes Task 8's
design note, and D26's open dependency was closed with an amendment at Task 9.

**D41's three-kind split — specifically checked, and sound.** The mapping is the
single authority, is not duplicated in SQL or storage, and
`test_every_reason_code_classifies` asserts on real data that every stored reason
code classifies to one of the three kinds. `NO_DEBT` and `NO_INTEREST_NO_DEBT` are
both NEITHER, so no unlevered company can be grade-capped. The one gap is that
*nothing yet consumes* the mapping except the CLI — Phase 6 will be its first real
reader, so the split is correct but unexercised under load.

**Rule-14 failure modes: clean.** No surviving expected value is derived from a
rendering; the one that was (`15.6886`, read off the CLI's 2-decimal display) was
caught and corrected during Task 11. Real-data pins in `METRIC_COVERAGE` and
`METRIC_OUTCOMES` were measured, reconciled against period counts, and hand-spot-
checked before being written. `test_every_period_has_a_row_for_every_metric` and
`test_all_seventeen_metrics_exist_for_every_period` enforce that reconciliation, so
a count that shifted with the code would fail rather than re-baseline silently. The
remaining `len(config.tag_map())` derivations are anchored by the literal `== 34` in
`test_project_setup.py` (audit finding 13's fix), which still holds.

**Structural impossibility analysis: complete, and it found more than JNJ.** Seven
metric/company pairs are structurally impossible — inputs that never resolve over
the same period, not merely thin:

| Metric | Impossible for | Cause |
|---|---|---|
| `fcf_margin`, `capex_to_revenue` | F, KHC | F has no `PaymentsToAcquirePropertyPlantAndEquipment` tag at all; KHC no revenue |
| `fcf_to_debt` | LUMN, F | F as above; **LUMN's 3 fcf periods and 15 total_debt periods have an empty intersection** |
| `ebitda_margin`, `ebit_margin` | JNJ, KHC | JNJ's `ebit` (2010–2014) and `revenue` (2017–2025) never overlap |
| `revenue_growth`, `net_margin` | KHC | no revenue in any period |

**LUMN's `fcf_to_debt` is a second empty-intersection case** that per-concept counts
hide exactly as JNJ's did — LUMN resolves both inputs, just never together.

---

## Spec assumptions, updated from the previous audit's finding 15

| Assumption | Status | If wrong | Phase 6 depends? |
|---|---|---|---|
| Rule 2's 350–380 day window | **Partly validated.** Observed durations now span **362–372 days** across all five companies — ~10 days' headroom each side | A legitimate annual period silently dropped | Indirectly (every metric) |
| D13 FYE derivation / D16 14-day clustering | **Still never exercised.** All five companies produce **0 selection warnings**; `FYE_DISAGREEMENT`, `FYE_TIE`, `AMBIGUOUS_FYE`, `NO_FYE_ANCHOR` remain synthetic-only | Wrong fiscal-year anchor; instants on the wrong year | Yes — silently wrong periods would score |
| Rule 1's 10-K/A acceptance | **Validated by data, not by the suite.** **312** facts come from 10-K/A filings; no test names an amended filing | Amended filings ignored | Yes |
| `Debt ⊆ liabilities` | **Thin** — 21 periods, 2 companies, effectively 1 (finding 6) | Phase 6 excludes the wrong periods | **Yes — FAIL gates scoring** |
| D15 equal-value duplicates | **Validated** — **16,074** DUPLICATE rows across the five, all re-storing idempotently | — | No |
| Band edges in `thresholds.yaml` | **Never validated against anything.** Calibration section calls them project assumptions | Grades systematically wrong | **Yes — directly** |

The last row is worth stating plainly: **Phase 6's band edges have never been
tested against a real company's ratios.** They are documented assumptions, and the
methodology's Calibration section says so, but nothing has yet checked that CCL's
measured leverage produces a sensible grade.

---

## What Phase 6 inherits

**Solid.** All seventeen metrics compute correctly where their inputs exist; every
reason code classifies into exactly one of three kinds, asserted on real data; the
store carries metric provenance to tags and filings; integrity verdicts are derived
rather than stored; 424 tests pass with the newer modules at 82–100% branch
coverage. The decision record is unusually clean — no drift, no unamended
supersessions.

**Not solid.**

1. **The data, not the code.** Only CCL can be scored without a grade cap
   (finding 1). Phase 6 built and demonstrated on this company set will produce
   mostly-capped grades.
2. **Three open questions, one of which the coverage data now answers:**
   - *The "excluded until reviewed" mechanism* — still open. No review path
     exists; Phase 6 must build one or amend the methodology to say exclusion is
     permanent absent re-ingest. **No new information; still a genuine choice.**
   - *`NO_DEBT` redistribution across three metrics* — **the coverage data makes
     this moot for now.** `NO_DEBT` fires **zero times** across all 89
     company-periods, and only one of the three metrics using it
     (`fcf_to_debt`) is a scoring metric at all. The scoring question reduces to a
     single category with a single affected metric. Phase 6 should still decide it,
     but it is no longer a multi-category problem.
   - *Score fingerprint scope* — **the data supports D18's scope note directly.**
     Band edges and weights change scores without touching any concept or metric
     value, and `component_aggregate_tolerance` (which does change values) is
     already in the concept fingerprint. Phase 6 needs its own function over
     `thresholds.yaml`; reusing `config_fingerprint` would fingerprint scores
     against config that cannot affect them.
3. **Band edges are unvalidated** — the assumption Phase 6 depends on most directly
   has never been checked against a real company (see the table above).
4. **Findings 2 and 3** are in the metric layer Phase 6 reads: a silently missing
   `revenue_growth` value feeds the business-performance category, and the dead
   duplicates sit in the module Phase 6 will extend.

---

## Verdicts

**Is the codebase fit for Phase 6? — Yes, after findings 2 and 3.**
Both are small and well-defined: one line plus a test for the `revenue_growth`
pairing, and a deletion for the dead functions. Neither is structural. Everything
else found is a non-blocker, and the decision record — the thing most likely to rot
across three tasks — came back clean. Finding 5's missing CLI and pipeline tests
should be done in the same pass but do not gate Phase 6.

**Is the demonstration company set fit for Phase 6? — No.**
This is the more serious verdict and it is about data, not code. **Four of the five
companies cannot produce a five-category score in any period**, so every grade they
generate is capped at 3 by D10 — not because they are risky, but because a tag did
not resolve. Ford can never score cash flow; KHC can never score business
performance; LUMN and JNJ top out at four categories. Only CCL demonstrates the
product as designed, from 13 of its 19 periods.

Phase 6 can be *built* on this set — CCL alone is sufficient to exercise every
scoring path, including the cap, the redistribution and the evidence-versus-gap
split. It cannot be *demonstrated* on this set without the output being misleading.
The company-selection work already queued in `TODO.md` should be treated as a
prerequisite for showing anyone a grade, and the selection criterion is now sharper
than "validate before adopting": **check that a candidate's inputs resolve over the
same periods, since per-concept counts hide an empty intersection** — the failure
mode that produced both JNJ's margins and LUMN's `fcf_to_debt`.
