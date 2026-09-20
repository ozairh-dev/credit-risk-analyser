# Interview notes

Per-component notes for talking about this project: what was built, why, how it works, the
financial idea it demonstrates, the technical idea, the hardest problem, and what I would
do differently.

Numbers carry their basis. Where a figure has no basis I can state, it is not here.
**Basis for engine-wide figures: the 43 adopted companies, capped grades, 776 scored
periods, commit `ce0fc56`, measured 2026-09-20.**

The arguments behind every choice are in `DECISIONS.md` (76 entries). This file does not
repeat them — it points.

---

## 1. The normalisation layer

**What was built.** Selection and mapping: taking SEC `companyfacts` JSON — every fact a
company has ever tagged, in no useful order — and producing one value per concept per
period, with the filing and XBRL tag it came from recorded.

**Why.** Everything downstream is arithmetic on these numbers. A wrong value here is
invisible forever after: it produces a plausible ratio, a plausible grade and a plausible
memo. This is the only layer where an error cannot be caught by looking at the output.

**How it works.** Annual facts only, deduplicated, restatement-aware. 46 candidate XBRL
tags map to 34 internal concepts in explicit rank order from `config/tag_map.yaml`, with
`source_tag` recorded on every resolved value. Fiscal year ends are derived from duration
facts rather than read from a label. Restatements append alongside the original with a
supersession record; nothing is overwritten.

**Financial concept.** That "revenue" is not one number. A filer may tag `Revenues`,
`RevenueFromContractWithCustomerExcludingAssessedTax`, or both with different scopes —
Ford's `Revenues` includes Ford Credit financing revenue, legitimately 5–11% above the
operating figure. Normalising financial statements across filers is most of the work in any
real credit system, and it is judgement, not plumbing.

**Technical concept.** Ranked candidate resolution with provenance, driven entirely by
config. No tag name appears in code.

**Hardest problem — the fy-stamp trap, which appeared four times in different clothing.**
SEC stamps each fact with `fy`, the *filing's* fiscal year, not the period the fact covers.
Trusting it silently mis-dates facts.

1. **D19** — no index on `fy` anywhere, deliberately, with a test asserting none exists. A
   fast index would *invite* the exact query the schema exists to prevent.
2. **D13** — fiscal year ends derived from duration facts, not from the label.
3. **D36** — period continuity as a **day-gap** (350–380 days) rather than a calendar-year
   step. The calendar reading produced 8 false warnings; JNJ's fiscal 2011 contains no
   period end at all while calendar 2012 contains two. Day-gap: **zero false positives
   across all 82 consecutive pairs**, observed gaps 363–371 days.
4. **D40** — phantom periods: a period end that is not a reporting period at all.

**How it was solved.** Each time, by finding the underlying shape rather than patching the
symptom. D36 states it plainly for the next reader — *a fiscal-year label is not a date, and
a date's calendar year is not a fiscal year* — and D41 generalises it: **trusting an
enumeration rather than asking what each element represents.** That became the standing
question for any enumeration in this data source.

**What I would improve.** The tag map is flat, so a tag cannot be scoped to a period range.
Ford needs exactly that (below), and I ruled it out rather than change the format for one
company. With more companies it would become the right change, and the format should be
designed for it before it is forced.

---

## 2. The refusal model

**What was built.** A three-kind reason system where refusing to produce a number is a
first-class output, not an error path.

**Why.** The failure mode that matters in credit analysis is not a crash — it is a
confident wrong number. A missing input must never become a default, and a contradiction
must never be averaged away.

**How it works.** Every refusal carries a reason code; every code has exactly one **kind**;
the kind, not the code, decides what scoring does:

- **EVIDENCE** — we know and it is bad → scores 0
- **GAP** — we do not know → dropped, and the grade is capped
- **NEITHER** — a good thing, not a shortfall → weight redistributed, no cap

Measured: **2,616 metric values refused** against 10,848 computed, across **14 reason codes
with real witnesses**. The informative ones are deliberately small: 70
`COMPONENT_AGGREGATE_MISMATCH`, 148 `LEASES_NOT_SEPARABLE`, 68 `INTEGRITY_FAILED`, 13
`CANDIDATE_TAG_MISMATCH`.

**Financial concept.** Data quality *is* credit analysis. An analyst who cannot reconcile a
debt figure does not estimate it — they go back to the filing. The three-kind split encodes
the distinction an analyst makes instinctively: a company with negative EBITDA has a
problem; a company whose filing never tags interest expense is an *unknown*; a company with
no debt is neither.

**Technical concept.** Making the refusal a typed value rather than an exception, so it
flows through the pipeline and reaches the output with its reason intact.

**Hardest problem — `DebtCurrent`, where the obvious rule was measured and turned out
backwards.** The us-gaap taxonomy defines `DebtCurrent` as short-term debt **plus** current
maturities of long-term debt. So the obvious rule is to subtract `current_ltd` when both
resolve.

Measured on JNJ FY2022, the taxonomy is wrong about its own filers: `DebtCurrent` 12,800M
is a rounded copy of `ShortTermBorrowings` 12,756M, with `LongTermDebtCurrent` 1,551M
reported **separately** — so it *excludes* what the taxonomy says it includes. The same
shape holds in all 16 JNJ periods where the tag appears.

**How it was solved.** Neither rule is safe, because the tag's scope is filer-dependent and
undetectable from the data. So `total_debt` refuses with `ST_DEBT_SCOPE_UNCERTAIN`, both
values recorded (D32). **Refusing is the only honest option when the data cannot tell you
which of two readings is true.**

There is a second lesson attached. D32 recorded that the guard "fires zero times on the
five cached companies" — a latent-hole guard. On the 43-company universe it fires on **9
company-periods across 3 companies**. The reasoning was right and the evidence statement
went stale, which is why every count in this project now carries its population.

**What I would improve.** Reason codes are strings with a Python-side kind mapping. A typed
enum carrying its own kind would make an unmapped code impossible rather than merely
tested-against.

---

## 3. The scoring engine's missing-data rules

**What was built.** Weighted scoring across five categories with explicit rules for what
happens when a component, or a whole category, cannot be computed — and a grade cap that
makes missing data visible in the grade itself.

**Why.** Real filings are incomplete. A model that only scores complete data scores almost
nothing; one that silently scores incomplete data lies about its own confidence.

**How it works.** Five categories (25/20/20/20/15), nine scored components, each mapped to
0–10 points by band edges in config. Unavailable components are treated by reason kind
(above). When whole categories are missing, the score is rescaled over those that scored and
the grade is **capped by how many categories scored**: ≤2 → grade 4, 3–4 → grade 3, 5 →
uncapped (D46). The cap line is generated by the engine and travels with the grade
everywhere it appears, so a capped grade can never read as a judged one.

**Capping is systematic, not exceptional: 316 of 776 scored periods carry one.** That number
is why the cap had to be in the grade rather than in a footnote.

**Financial concept.** Scoring incomplete information without pretending it is complete. A
2-of-5 score and a 4-of-5 score are different kinds of statement, and a credit process that
presents them identically is misleading regardless of the arithmetic.

**Technical concept.** Making a confidence qualifier structural — generated from stored
fields, so a consumer cannot omit it by accident — rather than advisory.

**Hardest problem — Ford, adopted on familiarity and unusable.** Ford was chosen as the
leveraged demonstration case because it is a well-known leveraged borrower. Running the full
pipeline over its history showed it **cannot produce a single period where both `total_debt`
and `ebitda` resolve**, so no leverage metric can ever compute for it. `OperatingIncomeLoss`
covers only 2017–2025, and consolidated debt is absent from companyfacts from 2018 — it
exists only in dimensioned Automotive/Ford-Credit contexts the endpoint does not return.

**How it was solved.** Ford was dropped from the role and **kept as a negative fixture** —
it earns its place by refusing to compute. The general rule became CLAUDE.md rule 10:
*validate before adopting; familiarity is not validation.* The screen that followed found
WBD passing the mechanical bar while reporting 1,819M of debt for 2018 against a
`LongTermDebt` aggregate of 16,793M in the same filing — an **89% understatement stamped
REPORTED** — which is what the rule exists to catch.

**What I would improve.** The category weights, the cap thresholds and the choice of which
nine metrics score are all undocumented assumptions. Only `ebitda_interest_cover`'s
exclusion has a recorded argument. I would either find evidence for the rest or mark each
explicitly as arbitrary — which is what `risk-scoring.md` now does.

---

## 4. The stress engine's driver attribution

**What was built.** Three deterministic scenarios propagating rate, margin and revenue
shocks through the metrics, with **driver attribution**: each shock re-run alone against
base, so the contribution of each is visible separately.

**Why.** A combined stress result tells you the outcome but not the cause. "Grade 3 → 5
under Severe" is not actionable; "the rate shock alone costs 1.2x of coverage, the margin
shock 0.4x" is.

**How it works.** 630 stressable periods × 3 scenarios = 1,890 runs. Each run carries its
assumptions verbatim — five of them are **output duties recorded as decisions before the
engine existed**, so a stressed figure can never appear without the basis behind it.

Attribution is reported as **directionally consistent with a bounded residual, never as
additive.** Propagation is multiplicative and tax is floored at zero, so the drivers
genuinely do not sum — and a table implying they do would be wrong in a way that looks
right.

**Financial concept.** Scenario analysis with attribution, and the honesty to say that
interacting shocks do not decompose linearly.

**Technical concept.** Enforcing an invariant **structurally rather than by discipline.**

**Hardest problem — the stress engine could manufacture availability the base engine had
refused.** Its gates are necessarily weaker: it works from propagated figures, not from
resolved concepts and the coverage gates. So it computed metrics the base pipeline had
refused, and a stressed grade scored a category the base grade could not — making base and
stressed incomparable, which is the product's headline comparison.

**How it was solved.** An earlier fix (D70) suppressed the two FCF-derived metrics and
measured real improvement: zero-shock grade changes 88 → 1, Severe improvements 10 → 0. But
it fixed the **instance**, not the **mechanism**. The final audit found the residual: AZO
2011-08-27, base capped on four categories, stressed uncapped on five, arriving through
`ebit_interest_cover` — **no FCF involved**, so D70's rule could never have caught it.

D75 made every stressed metric inherit its base refusal, applied last so no branch can
bypass it: manufactured metrics **118 → 0**, zero-shock grade moves **1 → 0**. D70 was then
re-measured to check it had not become redundant — **it had not**; disabling it reintroduces
71 zero-shock changes, because it addresses a different cause.

**The lesson worth stating: this was the third time a fix aimed at an instance left the
mechanism live.** When a defect is fixed, check what class it belongs to, not just where it
appeared.

**What I would improve.** `floating_share` is forced to 1.0 because the fixed/floating debt
split is unreachable from XBRL. Every rate-shock result inherits that assumption, and it is
the single largest source of error in the stress output. It is printed with every run, which
is the most the data supports — but it is a real limitation, not a cosmetic one.

---

## 5. The evidence-pack workflow

**What was built.** An export that produces the complete and exclusive basis for a memo, and
a validator that checks a drafted memo against it — with the validator's own limitations
printed **above** every result.

**Why.** The £0 constraint rules out a runtime LLM, and the governance position rules out
one in the calculation path. The workflow is therefore manual by design: the engine decides
every number, a model may only write prose about numbers it was given.

**How it works.** A nine-section Markdown pack: provenance with derived filing URLs, the
grade with its cap line, reported concepts, calculated values, trends and warnings, stress
with the five duties verbatim, integrity results, the assumption register built from config,
and an explicit list of what the pack does **not** contain. The validator matches every
figure at the memo's stated precision, flags any grade claim other than the pack's, and
refuses `REVIEWED` while unverified figures exist.

**Financial concept.** Auditability. A credit memo is only as good as the evidence trail
behind it, and "where did this number come from" must have an answer for every number.

**Technical concept.** Defining a trust boundary and making it enforceable — the "what this
pack does not contain" section is what makes "Data not available" a checkable rule rather
than an instruction.

**Hardest problem — the one I got wrong, reasoned from absence and had confirmed.** Not a
code defect: a reasoning failure, recorded in full as D67.

After screening 77 companies and finding zero `NO_DEBT` occurrences, I reported the path as
**"structurally unwitnessable"** and supplied a mechanism: *a debt-free filer reports nothing
rather than zero, so `NO_DEBT_DATA` fires at the composite layer first.*

**Both halves were false, and both were checkable in one query.** Filers tag explicit zeros
routinely — **213 explicit zero debt tags across 105 payloads**. And QCOM FY2014 reports
`ShortTermBorrowings = 0` *and* `LongTermDebt = 0`, so `total_debt` is exactly 0 and
`NO_DEBT` fires exactly as designed. It is simply rare: **2 occurrences in 1,028 resolved
`total_debt` values**, which is why 77 companies were not enough.

**The error survived review.** The owner read the claim, accepted the theory, and asked for
it to be recorded as a finding — so a second pair of eyes did not catch it either. A
plausible mechanism attached to a true observation ("we found none") is unusually
persuasive, which is exactly why the measurement, not the story, has to carry the weight.
It was corrected only by screening one more batch for unrelated reasons.

**How it was solved.** By measuring, and by writing the failure down with the same care as
a success — including that review did not catch it. The principle that came out of it: **a
negative claim needs the same evidentiary standard as a positive one, arguably higher**,
since "not found yet" and "cannot exist" are indistinguishable from inside a finite sample,
and only the second licenses deleting a code path.

**What I would improve.** The validator reads numbers, not labels or arguments. A figure
cited under the wrong label passes; true figures assembled into a false claim pass; a
fabricated source passes. All three are pinned by test as **characterised limitations rather
than defects**, and stated above every run — but the gap between "validated" and "correct"
is the thing most likely to be misread by someone summarising the tool rather than using it.

---

## If I started again

- **Design the tag map for period-scoped candidates from the start.** Ford needs it; one
  company was not enough to justify the format change, but the need will recur.
- **Write the negative claims down as claims.** The NO_DEBT error would have been caught in
  a day if "structurally unwitnessable" had been recorded as a hypothesis with a query
  attached rather than as a finding.
- **Attach a population and a commit to every count, from the first one.** Two separate
  investigations ended in the same place: D32's stale "fires zero times", and a grade
  distribution that could not be reconciled until the commit it was measured at was found.
- **Build the hand-verified golden set early.** It is the one thing in the v1 plan that was
  specified and not built, and it is the only test that would catch the engine misreading a
  filing *consistently* — every other test compares the engine against itself.
