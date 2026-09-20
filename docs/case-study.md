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
history, measured 2026-09-20 after D78-D80.** Every figure below carries that
basis, for a reason given under *Limitations*.

| | |
|---|---|
| Companies screened end to end | **105** — 43 adopted, a 41% pass rate |
| Company-periods analysed | **792** |
| Metric values computed | **10,975** |
| Metric values **refused** | **2,489**, across **14** reason codes with real witnesses |
| Periods scored | **776**, of which **267** carry a cap |
| Grade distribution 1→6 | 43 / 110 / 259 / 217 / 101 / 46 |
| Trend verdicts | **5,544** |
| Early warnings | **1,505** across 11 indicators |
| Stress runs | **630** periods × 3 scenarios = **1,890** |
| Tests | **930** — 886 pass, 44 skip by design. **17 of them are the golden set**: four company-years checked against the filing documents rather than against the engine |

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
- **930 tests is not 930 units of real-world validation.** Most assert engine behaviour
  against hand-computed or fixture data. The real-data assertions are narrower and are the
  ones that carry the claims above. Nearly every test compares the engine against itself:
  if it misread a filing *consistently*, almost nothing would notice. **The exception is
  the golden set** — four company-years read from the filing documents themselves. It found
  **four engine defects on first contact with real filings**, including a depreciation tag
  that understates one company's EBITDA by 80-86%, and two places where debt is counted
  twice. Those defects are measured and recorded, not yet fixed. **Four companies is four
  companies**: the set proves the engine reads those four filings correctly and nothing
  wider, and four of four turning up defects is not a reassuring ratio.
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
  informative: four companies, four defects, each invisible to a suite of 900 other tests
  because those tests all compare the engine to itself.

## Stack

Python 3.11, SQLite via stdlib `sqlite3`, pandas, pydantic, typer, pytest, PyYAML. No web
framework, no ORM, no Docker, no cloud. Thresholds, weights and stress defaults live in
YAML; a missing key raises rather than defaulting.

5,500 lines of source and 6,900 of tests (930 tests), built across eleven phases with a
decision log kept alongside.
