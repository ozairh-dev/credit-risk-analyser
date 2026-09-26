# Credit Risk Analyser — case study

A deterministic credit-analysis engine over SEC filings. It computes seventeen credit
metrics, an explainable score and grade, trend classifications, early warnings and stress
scenarios for 43 US-listed non-financial companies — **and refuses to produce a number
whenever its inputs are missing, contradictory or ambiguous, with a recorded reason for
every refusal.**

Built solo, in Python, at £0 running cost. No paid data, no hosting, no LLM in the
calculation path.

---

## The problem

Credit analysis begins with a tedious, error-prone step: getting comparable numbers out of
financial statements. Public filings are machine-readable — the SEC publishes XBRL for
every US filer — but "machine-readable" is not "consistent". The same economic quantity
appears under different tags at different companies, under different tags at the *same*
company across years, and sometimes under two tags in the same filing that disagree.

The interesting failure mode is not that this is hard. It is that it fails **quietly**. A
mis-resolved revenue figure produces a plausible margin, a plausible grade, and a plausible
memo. Nothing looks wrong. The system that gets this subtly wrong is more dangerous than
the one that crashes.

So the question the project is really about: **what should a credit tool do when the data
will not support an answer?**

## The approach

Four principles, each of which cost something to hold:

**1. The deterministic engine is authoritative.** Every ratio, score, grade, trend, warning
and stress result is computed by code. No LLM anywhere in that path. AI is used in one
place — a manual workflow where an analyst drafts a memo from an exported evidence pack —
and a validator checks that memo back against the pack.

**2. Provenance on every value.** A metric resolves backwards through its inputs to the
concept, the fact, the filing and the XBRL tag it came from. "Where did this number come
from" has an answer for every number. Filing URLs are derived at export rather than stored,
because a stored copy can only drift from the accession it describes.

**3. Refusal over estimation.** A missing input produces `UNAVAILABLE` with a reason code,
and anything depending on it is also `UNAVAILABLE`. No default values for financial inputs,
no approximating a refused value from an adjacent period or a related tag. **A refusal is
an answer.** This is the principle the whole design turns on, and the one that required the
most discipline: at every stage there was a plausible-looking number available, and taking
it would have been easier than refusing.

**4. Decisions recorded with their evidence.** 76 entries covering what was chosen, what
was measured, what the alternatives were, and what it cost — **including the choices that
turned out to be wrong, and why they survived review.** The decision log is the most useful
artefact the project produced.

## What it does

Nine stages: select facts → map tags to concepts → build composites → integrity checks →
compute ratios → classify trends → raise warnings → score and grade → stress.

The grade is an integer 1–6 built from five weighted categories. When a category cannot be
computed, the score is rescaled over what remains and the grade is **capped** by how many
categories scored — and the cap line, naming the missing categories and their causes,
travels with the grade everywhere it appears. A capped grade can never read as a judged one.

Stress runs three scenarios with **driver attribution**: each shock re-run alone, so the
contribution of each is visible separately. The attribution is reported as directionally
consistent with a bounded residual, never as additive — the propagation is multiplicative
and tax is floored, so the drivers genuinely do not sum.

## At scale

**Basis: the 43 adopted companies, capped grades, all periods of each company's filing
history, measured at commit `a5035a6` on 2026-09-20, after D78-D80 fixed the five defects
the golden set found.** Every figure below carries that
basis, for a reason given under *Limitations*.

| | |
|---|---|
| Companies screened end to end | **105** — 43 adopted, a 41% pass rate |
| Company-periods analysed | **792** (**777** with at least one computed metric) |
| Metric values computed | **10,975** |
| Metric values **refused** | **2,489**, across **15** reason codes with real witnesses |
| Periods scored | **776**, of which **267** carry a cap |
| Grade distribution 1→6 | 43 / 110 / 259 / 217 / 101 / 46 |
| Trend verdicts | **5,544** |
| Early warnings | **1,522** across 11 indicators |
| Stress runs | **630** periods × 3 scenarios = **1,890** |
| Tests | **936** — 892 pass, 44 skip by design. **17 of them are the golden set**: four company-years checked against the filing documents rather than against the engine |

**The refusal count is the number worth looking at**, because it is the part that is
measured rather than asserted. The bulk are ordinary missing inputs. The informative ones
are small and deliberate — each is a case where a plausible number was available and was
not produced:

- **70** `COMPONENT_AGGREGATE_MISMATCH` — debt components and the reported aggregate
  disagree beyond tolerance, so `total_debt` refuses rather than picking one
- **141** `LEASES_NOT_SEPARABLE` — lease liabilities cannot be separated from the debt
  figure, so a lease-adjusted number is not offered
- **42** `ST_DEBT_SCOPE_UNCERTAIN` / `LEASE_CONTAINMENT_UNVERIFIABLE` — a debt component
  may already sit inside the figure it would be added to, and the XBRL cannot settle it
- **13** `CANDIDATE_TAG_MISMATCH` — two tags for the same quantity disagree
- **68** `INTEGRITY_FAILED` — an arithmetic check proved an input wrong, so **every** metric
  for that period refuses

That last one has a concrete story. One company reported a single wrong revenue tag —
1.6bn against roughly 13bn actual — with no second tag to disagree with, so no
tag-comparison rule could catch it. A plausibility check did: an EBITDA margin above 100%
is arithmetically impossible. The engine now suppresses **every** metric for those four
periods rather than marking them, because an impossible figure should not be reachable at
all.

A second company was caught a different way: two revenue tags disagreeing by 90%, refused
on the disagreement itself. **The same class of error, caught by two independent
mechanisms.**

## Checking the engine against something other than itself

Every test in the suite compared the engine to hand-built fixtures or to its own prior
output. All of them shared one blind spot: **if the engine misread a filing consistently,
nothing would notice.** Expected values taken from the same XBRL the engine reads inherit
that blind spot exactly.

So the last thing built was a **golden set**: four company-years — CCL FY2019, YUM FY2023,
MCK FY2023, BDX FY2009 — where every figure was read from the income statement, balance
sheet, cash-flow statement and footnotes of the filing documents as a person reads them.
Not from the SEC's API, not from the cached data, not from any pipeline output.

**It found five engine defects within an hour, and not one was reachable by the 860 tests
that already existed.** Among them: a missing cash-flow tag that cost 75 company-periods
their operating cash flow and everything derived from it; two places where debt was counted
twice, because a component was added to a figure that already contained it; and a
depreciation tag that understated McDonald's EBITDA by **80-86%**, enough to move a grade.

Fixing them changed real numbers: 127 more metric values computed, **49 fewer periods
carrying a grade cap**, and a grade distribution that shifted measurably toward the strong
end.

### The pairing that says the most

Two moments in this project turned on reasoning without evidence, and they went opposite
ways. Both were settled by measurement, and neither would have been settled by argument.

**The one that was wrong.** After screening 77 companies and finding no instance of a
particular code path, I reported it as *"structurally unwitnessable"* and supplied a
mechanism: a debt-free filer reports nothing rather than zero, so a different refusal fires
first. **Both halves were false, and both were checkable in one query.** Filers tag explicit
zeros routinely — 213 of them across the data. And one company reports zero short-term
*and* zero long-term debt, so the path fires exactly as designed. It is simply rare: **2
occurrences in 1,028 resolved values**, which is why 77 companies were not enough. The claim
**survived review** — a plausible mechanism attached to a true observation is unusually
persuasive.

**The one that was right.** A rule was written refusing to compute total debt whenever one
particular tag appeared alongside another, on the suspicion that the first might already
contain the second. The tag's scope is filer-dependent and undetectable from the data, so
the rule refused rather than guess. **It had no witness at the time** — nothing in the data
demonstrated the overlap was real, and it could reasonably have been called
over-engineering.

Then the golden set read BDX's debt footnote:

```
Loans Payable — Domestic                 $ 200,000
Loans Payable — Foreign                      2,880
Current portion of long-term debt          200,085
                                         $ 402,965
```

The 402,965 the engine would have used **does** contain the 200,085 it would have added to
it. Had it added both, it would have overstated BDX's debt by **13%**. A rule written on
suspicion, with nothing to point at, was right about a real company — and the same hazard
turned out to be live in two other code paths that had no such guard.

**What distinguishes the two is not confidence — both claims were confidently made.** It is
that one was a negative claim ("this cannot happen") resting on absence, and the other was a
refusal to assert in the face of ambiguity. The first needed evidence it never had; the
second cost nothing while it waited for evidence, and was vindicated when the evidence
arrived. Recording both is more honest than recording either.

## Tested against real credit outcomes

Every check described so far compares the engine to a filing, a fixture, or itself. None of
them asks the question a credit tool exists to answer: **does it rank borrowers that failed
below borrowers that did not?**

So a benchmark was frozen before any improvement was attempted. 18 US non-financial filers
that later filed Chapter 11, each scored using **only filings available at least 12 months
before the petition**, against the 43 adopted companies as a survivor panel at the same
cutoff. Every event comes from the filer's own 8-K under Item 1.03, with the petition date
read from the document text rather than from an index.

**The point-in-time filter is the part that makes it honest.** The engine prefers the most
recently *filed* value for a period — correct for analysing a company today, and hindsight
in a backtest, because a figure restated after the bankruptcy would be used to "predict" it.
Facts filed after the cutoff are therefore dropped before the payload reaches the engine.
It removed 30–70% of facts per company. Without it the exercise would produce a flattering
number that looked rigorous.

**Two findings that need no threshold, each with its limit attached:**

- **Failures ranked below survivors in 89% of failure-survivor pairs** — AUC 0.893 on the
  score, 0.882 on the grade. Development set 0.902, held-out 0.882. Computed twice by
  independent derivations that agree. **This is discrimination on 18 events, not
  calibration**; no grade is mapped to a default rate, a spread or a loss, and nothing here
  could support such a map.
- **All 18 of 18 failures scored below the median of their own survivor panel.** Median
  grade 5.5 against 3.0. No failure graded 1, 2 or 3 at any cutoff. **11 of the 18 events
  are 2020**, so these are not 18 independent observations of a credit cycle.

Lead times run **14 to 26 months** (median 18), all at or beyond the 12-month minimum;
fiscal calendars, not choice, produce the spread. **The cohort cannot reach the 2008–09
cycle** — Charter's companyfacts begins 2011-05-03, so a 2008 cutoff yields zero facts
because XBRL did not exist. Everything here is conditioned on COVID and the 2022–23 rate
rise.

On a `grade >= 5` flag rule, frozen before the run and chosen on band semantics rather than
from the trade-off table: **78% sensitivity (14/18) at a 21% false-positive rate per
survivor company-cutoff** — but **49% (21 of 43) of distinct survivor companies are flagged
at least once.** Both describe the same rule. The 774 observations are 43 companies at 18
cutoffs, so **the precision of any rate here is governed by 43 and 18, not by the pair
count**; a company weak at one cutoff is usually weak at the next.

### Curating the cohort found more errors than it admitted

Five candidates were rejected, three for reasons that would have silently corrupted the
result. **CIK 1130713 is Overstock.com**, which bought the Bed Bath & Beyond brand out of
the bankruptcy auction and renamed itself — it never failed; the filer that did is 886158.
**CIK 1364479 is Herc Holdings**, the equipment-rental spinco that kept Hertz's old CIK and
survived. **CIK 77182 is J.C. Penney's pre-2002 operating subsidiary**, with two 10-Ks from
the 1990s and no XBRL. Each would have placed a surviving company in the failure cohort.

**And the SEC's own index turned out not to be a reliable oracle.** Its `reportDate`
disagrees with the 8-K's stated petition date in **8 of 19 cases**, and J.C. Penney's
2014-01-28 filing is tagged Item 1.03 while containing no bankruptcy language at all. One
correction changed an outcome: Windstream's petition was 2019-02-25, not the indexed
2019-02-28, which pushes the cutoff three days earlier, excludes the FY2017 10-K filed
2018-02-28, and moves its evaluated period back a year.

### The most informative result is a company the engine cannot see

`total_debt` refuses with `NO_DEBT_DATA` for **Hertz**, one of 2020's most leveraged filers.
No `ebit`, `cash`, `current_assets` or `current_liabilities` resolves either. Its securitised
fleet debt sits in **dimensioned contexts the companyfacts endpoint does not return**, behind
an **unclassified balance sheet**. This recurs the Ford finding that retired Ford as a
demonstration company years earlier in the project's life.

The damaging part is not the absence. Hertz's grade 4 rests on **one computed number** —
revenue grew 8% — giving business performance 8/10, rescaled to 80.0, capped from an uncapped
grade 2 to 4. Sixteen months before Chapter 11, **the engine rates Hertz better than every
failure it could actually see**, all of which are grade 5 or 6.

**The graduated cap is a ceiling, never a floor, so the system cannot say "we know nothing
about this borrower."** It can only decline to call that borrower strong. An analyst with
Hertz's filings in front of them records no opinion; this engine records a mid-scale grade.
That is a design gap in how missing information reaches the output, not a tuning question.

### Two results that retire a parked assumption and one that limits the method

**Escalated warnings barely discriminate: 50% of failures against 37% of survivors, 13
points.** The escalation threshold had been parked on the explicit grounds that firing in 31%
of periods "feels high" with no evidence base for moving it. That justification no longer
holds. The finding is stronger than a threshold question — the layer as built hardly
separates failures from survivors — and it identifies no better threshold.

**The four missed failures are a coherent group, not scatter.** Tailored Brands, Whiting,
Denbury and Extraction, all grade 4, all below most survivors (percentiles 0.22–0.40), and
**not one raised a warning of any kind.** Three of the four are oil and gas assessed on
FY2018 financials that failed in the March–April 2020 commodity collapse. Part of that is a
limit on what financial-statement analysis can do: **a 2018 balance sheet cannot contain a
future price shock**, and no ratio computed from it will. The engine ranked them below their
peers and did not rank them distressed, and closing that gap would need information the
filings do not carry.

The false positives read the same way — CCL, RCL, MAR, MGM, LVS, WYNN, PENN, CZR, HLT,
flagged mostly at COVID-era cutoffs. **A casino or a cruise operator in 2020 did look like a
default candidate on its financials.** Defensible on their own facts, and a reminder that the
false-positive rate is period-dependent.

### What the benchmark deliberately does not contain

Four of its five planned parts were not built. The numerical-accuracy check against filing
documents and the eight hand-written failure-mode cases were dropped on cost; the
unsupported-claim measurement and the blind grader are downstream of an LLM judgment layer
that does not exist yet. **The consequence should be read plainly: nothing in the benchmark
checks an engine figure against a filing document.** The golden set below remains the only
external check in the project, at four company-years.

What was built alongside A2 is a determinism assertion: seven companies, three repeats,
reversed analysis order, and four explicit hash seeds in fresh interpreters, all
bit-identical across eleven output blocks. **It proves only that the output does not move.**
A consistently wrong engine passes it perfectly.

## Limitations

Stated plainly, because a case study that overstates is worse than one that is modest and
exact.

> **The thresholds, weights and stress parameters are documented project assumptions, not
> calibrated values** — the grades are an internal analytical scale, and nothing maps them
> to ratings, defaults or spreads.

That sentence is the honest summary of the project's weakest point and is not softened
anywhere it appears. Specifically:

- **The grades mean nothing externally.** No band edge, weight or grade boundary has been
  tested against defaults, losses or agency ratings. The project has no such data and
  cannot acquire any at £0. One band — interest coverage — was re-edged on the observed
  distribution, which shows it now *discriminates* between companies; it does not show the
  discrimination predicts anything.
- **43 companies is not a validated universe.** They were screened for **data adequacy**,
  not sampled for representativeness, and all are large US filers. The set spans 21 distinct
  2-digit SIC groups (measured at adoption, D66) — but breadth of industry is not the same
  as being a representative sample of anything, and no claim here rests on it.

  An earlier version of the screen *did* skew: one criterion required every company to
  witness a particular integrity check, and since hotel and gaming filers happen to tag the
  relevant field, the set came out 5-of-19 leisure. The screen was selecting for a filing
  convention and reading it as a market. Demoting that criterion from a per-company gate to
  a set-level target took the universe from 19 to 43 and removed the cluster. **The
  generalisable point: a check that not every filer can witness must never be a per-company
  selection gate** — it silently narrows the universe along a dimension nobody chose.
- **936 tests is not 936 units of real-world validation.** Most assert engine behaviour
  against hand-computed or fixture data. The real-data assertions are narrower and are the
  ones that carry the claims above. Nearly every test compares the engine against itself:
  if it misread a filing *consistently*, almost nothing would notice. **The exception is
  the golden set** — four company-years read from the filing documents themselves. It found
  **five engine defects on first contact with real filings**, including a depreciation tag
  that understated one company's EBITDA by 80-86%, and two places where debt was counted
  twice. All five are fixed (D78-D80), each with its own before/after measurement across
  the 43. **Four companies is four companies**: the set proves the engine reads those four
  filings correctly and nothing wider, and four of four turning up defects is not a
  reassuring ratio.
- **A validated memo is not a checked memo.** The validator confirms figures *appear* in the
  evidence pack at the memo's stated precision. It cannot confirm they are used correctly: a
  figure cited under the wrong label passes, true figures assembled into a false claim pass,
  and a fabricated source passes. All three are pinned by test as characterised limitations
  and printed above every result.
- **One stress assumption dominates the rest.** The fixed/floating debt split is unreachable
  from XBRL, so the whole debt stack is assumed to reprice. Every rate-shock result inherits
  that. It is printed with every run, which is the most the data supports.
- **Every count needs its population and its commit.** Two separate investigations ended at
  the same lesson. A guard recorded as firing "zero times" on five companies fires on nine
  company-periods across the adopted 43. And a grade distribution that could not be
  reconciled against an audit turned out to be correct in both places — measured three
  commits apart, with neither stating which. A count without its scope is a true statement
  that means something other than it appears to.

## What I would do differently

- **Design for period-scoped tag candidates from the start.** One company in the set cannot
  produce a leverage ratio in any period because its consolidated debt disappears from the
  endpoint mid-history. Fixing it needs a tag-map format change that one company could not
  justify — but the need will recur.
- **Record negative claims as hypotheses with a query attached.** The project's most
  instructive error was reasoning from absence: a code path was declared "structurally
  unwitnessable" after 77 companies produced no instance, and the gap was filled with an
  invented mechanism rather than a measurement. Both halves were false and both were
  checkable in one query — the path fires, it is simply rare, at 2 occurrences in 1,028
  resolved values. **It survived review**, because a plausible mechanism attached to a true
  observation is unusually persuasive. It is written up in full rather than quietly fixed.
- **Build the hand-verified golden set first.** It was the last thing built and the most
  informative: four companies, five defects, each invisible to the 860 tests that already
  existed, because every one of them compared the engine to itself.

## Stack

Python 3.11, SQLite via stdlib `sqlite3`, pandas, pydantic, typer, pytest, PyYAML. No web
framework, no ORM, no Docker, no cloud. Thresholds, weights and stress defaults live in
YAML; a missing key raises rather than defaulting.

5,500 lines of source and 6,900 of tests (936 tests), built across eleven phases with a
decision log kept alongside.
