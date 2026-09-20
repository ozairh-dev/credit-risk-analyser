# Decisions

Format: decision · reason · alternatives considered · consequences.

## D1 — Python only, no frontend, no web framework in v1
Reason: one language for a solo builder; every hour on plumbing between Next.js,
TypeScript and Python is an hour not spent on the credit engine.
Alternatives: Next.js + Python (original brief); FastAPI + simple frontend.
Consequences: v1 output is CLI + exported reports. UI is a v2 decision.

## D2 — SQLite instead of PostgreSQL
Reason: 25–50 companies, one user, zero setup. Postgres adds nothing until concurrency
or scale exist.
Alternatives: Postgres locally; Supabase free tier.
Consequences: migration to Postgres later is a rewrite of `store/` against a new driver,
not a configuration change.
**Amended (pre-Task-9 audit, finding 10):** this originally read "mechanical via
SQLAlchemy". D22 removed SQLAlchemy from the stack in favour of stdlib `sqlite3`, so there
is no ORM to repoint — the SQL in `store/` is hand-written and some of it is
SQLite-specific (the `(period_start IS NULL)` expression index of D29, partial unique
indexes). Postgres remains reachable, but as deliberate work, not a swapped dialect.

## D3 — SEC EDGAR only in v1; Companies House deferred
Reason: companyfacts is a clean JSON API with standardised tags. UK iXBRL is document
parsing with weak standardisation and many abbreviated filings.
Alternatives: both from the start (original brief).
Consequences: US-listed universe only in v1.

## D4 — No runtime AI in v1; manual evidence-pack workflow with a validator
Reason: £0 constraint; a subscription is not an API; the deterministic engine must be
proven standalone first.
Alternatives: Ollama local model; Claude API.
Consequences: memo drafting is a documented manual process; validator enforces that no
number in a memo is absent from the evidence pack.

## D5 — EBITDA is always EBIT + D&A in v1, labelled as such
Reason: there is no standard us-gaap EBITDA tag; "reported EBITDA" as a first choice
(original brief) is not implementable from XBRL.
Alternatives: parse adjusted EBITDA from filings text (v3 at best).
Consequences: no adjusted EBITDA; D&A missing → EBITDA UNAVAILABLE.

## D6 — Operating lease liabilities included in total debt by default, with toggle
Reason: post-ASC 842 they are fixed obligations; credit analysis and rating agencies
treat them as debt-like. The original brief did not decide this.
Alternatives: exclude; include finance leases only.
Consequences: leverage will be higher for lease-heavy companies; ex-lease figure shown
alongside wherever it can be computed.
**Amended by D27 (2026-09-10):** "always shown alongside" is no longer absolute. On D27's
lease-inclusive LTD branch the filer reports debt and leases as one bundled figure, so
leases are not separable, `total_debt_ex_leases` is `UNAVAILABLE` with
`LEASES_NOT_SEPARABLE`, and `include_operating_leases` is inoperative for that period.
The toggle itself lives in `config/composites.yaml` (D28).

## D7 — Stress propagation: constant-margin default, operating-leverage optional
Reason: the original brief specified shocks but not how revenue shocks reach EBITDA.
Constant margin is transparent; operating leverage is more realistic but needs an
assumed fixed-cost share.
Alternatives: operating leverage as default.
Consequences: both modes tested; mode and fixed-cost share are ASSUMED and registered.

## D8 — Rate shocks apply to the whole debt stack by default (floating_share = 1.0)
Reason: floating/fixed split is not reliably available from XBRL. Whole-stack repricing
is conservative and stated as a simplification.
Alternatives: assume a floating share; parse debt footnotes.
Consequences: stressed interest is an upper bound; documented in every stress output.
**Amended by D54 (2026-09-13):** the value stands, the reasoning does not. Measured, the
split is **unreachable** rather than "not reliably available" — no rate-split USD amount
exists in any of the five cached payloads — and 1.0 is **not** merely "conservative": it
changes the stressed grade in four measured periods, including CCL 2015 and 2018 falling
3 -> 4 at Severe. Read D54 before relying on this entry's justification.

## D9 — Evidence-reason vs data-gap-reason UNAVAILABLE handled differently in scoring
Reason: negative EBITDA is information (score 0); missing interest expense is a gap
(drop and cap the grade). Treating both the same would either punish data gaps or
reward losses.
Alternatives: treat all UNAVAILABLE as neutral.
Consequences: reason codes are load-bearing and must be tested.

## D10 — Grade capped at 3 when a whole scoring category is missing
Reason: a score built on partial data should not be able to show "Very strong".
Alternatives: no cap; refuse to score.
Consequences: cap value is config; stated in the explain output.
**Amended by D46 (2026-09-12):** the cap is no longer a single value. It is graduated by
how many categories actually scored — N <= 2 caps at grade 4, N = 3-4 at grade 3 — because
a 2-of-5 score was presenting with the same authority as a 4-of-5 one. The config key
`max_grade_with_missing_category` is replaced by `max_grade_by_categories_scored`. D10's
principle is unchanged; only its granularity moved.

## D11 — Lease liability concepts split into current/noncurrent, not one "candidate" pair
Reason: `docs/data-sources.md` originally listed `finance_lease_liab` and
`operating_lease_liab` as single concepts with two "candidate" tags (first-found-wins),
but `total_debt` needs current + noncurrent lease liability **summed**, not one picked
over the other — the same relationship `current_ltd`/`noncurrent_ltd` already have as two
separate rows in the same table. `config/tag_map.yaml` already implemented the correct
split; the docs table was the one that was wrong.
Alternatives: keep leases as a single concept and document a special summing rule just
for those two rows.
Consequences: docs/data-sources.md now matches config/tag_map.yaml exactly. No code
impact — normalise/ tag-mapping (Phase 3) isn't built yet; this closes the mismatch
before it starts.

## D12 — margin_shock has one source of truth: the presets table, not the Inputs table
Reason: the stress "Inputs" table stated example margin_shock values with a negative
sign, contradicting both the propagation formula (`margin_s = ebitda_margin_base −
margin_shock`, where a *positive* shock reduces margin) and `config/stress.yaml`'s actual
positive preset/grid values. Two restatements of the same input had drifted apart.
Alternatives: fix the sign in the Inputs table and keep both; leave it as-is.
Consequences: the Inputs table now points to the presets table instead of restating
numbers, so there is one place to get this wrong instead of two. config/stress.yaml was
already correct and is unchanged. `test_stress_presets_present` now asserts the exact
moderate/severe values so a future edit can't silently reintroduce a sign error.

## D13 — Fiscal year end for instant-fact selection is derived from accepted duration facts
Decision: rule 3's "fiscal year end" is the `end` date of the duration facts accepted by
rules 1–2 for that fiscal year. If accepted duration facts disagree on `end`, use the
most common date and flag the period. If a year has no accepted duration facts, its
instant facts are `UNAVAILABLE` with reason `NO_FYE_ANCHOR` — never accepted unvalidated.
Reason: companyfacts JSON has no per-company fiscal-year-end field, so rule 3 as
originally written had no defined anchor (flag A from the Task 5 fixture).
Alternatives: fetch the SEC submissions API for the registrant's FYE (extra endpoint and
coupling for one date); majority vote over instant facts' own end dates (circular —
validates instants against themselves).
Consequences: rule written into docs/data-sources.md. A period with only balance-sheet
data cannot pass selection — fail-safe (CLAUDE.md rule 9) rather than guessed.

## D14 — Selection rules apply in order: filter (rules 1–3), then dedup (rule 4)
Decision: rules 1–3 filter the raw facts; rule 4's supersession pass runs on the
survivors only.
Reason: deduping first could pick a "most recently filed" fact that a later filter then
removes, silently discarding a valid earlier-filed fact. The fixture proves the point:
R4 and R3 share (Revenues, end 2023-12-31) within the same filing — dedup-before-filter
is an unresolvable tie (flag B from the Task 5 fixture).
Alternatives: dedup first; interleave per rule.
Consequences: Task 6 is a filter pipeline followed by a supersession pass; the fixture's
expected answers assume this order.

## D15 — Supersession only on changed values; equal values keep original-filing provenance
Decision: rule 4's "most recently filed is current" applies only when values for the
same (concept, period end) differ. When a later filing repeats an identical value
(routine comparative reporting), the earliest filing remains the source and no
`superseded_by` is recorded.
Reason: provenance answers "where was this first reported"; a comparative repeat of an
unchanged number is not a new report, and this keeps `superseded_by` meaningful instead
of firing on no-ops (flag C from the Task 5 fixture).
Alternatives: literal rule 4 — latest filing always current regardless of value.
Consequences: docs/data-sources.md rule 4 amended; fixture expectations updated — FY2022
revenue provenance is now the original 10-K (R1), and only the restated net income pair
produces a supersession record.

## D16 — Selection-plumbing details underdetermined by D13-D15, resolved fail-safe
Decision: four internal calls in select_annual_facts (Task 6), all invisible to the
Task 5 fixture and each with its own unit test:
1. D13 disagreement scope — accepted duration end-dates within 14 days of each other
   are the same fiscal year; farther apart are different fiscal years.
2. D13 most-common tie — no fiscal year end is chosen; instant facts near the tied
   dates are UNAVAILABLE with reason AMBIGUOUS_FYE, and the period is flagged.
3. NO_FYE_ANCHOR association — an instant whose end matches no derived FYE is a plain
   rule 3 exclusion when its own filing contributed accepted duration facts; it is
   UNAVAILABLE with NO_FYE_ANCHOR only when its filing contributed none. Keyed per
   filing (accession), never per fy stamp.
4. Same-day refilings — filed-date ties in the rule 4 supersession pass are broken by
   accession order, and every invocation of that tiebreak emits a
   SAME_DAY_REFILING_TIEBREAK warning naming the tag, period end and both accessions
   (owner amendment, 2026-09-10): accession order is a plausible proxy for filing
   sequence, not a guarantee, so the heuristic must be visible whenever it decides an
   outcome rather than silent.
Reason: D13-D15 do not determine these; each default follows the fail-safe principle
(CLAUDE.md rules 3 and 9) rather than guessing, and (1) keeps 52/53-week filers whose
year end drifts across the calendar boundary in one fiscal year.
Alternatives: block and ask per case (stalls on vanishing-rare edges the owner already
delegated as "internal calls"); calendar-year bucketing for (1) — breaks 52/53-week
filers at year boundaries.
Consequences: changing any of the four is a one-line edit plus its test.

## D17 — Tag-mapping behaviour beyond the docs' one-line rule (Task 7)
Decision: five calls in map_concepts. (1) Owner call, 2026-09-10: when two candidate
tags for one concept are both present in a period with different values, first-found
still wins but a CANDIDATE_TAG_DISAGREEMENT warning names both tags and both values —
conflicting figures are a data-quality signal, not something to swallow. (2) Equal-value
co-tagging does NOT warn: real filings routinely tag the same number under two candidate
tags (e.g. Revenues and RevenueFromContractWithCustomer...), so warning on equality
would fire on most companies and drown the signal. (3) Mapping consumes CURRENT facts
only; superseded and duplicate facts are audit trail. (4) A concept with no candidate
present for a period is UNAVAILABLE with reason NO_CANDIDATE_TAG, one row per
concept-period over the derived fiscal year ends plus any period a candidate actually
has — the raw material for Phase 4's completeness summary. (5) The reported label is
carried by selection (SelectedFact.label) so mapping can preserve it, implementing the
docs' "keep the original label".
Reason: docs/data-sources.md defines first-found-wins in one line; these are the
behaviours around it that the line does not determine.
Alternatives: warn on any co-presence (noise); map from superseded values (breaks
restatement semantics); skip UNAVAILABLE rows (hides gaps until scoring).
Consequences: each call has a test; the disagreement warning will fire routinely for
equity on companies with noncontrolling interests (StockholdersEquity vs the
...IncludingPortionAttributableToNoncontrollingInterest candidate differ by NCI) — that
is by design, the config ordering prefers parent-only equity.

## D18 — concepts and metrics are append-with-history, fingerprinted by config
Decision (owner amendment, 2026-09-10): concepts and metrics are not upserted on
identity. A partial unique index keeps one CURRENT row per identity (the pattern already
proven in facts) and each row records a `config_fingerprint`.
Reason: CALCULATED values are not config-independent — total_debt varies with
include_operating_leases (D6) and net_debt with include_st_investments — so a config
change silently alters every derived value while the underlying facts are unchanged.
Upsert would destroy the evidence that a number moved for a settings reason rather than
a filing reason: the same silent-provenance-loss D15 exists to prevent.
What the fingerprint covers: only the toggles that change a computed value
(include_operating_leases, include_st_investments — the allowlist in
store/fingerprint.py), never the whole config file. Band edges, weights and grade
boundaries are deliberately excluded: they change *scores*, not concept or metric
values, and scores keep their own history. The composites config file does not exist
yet (Task 9 creates it); until then the methodology's documented defaults are
fingerprinted, so the value is stable from the first stored row.
Alternatives: upsert (rejected above); fingerprint the whole config (every unrelated
threshold edit would orphan history).
**Scope note for Phase 6:** this fingerprint's scope is deliberately DISJOINT from what
a score fingerprint will need. Band edges, weights and grade boundaries move *scores*,
not concept or metric values — so Phase 6 needs its own fingerprint function over the
thresholds.yaml values, not a reuse of `store.fingerprint.config_fingerprint`. Reusing
this one would fingerprint scores against config that cannot affect them while ignoring
the config that can. Flagged here so it is designed rather than discovered.
Consequences: two implementation calls follow from it and are tested.
(a) No `superseded_by` pointer on concepts/metrics: the replacing row is the CURRENT row
with the same identity, and a pointer would need the CHECK-plus-partial-index pair to be
satisfiable in an impossible order. Supersession here is recompute history, not the
filing relationship facts model.
(b) Re-storing an IDENTICAL row under an identical fingerprint is a no-op, not a new
history entry — history exists to record that a value moved, and nothing moved. Facts
are likewise idempotent on (cik, tag, period_end, accession); a *changed* value for an
identity already stored CURRENT is a cross-fetch restatement, which nothing drives yet
and which raises rather than guessing (CLAUDE.md rule 9).

## D19 — No index on fy, deliberately
Decision: there is no index on `fy` anywhere, and "company + fiscal year" lookups go
through `(cik, period_end)` instead. A test asserts no index covers `fy`.
Reason: period identity is (concept, period_end) because SEC stamps `fy` with the
filing's fiscal year, not the fact's period (the fy-stamp trap). A fast fy index would
*invite* the exact query this schema exists to prevent; leaving the fy-keyed query
unsupported by any index is stronger protection than documenting against it.
Alternatives: add the fy index as originally requested in the Task 8 brief.
Consequences: code grouping by fy gets no index support and, if it tries to write two
periods under one identity, collides with a unique constraint loudly.

## D20 — Stress tables deferred to Phase 8
Decision (owner amendment, 2026-09-10): stress_runs, stress_results and stress_drivers
are not created in Task 8. scores, score_components, warnings and warning_evidence are,
as designed.
Reason: the stress engine still has unresolved config — new_debt_rate's fallback is an
open TODO in config/stress.yaml and fixed_cost_share is an untested assumption — so the
tables' shape is not yet determined by anything real. Phase 6-7 is fully specified in
the methodology, so its tables are.
**Amended by D53 (2026-09-12):** both blockers are resolved — fixed_cost_share is
measured and kept at 0.3 with output duties, and new_debt_rate has its band structure —
so the deferral's reason no longer holds and Phase 8 step two builds the tables.
Alternatives: build all three now from the methodology's stress section.
Consequences: Phase 8 adds them when it knows what it needs; no columns exist "for
later".

## D21 — filings.form is unconstrained; annual-only is a selection rule
Decision: `filings.form` has no CHECK restricting it to 10-K/10-K/A, although the
approved design had one.
Reason: the facts table also stores UNAVAILABLE rejection records, and a FOREIGN_UNIT
rejection is raised before rule 1 filtering — so a rejected fact can legitimately come
from a 10-Q, whose filing row must then be storable. Annual-only is a selection rule
(rule 1, enforced and tested in normalise/selection.py), not a storage invariant;
putting it in both places made the storage layer reject valid audit records.
Alternatives: apply rule 1 before rule 5 (changes approved Task 6 semantics); make
facts.accession nullable for UNAVAILABLE rows (two deviations instead of one).
Consequences: UnavailableFact now carries form/filed so every referenced filing can be
stored completely.

## D22 — SQLite via stdlib sqlite3, not SQLAlchemy
Decision: the store layer uses raw DDL and Python's stdlib `sqlite3`. CLAUDE.md's stack
line is amended from "SQLite via SQLAlchemy" to "SQLite via stdlib sqlite3".
Reason: the CHECK constraints and partial unique indexes are the substance of this
schema — they are what enforces the six data_status values, the UNAVAILABLE/reason_code
biconditional and the one-CURRENT-row-per-identity rule at the database level. Expressed
as raw SQL they are readable and reviewable; expressed through an ORM they would be
obscured, and the ORM itself is an abstraction for a problem we do not have (CLAUDE.md
rule 9).
Alternatives: SQLAlchemy Core (table metadata in Python, constraints as keyword
arguments); SQLAlchemy ORM (mapped classes).
Consequences: SQLAlchemy remains layerable later without schema changes if a reason
emerges — connection pooling, a second backend, or query composition that outgrows
hand-written SQL. pyproject.toml still lists sqlalchemy as a dependency; it is unused
for now and stays until something needs it or a cleanup pass removes it.

## D23 — "Core concept" defined for the abnormal-movement check, with its edge cases
Decision (owner call, 2026-09-10): the abnormal-movement integrity check runs over 16
named concepts, not all 31 — the four composites (total_debt, net_debt, ebitda, fcf) plus
the reported concepts feeding them and the ratios (revenue, ebit, d_and_a,
interest_expense, cash, total_assets, total_liabilities, equity, current_assets,
current_liabilities, cfo, capex). Two undefined cases are specified rather than left to
implementation: a sign change between periods flags regardless of magnitude
(ABNORMAL_SIGN_CHANGE), and a prior-period value of zero flags instead of producing an
undefined percentage (ABNORMAL_FROM_ZERO).
Reason: "any core concept" was undefined, so Task 10 would have resolved it by
implementation — the check's scope would have become whatever the code happened to do.
Composites are included deliberately: they aggregate several tags, so a single
mis-mapped input surfaces in the composite before it surfaces in any individual reported
concept; excluding them would skip the values most likely to be wrong. The full 31 are
excluded because a large move in something like dividends is ordinary and would only
generate noise. The two edge cases follow the same principle as the ratio rules — a
comparison that is not meaningfully a percentage must flag, never silently skip.
Alternatives: all 31 concepts (noise); reported concepts only (misses the aggregation
errors this check is best placed to catch); leave the edge cases to implementation.
Consequences: docs/credit-methodology.md carries the list and an edge-case table. The
three reason codes (ABNORMAL_MOVEMENT, ABNORMAL_SIGN_CHANGE, ABNORMAL_FROM_ZERO) are
named here so Task 10 implements them rather than inventing its own; they are stored in
data_quality_events like the other structured codes. A concept UNAVAILABLE in either
period is not an abnormal movement — it is already recorded as a data gap.

## D26 — Component/aggregate debt mismatch refuses to compute, it does not compute-and-flag
Decision (owner call, 2026-09-10): where `total_ltd_aggregate` and at least one of
`current_ltd` / `noncurrent_ltd` both resolve, the two are reconciled **before** either is
used. Within `config/composites.yaml: component_aggregate_tolerance` (default 0.05) the
components are used as before; above it `total_debt` is `UNAVAILABLE` with
`reason_code = COMPONENT_AGGREGATE_MISMATCH`, both figures recorded for review. The old
rule — "use the components, and flag if they differ from the aggregate by more than 5%" —
is replaced.

Reason: the old rule flagged a number as suspect and then used it anyway. WBD 2018
reported `current_ltd` 1,819M with `noncurrent_ltd` absent and a `LongTermDebt` aggregate
of **16,793M in the same filing**; the rule discarded the aggregate and emitted 1,819M, an
**89% understatement stamped REPORTED with full provenance**. That is precisely the
plausible-looking wrong number CLAUDE.md rule 9 forbids. Two contradictory figures for one
quantity mean the debt is not known, and the honest output is `UNAVAILABLE`.

**The detector matters, and a ratio heuristic is not it.** While screening candidates I
first tested plausibility as "total_debt below 2% of total liabilities". WBD sat at **8%**
and passed; the error was invisible to the ratio. Comparing against the aggregate caught it
immediately. Any future plausibility work on debt should compare against the aggregate, not
against a balance-sheet ratio.

**The comparison basis had to be specified, because `LongTermDebt`'s scope varies by
filer.** Measured: for JNJ the aggregate equals `current_ltd + noncurrent_ltd` **exactly in
all 8 periods** (0.0%), excluding short-term borrowings; for CCL it equals those
components **plus `short_term_debt`** exactly in 5 of 9 periods (2009-2013). Including
`short_term_debt` in the basis would therefore flag all 8 JNJ periods falsely (7.6%-83%
deviation), while excluding it flags CCL 2010 at 7.9%. The rule uses the long-term
components only — `LongTermDebt` is a long-term-debt tag, so that is the apples-to-apples
comparison — and a filer who bundles short-term borrowings into it shows up as a genuine
deviation rather than a silent exact match.

Alternatives: keep compute-and-flag (rejected, above); prefer the aggregate over the
components on mismatch (it is not knowable which is right — WBD's aggregate was correct,
but that cannot be assumed in general); include `short_term_debt` in the basis (falsely
flags every JNJ period); raise the tolerance to 10% to spare CCL 2010 (rejected — tuning a
correctness threshold to make a demonstration case look better is backwards; 7.9% is a real
discrepancy worth surfacing).

Consequences, measured across the four cached companies at the 5% default:

| Company | total_debt periods before | after | newly UNAVAILABLE |
|---|---|---|---|
| F | 3 | 3 | none (no period has both an aggregate and a component) |
| JNJ | 18 | 18 | none — exact agreement in all 8 comparable periods |
| LUMN | 2 | **0** | 2009-12-31 (500M vs 7,754M, 93.6%); 2010-12-31 (12M vs 7,328M, 99.8%) |
| CCL | 18 | **17** | 2010-11-30 (8,624M vs 9,364M, 7.9%) |

Total 41 -> 38 periods. Two consequences worth stating plainly: **LUMN now has no usable
`total_debt` in any period** — its only two were the WBD shape and were wrong by 94% and
100%, so losing them is the rule working, not a regression; and CCL's longest consecutive
run drops from 18 to 15 periods (2011-2025), still far above the three-period bar that
qualified it under D25.

`config/composites.yaml` is created by this change to hold the tolerance rather than
hard-coding 5%. **Open dependency for Task 9:** the tolerance changes whether `total_debt`
computes at all, so it must join D18's fingerprint allowlist in `store/fingerprint.py` when
the composites are wired. It is deliberately absent from that allowlist for now because
nothing reads it yet — noted in the YAML comment and here so it is not missed.
*(Done at Task 9: the tolerance joined the allowlist when metrics/composites.py became
its first reader.)*

## D27 — Lease-inclusive LTD is its own branch; plain LTD wins; leases become non-separable
Decision (owner-approved 2026-09-10): filers who report long-term debt only bundled with
capital/finance lease obligations get two new **distinct** concepts —
`ltd_incl_leases_current` and `ltd_incl_leases_noncurrent` (not aliases of
`current_ltd` / `noncurrent_ltd`) — and a third `total_ltd_aggregate`-style
branch in `total_debt`:

```
total_debt = ltd_incl_leases_current + ltd_incl_leases_noncurrent + short_term_debt
method     = debt_from_lease_inclusive_ltd
```

Lease components are **not** added on this branch; they are already inside. Four
specifics:

**1. Only the current/noncurrent pair is a value source.**
`DebtAndCapitalLeaseObligations` is mapped as `ltd_incl_leases_aggregate` for
**cross-checking only, never as a value**. Ford reports that single tag as 152,577M for
2008-2017 and then 600M / 600M / 471M for 2018-2020; using it as a value would
reintroduce precisely the error D25 retired Ford for, through a new door. Verified after
implementing: Ford resolves the aggregate in 13 periods and the pair in **zero**, so the
restriction keeps Ford out of the branch entirely. LUMN resolves the pair in 17 periods,
KHC in 12.

**2. Precedence: the plain LTD path wins when both resolve.** Three reasons, and **the
third is decisive**: (a) the plain concepts are debt alone, so leases stay separable and
`total_debt_ex_leases` stays computable; (b) the plain path can be policed by D26's
reconciliation, which this branch often cannot; and (c) **it is the only ordering that
does not propagate LUMN's uncorrected 2009 filer error into a 2x overstatement.** LUMN's
FY2010 10-K tagged `LongTermDebtAndCapitalLeaseObligationsCurrent` with the *same* value
as the noncurrent tag (7,254M for 2009, 7,316M for 2010). The FY2011 filing corrected
2010 to 12M — which D15 supersession already picks up — but **2009 was never corrected**,
so summing the pair there yields 14,508M against a true ~7,754M. Under plain-wins, 2009
and 2010 instead take the plain path, hit D26's mismatch check (93.6% and 99.8%), and stay
`UNAVAILABLE`. Stated explicitly: **LUMN gains 15 usable periods, not 17, and 2009/2010
remaining UNAVAILABLE is the correct outcome, not a shortfall** — those two periods'
inputs are self-contradictory and no honest number can be produced from them.

**3. `total_debt_ex_leases` → `UNAVAILABLE`, `LEASES_NOT_SEPARABLE`.** Never approximated
by subtracting the standalone lease tags: nothing guarantees those cover the same
obligations as the bundled figure (LUMN 2019's standalone lease tags total 2,212M, but
that is not demonstrably the lease content of the bundled 34,694M), so the subtraction
would be a fabricated number — rule 3.

**4. D26's consistency check extends to this branch.** Where `ltd_incl_leases_aggregate`
resolves, `ltd_incl_leases_current + ltd_incl_leases_noncurrent` is reconciled against it
at the same `component_aggregate_tolerance`; beyond it, `COMPONENT_AGGREGATE_MISMATCH`.
Reason: leaving this branch unchecked would police the better-validated path while
trusting the weaker one, which is backwards. And the cross-check-not-value-source
distinction is the same one that made D26 work — **comparing against a second source is
reliable, deriving a value from it is not.**

`include_operating_leases` is **inoperative** on this branch: the composition is fixed by
what the filer reported and there is no separable lease figure to include or omit. A row
on this branch still records the config fingerprint in effect when written (D18),
including a lease toggle that had no effect on it. That stays consistent — the
fingerprint's contract is "the settings that produced this row", not "the settings that
mattered" — but it means a fingerprint change must not be read as implying a
lease-inclusive row's value should have moved. The `LEASES_NOT_SEPARABLE` record on
`total_debt_ex_leases` is what makes that visible in the data. No allowlist change needed.

Alternatives: map the family onto the existing LTD concepts (double-counts leases, breaks
D6's toggle and `total_debt_ex_leases` — the certain form of the disjointness problem
that began this investigation); lease-inclusive wins on conflict (emits LUMN 2009's
14,508M); leave the branch unchecked (rejected per point 4); map the combined total as a
value source (rejected per point 1).

Consequences: LUMN 0 -> 15 usable `total_debt` periods, KHC 0 -> 12. CCL, JNJ and F are
untouched — the branch never fires for them. `config/tag_map.yaml` grows from 31 to 34
concepts, which grows the fixture's concept-slot count from 62 to 68; six tests that
asserted those totals now derive them from the tag map, since a concept addition
legitimately changes them while the load-bearing assertion (exactly 7 resolve, and which
7) stays exact. Composites themselves are Task 9.

## D28 — Composite toggles live in config only; a missing key raises
Decision (pre-Task-9 audit finding 3, 2026-09-11): `include_operating_leases` and
`include_st_investments` are defined in `config/composites.yaml` and read from there.
`store/fingerprint.py` no longer carries `COMPOSITE_DEFAULTS`; it keeps only
`FINGERPRINTED_KEYS` — the *names* of the settings that change a computed value, which is
a code-level judgement — and raises `KeyError` if the config file omits one.
Reason: the two toggles existed only as Python constants, with `composites.yaml`
mentioning them in a comment and defining neither. That is a direct CLAUDE.md rule 6
violation ("thresholds, weights, band edges and stress defaults live in `config/*.yaml`,
never in code") and it made D18's fingerprint describe a value no config file could
change. Task 9's `total_debt` and `net_debt` are the first code to read them, so the
violation had to be fixed before that code was written, not after.
Alternatives: keep the in-code defaults as a fallback (the thing being fixed); fall back
silently when a key is absent (rule 3 forbids default values for financial inputs, and a
silent default would make the fingerprint misdescribe the settings in force).
Consequences: `test_fingerprint_is_config_driven` proves the values come from the file by
editing a temp config and asserting the fingerprint changes — the same proof style as
`test_mapping_order_is_config_driven`, which checks *where a decision lives* rather than
only what it computes. `test_missing_composite_setting_raises` covers the refusal. The
`FileNotFoundError` fallback in `composite_config_values` is gone with the defaults.

## D29 — Fact identity includes period type: a duration fact and an instant fact are different facts
Decision (pre-Task-9 audit findings 1 and 5, 2026-09-11): fact identity widens from
`(tag, period_end)` to `(tag, period type, period_end)`, where period type is `duration`
when the fact carries a `start` and `instant` when it does not. Applied in every place
that encodes identity: the rule-4 group key in `normalise/selection.py`, `uq_facts_current`
in `store/schema.py` (via a `(period_start IS NULL)` index term), and both the superseder
lookup and the natural-key idempotency check in `store/writer.py`.
Reason: grouping a flow and a stock together made them supersede each other. Evidence from
real data — KHC `GoodwillImpairmentLoss` ending 2018-12-29, where one filing
(`0001637459-19-000049`) reported both a duration fact of 7,008M and an instant fact of
6,900M. The duration fact was recorded as **superseded by its own accession**, which is
meaningless provenance and contradicts D15's intent, and `store_company_data` then raised
`superseding fact not found`, so **KHC could not be stored at all**. The same company's
`ImpairmentOfIntangibleAssetsIndefinitelivedExcludingGoodwill` did not crash: there an
instant fact won and superseded a duration fact silently, so whether the bug crashed or
quietly picked the wrong-shape value depended on insertion order.
**No concept value was ever wrong:** no currently-mapped tag is reported as both shapes in
any cached company (measured across F, JNJ, LUMN, CCL, KHC), so this was a latent hole
rather than a live error. It was reachable only through tags outside the tag map — until a
future tag-map addition made it reachable through one inside it.
Alternatives: refuse mixed-shape groups with a new reason code (rejected — a duration fact
and an instant fact are both legitimate and differently-meaningful, so refusing would
discard two true values to avoid a conflict that does not exist); key on exact
`period_start` rather than period type (would stop a genuine restatement superseding when
two filings disagree on the start date by a day).
Consequences: all five cached companies now store, with zero facts superseded by their own
accession and re-store idempotent. Two facts of the *same* shape still supersede normally
(tested). Two further fixes came with it: (a) finding 5 — the writer's SUPERSEDED insertion
sort now includes `accn`, matching D16(4)'s tiebreak, which `selection.py` already applied
and the writer did not, so the two no longer disagree on same-day refilings; and (b) the
superseder lookup now requires exactly one match and raises otherwise, and the
concept->fact provenance lookup in `_store_concepts` also matches on period type, since
with identity widened both shapes can be CURRENT and provenance must point at the fact the
value actually came from.

**Status note (2026-09-17):** the counts above were **measured at five companies** (F,
JNJ, LUMN, CCL, KHC), before the 43-company universe was adopted (D67). The reasoning is
unaffected; the evidence statement is provisional. **Re-measure before relying on any
count here.**

## D24 — Rule 5 classifies units three ways; FOREIGN_UNIT is for currencies only
Decision (owner call, 2026-09-10, after measuring the three cached companies): rule 5
splits units into monetary-USD (selected), monetary-non-USD (`UNAVAILABLE`,
`FOREIGN_UNIT`), and not-a-monetary-item (ignored entirely — no fact, no marker, no
event). The third kind covers `shares`, `pure`, compound per-unit denominations of the
form `USD/<something>` (`USD/shares`, `USD/Warrant`), and count units naming a thing
counted (`segment`, `patent`, `lawsuit`, `Employee`, `reporting_unit`, …).
Implementation: a unit is treated as a currency only when it matches an ISO-4217 shape
(exactly three uppercase letters), which is what SEC uses for monetary facts.
Reason: the previous rule marked every non-USD, non-`shares`, non-`pure` unit as
`FOREIGN_UNIT`, which produced **3,845 markers across F, JNJ and LUMN — 3,612 of them
`USD/shares`** and ~233 count units. A data-quality marker that fires ~1,300 times per
company on ordinary reporting is not a signal; it would have made the Phase 4 panel
unreadable and buried the one marker that matters. Same principle as D15 (supersession
only on changed values), D17(2) (no warning on equal-value co-tagging) and D16(4)'s
tiebreak warning: a flag must fire when something is actually wrong. A per-share rate is
not foreign currency, and neither is a count of patents.
Alternatives: ignore only `USD/<something>` as literally scoped (would have left the
~233 count-unit markers, which are equally misclassified); keep an explicit denylist of
non-monetary unit names (unbounded — the sample alone contains `segment`, `Segment` and
the SEC typo `segement`).
Consequences: measured effect on the three cached companies — **3,845 markers -> 1**,
and that one is JNJ's single genuine `EUR` fact, which is exactly the case the code
exists for. Selected fact counts and all mapped values are unchanged (verified: JNJ 4,055
current facts before and after; `short_term_debt` 2025-12-28 still 8,495M via
`ShortTermBorrowings`). `classify_unit` is the single place this decision lives.

## D25 — CCL replaces Ford as the leveraged demonstration case; companies are validated, not assumed
Decision (2026-09-10): **CCL** (Carnival Corp, CIK 815097) is the leveraged demonstration
case. Ford is dropped from that role but its cached data is **retained deliberately** as a
negative fixture. And, generally: **a demonstration company may not be adopted until the
full pipeline has been run over its entire filing history**, including a
partial-components-versus-aggregate audit of `total_debt`. Familiarity with a company is
not evidence that its XBRL is usable.

Reason: Ford was adopted on familiarity, without that check. Running it revealed Ford
cannot produce a single period with both `total_debt` and `ebitda`, so no leverage metric
can ever compute for it: `OperatingIncomeLoss` covers only 2017-2025 while consolidated
debt is absent from companyfacts from 2018 (it exists only in dimensioned
Automotive/Ford-Credit contexts the endpoint does not return). Fixing that would have
required period-scoped tag candidates — a `tag_map.yaml` format change to solve one
company's problem, which CLAUDE.md rule 9 rules out.

The audit requirement is not theoretical: screening 13 candidates, **WBD passed the
mechanical bar (10 consecutive periods) while reporting 1,819M of debt for 2018 against a
`LongTermDebt` aggregate of 16,793M sitting in the same filing — an 89% understatement
stamped REPORTED**. The cause is the methodology's own components-vs-aggregate rule: the
aggregate is used only when *neither* `current_ltd` nor `noncurrent_ltd` is present, so one
resolving component is enough to discard it. The same shape appeared benignly in MGM
(2011-13, 2024-25) and CHTR (2014), where the aggregate happens to equal `noncurrent_ltd`.
A ratio threshold does not detect this (WBD sat at 8% of liabilities, not the <2% that
would look obviously wrong) — comparing against the aggregate does. **This is a live
methodology defect for Task 9, independent of company choice.**

On the slot itself: the sector label "industrial" was incidental. The requirement was a
genuinely leveraged, non-captive-finance, non-financial US borrower, which CCL satisfies
(SIC 4400, verified from the SEC submissions endpoint). Ford's captive finance arm was
part of why its debt was unreadable in the first place. No industrial screened passed —
URI has no true `InterestExpense` (only `InterestPaidNet`, a cash-flow concept), AAL and
DAL lack `capex` under the mapped tag, KHC's debt is lease-bundled.

Alternatives: keep Ford and add period-scoped tag candidates (format change, rule 9);
adopt WBD or CHTR (rejected — WBD factually wrong, CHTR's coverage ends in 2013 because
`InterestExpense` stops); adopt MGM (viable second choice, but its debt is lease-dominated
— 25.5bn of 31.9bn in 2025 — so its leverage swings on the `include_operating_leases`
toggle alone).

Consequences: CCL gives 18 consecutive validated periods (2008-2025) spanning a full
distress-and-recovery arc — debt tripling 11.5bn -> 35.9bn, three years of negative EBITDA
— which exercises D9's evidence-vs-gap paths on real data. No config changes were needed
to adopt it. Ford stays cached as the refuses-to-compute fixture. **CCL's known
limitation: `total_liabilities` never resolves for it — Carnival reports no `Liabilities`
tag — so the "Debt ⊆ liabilities" integrity check will be `UNAVAILABLE` for CCL in every
period.** That is correct fail-safe behaviour, not a defect, but it means CCL cannot serve
as the fixture for that particular integrity check.

## D30 — Two provenance fields are deliberately absent: currency and source_url
Decision (Task 8 design, recorded retrospectively at the pre-Task-9 audit, finding 9):
the store has no `currency` column and no `source_url` column. Both omissions were
settled when the schema was designed but never written down, so until now the only record
was a chat message while `docs/data-sources.md` still listed both as required fields.

(a) **`currency` is collapsed into `unit`.** v1 is USD-only — D3 restricts the universe to
US-listed filers and D24 makes a non-USD monetary fact `UNAVAILABLE` with `FOREIGN_UNIT`,
never converted. A separate currency column could therefore only ever hold `USD` beside a
`unit` that already says `USD`, or disagree with it. `unit` carries the currency for
monetary items and the dimension (`ratio`, `percent`) for everything else.

(b) **`source_url` is derived at export, not stored.** The SEC filing-index URL is a pure
function of `(cik, accession)`, both already columns on `facts`. A stored copy can only
drift: if EDGAR's URL shape changes, every historic row is silently wrong and needs a
migration, whereas a derived URL is corrected by editing one function.
*Status (DISCHARGED at Phase 9, 2026-09-16): `store/provenance.py::filing_url` is the
single derivation, and the evidence exporter is its only caller. The note below recorded
the obligation while it was outstanding.*
*Status (pre-Phase-6 audit, finding 7): this was an **obligation on the first exporter**,
not a description of existing code. No exporter exists yet and nothing in `src/` derives
a URL, so there is presently nothing to point a reader at. Whoever builds the first
export path owes the derivation — this entry states the requirement, it does not record
a completed one.*

Reason: both are the same principle — do not store what is already derivable from what is
stored, because the copy can disagree with its source. That is CLAUDE.md rule 13 (one
invariant, one layer) applied to columns rather than constraints.
Alternatives: add both columns as the doc's field list implied (rejected above); keep
`currency` against a future multi-currency universe (rejected — D3 makes that a v2 schema
change regardless, and a column that can hold only one value until then is not a head
start on the migration).
Consequences: anything needing a filing link builds it from `(cik, accession)`; nothing
reads a currency column, because there is none. If v1's USD-only assumption is lifted,
(a) is reopened as a deliberate schema change rather than inherited as a default.

## D31 — The cache window is exclusive: at exactly max_age the cache is stale
Decision (owner, pre-Task-9 cleanup, audit finding 8, 2026-09-11): `ingest/cache.py`
refuses a cached copy when `now - fetched_at >= max_age`. At exactly `max_age_hours` the
cache is stale and is re-fetched.
Reason: the window is a **staleness window, not a freshness guarantee**. "Do not re-fetch
within 24 hours" (`docs/data-sources.md`) describes the period during which re-fetching is
prohibited, and at exactly 24 hours that period has elapsed. Inclusive semantics would
make the real window 24 hours plus one tick — a value nobody chose. The cost asymmetry
points the same way: going stale one second early costs one unnecessary HTTP request to an
endpoint already rate-limited, while staying fresh one second late serves data the config
has already judged too old.
**Nothing chose the original `>`.** It fell out of typing rather than a judgment, and was
never exercised in either direction — the existing tests used 1h and 25h, so the boundary
itself was untested. This entry exists so the next reader finds a decision rather than an
accident.
Alternatives: inclusive (`>`), where exactly-max_age is still fresh. Smaller change,
rejected above.
Consequences: one character in `read_cache`, and `test_cache_at_exactly_max_age_is_stale`
now pins it. That test holds one cache file at a fixed age and moves the **window** across
it — three explicit `max_age` values — rather than moving the timestamp under a live
clock. The distinction is load-bearing, not stylistic: `read_cache` calls
`datetime.now()` itself, so a file written `max_age` ago is always `max_age` plus a few
microseconds by the time the comparison runs, which is stale under **both** operators and
cannot tell them apart. Testing values just inside and just outside the boundary would
have stepped around the race and proved nothing about the comparison; the clock is frozen
so equality is actually reachable. Verified by reverting to `>` and confirming that this
test, and only this test, fails.

## D32 — DebtCurrent's scope is filer-dependent; overlap with current_ltd refuses to compute
Decision (owner-approved 2026-09-11, Task 9): when `short_term_debt` resolves via the
`DebtCurrent` tag **and** `current_ltd` resolves in the same period, `total_debt` is
`UNAVAILABLE` with the new reason code `ST_DEBT_SCOPE_UNCERTAIN`, both values recorded.
`DebtCurrent` stays in the tag map as last-rank candidate; when `current_ltd` does not
resolve, no overlap is possible and the tag is usable.

Reason — the decisive finding: the us-gaap taxonomy defines `DebtCurrent` as short-term
debt **plus current maturities of long-term debt**, but JNJ's usage excludes them —
measured FY2022: `DebtCurrent` 12,800M is a rounded copy of `ShortTermBorrowings`
12,756M, with `LongTermDebtCurrent` 1,551M reported separately, and the same shape holds
in all 16 JNJ periods where the tag appears. So the tag's scope is filer-dependent and
undetectable from the data. A subtract rule (`DebtCurrent − current_ltd`) and a
take-it-alone rule each assume a scope that cannot be verified; refusing is the only
honest option (CLAUDE.md rules 3 and 9, and rule 11 — never approximate a refused value).

**D26 does not already cover this.** Its comparison basis is deliberately long-term
components only, so an inflated `short_term_debt` is invisible to the aggregate
reconciliation. The guard is a separate check on a separate component.

Fires zero times on the five cached companies: `ShortTermBorrowings` outranks
`DebtCurrent` in every JNJ period, and no other cached company reports the tag at all.
This is a latent-hole guard in the D29 mould — closed because a future tag-map or
universe change makes it reachable, not because it is live today.

Alternatives: drop `DebtCurrent` from the candidates (loses the only short-term figure
for filers who report nothing else, and the taxonomy-correct usage is genuinely the
better figure where `current_ltd` is absent); subtract or use alone (both assume an
unverifiable scope, above).
Consequences: a new reason code in the vocabulary (docs/data-sources.md); the guard sits
in `metrics/composites.py` before branch-1 assembly; unit-tested on synthetic data since
no cached company exercises it.

**Status note (2026-09-17, v1 final audit finding 5):** the "fires zero times" statement
above is **stale**. `ST_DEBT_SCOPE_UNCERTAIN` is now a live path:

- **Across the 43 adopted companies: 9 company-periods, 3 companies** — BDX 6, ECL 2,
  MPC 1. Those 9 refusals appear as **18 composite rows**, because a refused
  `total_debt` propagates to `net_debt`; that is the 18 the audit reported, and the two
  figures count different things rather than disagreeing.
- **Across all 105 screened companies: 62 company-periods, 14 companies** — MRK 13, QCOM
  9, HPQ 8, HAL 7, BDX 6, IBM 5, DLTR 4, COR/ECL/OXY 2 each, HCA/MPC/MTN/VZ 1 each.

**The decision itself is unchanged and correct** — the guard was right and the universe
grew into it — but the D29 latent-hole comparison no longer applies. Recorded with both
scopes because the first measurement taken for this note was run over all 105 and
reported as though it were the adopted 43, which would have overstated the adopted-set
figure roughly sevenfold. **A count is only meaningful with its population attached.**

## D33 — Four Task 9 spec gaps resolved (owner-approved 2026-09-11)
The methodology left four points underdetermined; each resolution is also written into
the docs rather than living only here. In D16's mould: each defaults fail-safe unless
measurement showed fail-safe was self-defeating.

**1. `short_term_investments` is zero-by-absence for `net_debt`; `cash` stays
`MISSING_INPUT`.** The general any-input-missing rule would kill `net_debt` in **61 of
87** cash-periods across the five validated companies — including every LUMN and KHC
period — for want of a refinement. Cash is the substantive input; STI adjusts it. The
zero-by-absence is recorded like `total_debt`'s optional components.

**2. "Same filing" means same-period, not same-accession.** The strict reading
contradicts D15, which deliberately keeps an equal-value fact at its original filing's
provenance — two decisions cannot both hold if one forbids what the other produces.
Measured: CURRENT debt inputs legitimately span accessions in 12 periods across the five
companies. Composites accept CURRENT facts regardless of accession; the rule's real
content — no mixing of quarters or fiscal periods — is enforced by selection.

**3. `total_debt_ex_leases` excludes both lease kinds:** `short_term_debt + current_ltd
+ noncurrent_ltd`. The figure was used in three places and defined in none. Cross-branch
comparability decides it: D27's bundle contains finance leases, so an "operating-only"
reading would make the figure mean different things on different branches — a metric
that changes definition by branch is worse than one occasionally unavailable.

**4. A half-resolved lease-inclusive pair falls through to `NO_DEBT_DATA`.** Half of an
already-weaker branch, with no D26-style cross-check available on that half, is the
least-trustworthy input in the tree. Zero half-resolved pairs exist in-sample (measured
across all five companies), so this is latent, not live. Also settled in passing, from
D26's own consequences table rather than as a new call: within the plain
`current_ltd`/`noncurrent_ltd` pair, the missing member counts as zero when the other is
present — JNJ's 18-period expectation in that table is only reachable on that reading
(7 of its periods are noncurrent-only with no aggregate) — and the lease composites sum
their split halves under the same zero-by-absence recording.

**Status note (2026-09-17):** the counts above were **measured at five companies** (F,
JNJ, LUMN, CCL, KHC), before the 43-company universe was adopted (D67). The reasoning is
unaffected; the evidence statement is provisional. **Re-measure before relying on any
count here.**

## D34 — Deviation edge semantics: agreement computes, contradiction refuses, bad input refuses
Decision (owner, Task 9, 2026-09-11): `_deviation(components, aggregate)` in
`metrics/composites.py` — the single function both D26 reconciliations funnel through —
resolves its edge cases as: **both zero → 0.0** (computes); **aggregate zero with
components non-zero → inf** (refuses); **either value negative → inf** (refuses). The
ordinary case is fixed by D26's measured figures: absolute difference relative to the
aggregate (CCL 2010: |8,624−9,364|/9,364 = 7.9%).

Reason — the test applied to each edge: **could this produce a plausible-looking wrong
number (forbidden), or only an unnecessary refusal (acceptable)?** Aggregate-zero-vs-
non-zero is a contradiction no percentage can express; proceeding would pick a side with
no basis. A negative value is a tagging error — debt cannot be negative — and a deviation
computed from it would launder bad input into a plausible number. Both-zero is the only
edge where the answer was *neither*: the sources agree ("no long-term debt"), and that
agreement is detectable directly even though 0/0 has no value — refusing there would cost
coverage on a case where both sources say the same thing. Hence it is the one edge that
computes.

Implementation constraint that is part of the decision: **signs are checked before any
`abs()`, and `abs()` applies only to the difference.** `abs()` on the inputs would turn
components = −8,624 against aggregate = 8,624 into a deviation of 0.0 — perfect agreement
manufactured from contradictory data, the worst available outcome. The negative-components
/ positive-aggregate-of-equal-magnitude case is pinned by a dedicated test, since it is
the one a misplaced `abs()` silently passes.

Alternatives: refuse on both-zero too (uniform fail-safe; rejected — an unnecessary
refusal with no protective value); treat aggregate-zero as tolerance-exempt agreement
(picks a side); clamp negatives to zero (launders the error).
Consequences: both the plain-components and lease-inclusive reconciliations inherit these
semantics from the one function (CLAUDE.md rule 13 — one invariant, one layer); a test
per edge in tests/test_composites.py.

## D35 — concepts.detail column, added at Task 9 rather than Task 8
Decision (2026-09-11): the `concepts` table gains a nullable `detail TEXT` column. It
holds supporting specifics that belong on the row itself: on a
`COMPONENT_AGGREGATE_MISMATCH` or `ST_DEBT_SCOPE_UNCERTAIN` refusal, **both disagreeing
figures and the deviation** (the methodology's "record both figures on the UNAVAILABLE
record so the disagreement is reviewable"); on a CALCULATED composite, **which components
were zero-by-absence** (the methodology's mandated recording).

Why no existing column could carry it: `reason_code` is a closed vocabulary keyed for
counting and querying — free text there would break every GROUP BY over it; `method` names
the formula, and overloading it would make equal-method rows unequal; `label` is the SEC's
reported label, reserved for REPORTED provenance; and `data_quality_events` rows are
pipeline judgements about a period, not attributes of one stored value — putting per-row
figures there would detach the evidence from the row it explains.

Timing: the need only became concrete when Task 9 implemented the refusal paths — Task 8's
design predated D26's "record both figures" being exercised by real code. The column
arrived inside the Task 9 feature commit (`005bb0b`); this entry exists so its origin is
findable without reading that commit.

**Standing preference going forward: schema changes get their own DECISIONS entry, even
small ones.** `docs/` describes the schema, and a reader tracing a column should find a
decision, not have to excavate a feature commit's diff.

Alternatives: free text in `reason_code` (breaks counting); overload `method` (breaks
equality); a parallel events row (detaches evidence from the value). Consequences:
`detail` is display/audit text, never parsed by code — anything the engine must act on
belongs in a typed column or a reason code, not in `detail`.

## D36 — Period continuity is a day-gap between period ends, not a calendar-year step
Decision (owner-approved 2026-09-11, Task 10): two periods are consecutive when the gap
between their `period_end` dates falls in selection rule 2's existing 350-380 day window,
not when their calendar years differ by one.

Reason, measured: keying on `int(period_end[:4])` produces **8 false continuity warnings**
across the cached companies — JNJ at 2008->2010, 2012->2012, 2014->2016, 2017->2017,
2019->2021 and 2023->2023, plus two in KHC — every one a 52/53-week fiscal-calendar
artefact rather than a real gap. JNJ's FY2009 ends **2010-01-03**, so calendar 2009
contains no JNJ period end at all while calendar 2012 contains two. On the day-gap
reading: **zero false positives across all 82 consecutive pairs**, observed gaps 363-371
days, comfortably inside the window. Reusing rule 2's window also avoids inventing a
second definition of "a year" (CLAUDE.md rule 13).

**This is D19's fy-stamp trap reappearing in a new place — the third occurrence.** D19
removed the `fy` index because SEC stamps `fy` with the filing's fiscal year rather than
the fact's period; D13 derived fiscal year ends from duration facts for the same reason;
and continuity would have reintroduced the identical error through calendar arithmetic on
a date. Stated plainly for the next reader: **a fiscal-year label is not a date, and a
date's calendar year is not a fiscal year.** Treat it as a known hazard of this data
source rather than rediscovering it a fourth time.

Alternatives: calendar-year step (8 false warnings, above); the `fy` stamp itself (the
trap directly); a fixed 365-day tolerance of a few days (a bespoke window where an
agreed one already exists).
Consequences: `config/integrity.yaml` carries `continuity_window_days: [350, 380]`,
duplicating rule 2's window as a value rather than importing it — the two are
conceptually the same question asked of different objects (a fact's duration, a gap
between periods) and may legitimately diverge. A test pins a real 52/53-week sequence so
the finding is defended by test rather than by argument.

**Status note (2026-09-17):** the counts above were **measured at five companies** (F,
JNJ, LUMN, CCL, KHC), before the 43-company universe was adopted (D67). The reasoning is
unaffected; the evidence statement is provisional. **Re-measure before relying on any
count here.**

## D37 — Integrity results get their own table, not data_quality_events
Decision (owner-approved 2026-09-11): integrity check outcomes are rows in a new
`integrity_results` table — `(cik, period_end, check, outcome, detail, lhs, rhs,
deviation, config_fingerprint, created_at)` with a unique index on
`(cik, period_end, check)`. The per-period verdict is **derived in a query, never
stored** (rule 13: storing it would encode the same invariant twice, and the derivation —
FAIL if any check failed, else WARN if any warned, else PASS — is trivial). Task 8's
design note said these would be `data_quality_events` rows; that note is superseded.
Abnormal movement **stays** in `data_quality_events` under D23's three existing codes:
those are genuinely per-concept events, already specified that way, and warn-only.

Reason 1 is decisive: **scoring must read the verdict programmatically, and the events
table has nowhere structured to put it.** It has no outcome column and no numeric
columns; the only home for a pass/fail plus two figures would be `detail` — which D35
fixed, one week earlier, as display text *never parsed by code*. Routing the scoring gate
through free text would break that boundary immediately after drawing it.
Reason 2: PASS rows would be non-events — seven checks across ~88 periods is ~600 rows of
"nothing happened" in a table whose purpose is surfacing judgements, which is exactly the
failure CLAUDE.md rule 12 names (the unit fix cured the same shape at 3,845 markers).
Reason 3: idempotency has no key — events dedupe by whole-row match, while an integrity
result needs the natural key `(cik, period_end, check)` so a re-run updates rather than
accumulates.

Alternatives: force it into `data_quality_events` (all three reasons above); store the
period verdict as a column (rule 13); put only failures in events and drop passes
(loses the evidence-versus-gap distinction that makes witness coverage measurable).
Consequences: `store/queries.py` gains the verdict derivation; Phase 6 reads the table,
not free text.

**Status note (2026-09-17):** the counts above were **measured at five companies** (F,
JNJ, LUMN, CCL, KHC), before the 43-company universe was adopted (D67). The reasoning is
unaffected; the evidence statement is provisional. **Re-measure before relying on any
count here.**

## D38 — Integrity thresholds live in config/integrity.yaml, outside the D18 fingerprint
Decision (owner-approved 2026-09-11): `balance_sheet_tolerance` (0.01),
`abnormal_movement_threshold` (3.0) and `continuity_window_days` ([350, 380]) live in a
new `config/integrity.yaml`, not in `config/composites.yaml`.

Reason: `composites.yaml` is fingerprinted under D18 because its keys change **concept
values** — `include_operating_leases` moves `total_debt`, `component_aggregate_tolerance`
decides whether it computes at all. Integrity thresholds change **verdicts, not values**.
Folding them into the fingerprinted file would move every concept row's fingerprint
whenever a tolerance changed, falsely implying the stored value should have moved — the
precise misreading D18's scope note exists to prevent, and the same disjointness argument
it makes for Phase 6's score fingerprint.
Alternatives: add to composites.yaml (above); hard-code (CLAUDE.md rule 6).
Consequences: integrity rows carry the config fingerprint in force when written, but that
fingerprint covers the composites config, not these thresholds — a Phase 6 integrity
fingerprint, if one is ever needed, is its own function over this file.

## D39 — Two small integrity-check specifics: zero denominator skips, and current-subset splits
Decision (owner-approved 2026-09-11):

**(a) Zero or negative `total_assets` skips the balance-sheet check** rather than dividing.
The methodology's rule divides by `total_assets`, and the general rules already say a zero
denominator yields `UNAVAILABLE`/`ZERO_DENOMINATOR` rather than a misleading number
(CLAUDE.md rule 4). The outcome is SKIP with that reason — the check could not run, which
is a data gap, not a violation.

**(b) "Current subset of total" is two checks, not one.** The methodology's single table
row covers `current_assets <= total_assets` and `current_liabilities <= total_liabilities`
— independent comparisons whose inputs resolve independently, so one can pass while the
other skips. Stored as `current_assets_subset` and `current_liabilities_subset` so an
outcome is never ambiguous about which comparison produced it. A cosmetic departure from
the table's seven rows, making eight stored checks; the methodology's table is amended to
show both.

Consequences: SKIP is a first-class outcome alongside PASS/WARN/FAIL precisely so these
cases are distinguishable — a company whose inputs never resolved must not look as clean
as one that genuinely passed (the evidence-versus-gap split of D9).

## Open question for Phase 6 — "excluded from scoring until reviewed" has no review mechanism
Raised at Task 10, deliberately not resolved there. The methodology says a period failing
an integrity check is stored, marked `integrity = FAIL` and "excluded from scoring until
reviewed". There is no review mechanism anywhere in v1: no reviewed flag, no integrity
override path (the `overrides` table covers values, not verdicts), and nothing that can
move a period from FAIL back into scoring. Task 10 therefore stores the verdict and
stops; the exclusion itself belongs to Phase 6, where scoring exists.

**Phase 6 must choose:** build a review mechanism, or amend the methodology to say the
exclusion is permanent absent a manual data fix and re-ingest. Inventing one at Task 10
would have been a scoring decision made in the wrong task.

## D40 — Continuity iterates over trend-eligible periods only; phantom periods still get every other check
Decision (owner-approved 2026-09-11, Task 10): `period_continuity` runs over periods with
**at least one resolved concept**. A period where nothing resolved is SKIP with
"not a trend period" and is not a link in the chain. Every other check still runs on it,
all skipping, so the period is recorded rather than hidden.

**The methodology reading that decides it — this is the rule as written, not an exception
to it.** The check is specified "consecutive fiscal years with no gap **for trend use**".
Trends operate on concept values. A period with zero resolved concepts therefore cannot be
a trend period, and asking whether it is contiguous with its neighbours is asking a
question the rule does not pose.

Measured: **3 false warnings removed, 0 true ones** — LUMN `2013-12-31 -> 2014-02-20`
(51 days) and `2014-02-20 -> 2014-12-31` (314 days), KHC `2013-04-28 -> 2014-12-28`
(609 days). These were the **only** continuity warnings in the entire cached set, so the
check went from 100% false-positive to silent on data that is in fact continuous: LUMN's
2013 and 2014 fiscal years are 365 days apart.

**Why the phantom periods exist, and why D17 stays intact.** Each comes from a single tag
*outside* `tag_map.yaml` that happens to carry an annual-length duration — LUMN's
`StockRepurchasedDuringPeriodValue` (2013-02-13 to 2014-02-20, 372 days) and KHC's
`TreasuryStockValueAcquiredCostMethod`. Mapping enumerates the period deliberately, under
D17's rule that an odd-period fact is never dropped silently, and produces 34 UNAVAILABLE
rows. That rule is left untouched: **the right place to decide a period is irrelevant to
trends is the check that cares about trends, not the layer that records what was filed.**

**Topology worth carrying forward:** continuity is the first check whose inputs are *other
periods* rather than values within a period, which is why one junk period does
disproportionate damage here and nowhere else — sitting between two real periods, it
breaks the chain twice. **Checks over sequences amplify bad members; checks over single
rows contain them.** This applies directly to Phase 7 (trends and early warnings), which
is entirely sequence-based: every rule there should be asked which periods it treats as
links before it is implemented.

**Fourth appearance of one shape:** trusting an enumeration rather than asking what each
element represents. D19 (the `fy` stamp is the filing's year, not the fact's), D13 (fiscal
year ends derived from duration facts rather than labels), D36 (a date's calendar year is
not a fiscal year), and now a period end that is not a reporting period at all. Treat
"what does this element actually represent?" as the standing question for any enumeration
in this data source.

Alternatives: keep the warnings (100% false, above); drop zero-value periods at mapping
(contradicts D17's no-silent-drop and would hide them from every other check too); exclude
phantom periods from all checks (loses the honest record that a period exists about which
nothing is known).
Consequences: abnormal movement also iterates trend-eligible periods, for the same reason
— a phantom period between two real ones would otherwise suppress every year-on-year
comparison across it. Tests pin both the exclusion and the non-hiding.

## D41 — Ratio edge specifics, and reason kind stays a Python mapping
Decision (owner-approved 2026-09-11, Task 11). Six calls, five of them small, one of them
about where a classification lives.

**(a) `reason_kind` is a Python mapping, not a stored column.** D9 makes the
evidence-versus-gap split load-bearing for Phase 6: an evidence reason scores 0 in the
worst band, a gap is dropped and caps the grade. One authoritative `REASON_KIND` mapping
in `metrics/ratios.py` classifies every reason code; nothing is stored.
Reason: the kind is fully derivable from `reason_code`, so a column is D30's rejected
shape — a second copy that can only drift — and CLAUDE.md rule 13. The SQL-consumer
argument is hypothetical: no such consumer exists. D37 stored a verdict because a
programmatic gate had genuinely nowhere structured to live; here the structure already
exists in `reason_code`, and the mapping is a lookup away. If Phase 6 wants it in SQL,
add it then — the mapping makes that trivial.
**Three kinds, not two:** EVIDENCE (`NEGATIVE_EBITDA`, `NEGATIVE_EARNINGS`), GAP
(`MISSING_INPUT:*`, `INTEREST_MISSING_WITH_DEBT`, `ZERO_DENOMINATOR`,
`NEGATIVE_DENOMINATOR`), and NEITHER — `NO_INTEREST_NO_DEBT`, which the methodology
treats as an unlevered company whose category weight is redistributed with no grade cap.
Collapsing that third kind into GAP would cap the grade of a company for being
debt-free.

**(b) Interest missing while `total_debt` is UNAVAILABLE → `MISSING_INPUT:total_debt`.**
The coverage table covers `total_debt == 0` and `> 0` only, and neither fits: we cannot
say "no debt" or "debt present". A gap about the gate, not a claim about the company.

**(c) The interest gate runs before the earnings check — for a substantive reason, not
table row order.** When `ebit <= 0` and interest is missing or zero with debt present,
both rules apply. A missing denominator means the ratio was **never computable**;
negative earnings is a statement **about a ratio you could have computed**. The evidence
claim presupposes a working comparison, so the gap is reported first.

**(d) `ebitda == 0` keeps `NEGATIVE_EBITDA`.** The rule is `ebitda <= 0`, so zero takes
this code despite the name. Kept rather than renamed — the code names the **band**
(worst), not the sign, and zero EBITDA belongs in that band for the same reason negative
does: a company that cannot cover any debt from earnings. Documented in the methodology
so the next reader does not read it as a bug.

**(e) `NEGATIVE_DENOMINATOR` is emitted as a `data_quality_events` row.** The general
rules say the negative denominator is "itself surfaced as a warning" but name no code and
nothing emitted one. It follows Task 10's split: a per-value warning is an event, while a
check outcome is an `integrity_results` row (D37).

**(f) Negative `interest_expense` is treated as the zero case.** Not covered anywhere in
the methodology. A negative interest expense is a tagging artefact, not free money, so it
takes `INTEREST_MISSING_WITH_DEBT` rather than producing a negative coverage ratio.

Consequences: all six are written into `docs/credit-methodology.md`, not left here.
Measured witness note: five of the seven coverage edge cases have **zero** real-data
witnesses and are synthetic-only — `interest_expense` resolves positively in all 87
cached company-periods, `total_debt` is never exactly zero, and `current_liabilities` is
never zero or negative. Recorded in PROJECT_STATE.md beside Task 10's witness table.

**Status note (2026-09-17):** the counts above were **measured at five companies** (F,
JNJ, LUMN, CCL, KHC), before the 43-company universe was adopted (D67). The reasoning is
unaffected; the evidence statement is provisional. **Re-measure before relying on any
count here.**

## D42 — Five calls completing Phase 5's metric set
Decision (owner-approved 2026-09-12, Phase 5 completion). The remaining fourteen ratios
follow Task 11's pattern unchanged; these five points were underdetermined by the
methodology and are settled here and in the doc.

**(a) `NO_DEBT` is kind NEITHER, the same shape as `NO_INTEREST_NO_DEBT`.** An unlevered
company cannot have a debt ratio, and that is a good thing, not a shortfall. Classifying
it GAP would cap the grade of a debt-free company — precisely the bug the three-kind
split of D41a exists to prevent. Applies to `cash_to_debt`, `fcf_to_debt` and
`cfo_to_debt`.
**Open question for Phase 6, deliberately not answered here:** the methodology specifies
weight redistribution for `NO_INTEREST_NO_DEBT`, a single coverage metric, but says
nothing about **three separate leverage and cash-flow metrics all returning `NO_DEBT`
simultaneously**. Whether that redistributes three weights, collapses a category, or means
something else is a scoring decision; inventing it here would be a Phase 6 rule made in
the wrong phase.

**(b) `quick_ratio`'s cross-period inventory test uses the resolved-concept reading.**
"Reports no `InventoryNet` tag in any period" means no `inventory` concept resolves in any
period — not the tag's presence in the raw companyfacts payload. The payload reading would
let an unselected quarterly-only fact silently flip a company into "has inventory",
letting the metric see data that selection deliberately excluded.
Measured consequence: all five cached companies carry `InventoryNet` in the payload, so
none is a non-inventory business under either reading; but **LUMN resolves `inventory` in
only 2 of its 18 periods, so 16 go `UNAVAILABLE`**. That is the correct conservative
outcome — subtracting an unknown inventory from current assets would fabricate a number —
even though it makes the metric near-useless for a telco.
This is the only rule in the metric table whose per-period answer depends on other
periods. It needs no new pipeline structure: `compute_metrics` already receives the whole
`MappingResult`, so company-wide knowledge is in hand; it is isolated in one function
rather than threaded through as a flag.

**(c) `revenue_growth` pairs periods only within `continuity_window_days`, else
`INSUFFICIENT_DATA`.** Adjacent-in-the-list is not adjacent-in-time: JNJ resolves
`revenue` in 10 of 19 periods, so naive pairing of consecutive revenue-resolving periods
would compute a multi-year change and label it one-year growth — a plausible-looking wrong
number, which rule 9 forbids. D36's window is reused rather than a new threshold invented.
**This is D40's sequence-topology hazard arriving a phase earlier than expected.** D40
noted that checks over sequences amplify bad members while checks over single rows contain
them, and flagged Phase 7 as entirely sequence-based. `revenue_growth` is the first metric
of that shape, and the same question — *which periods count as links?* — must be asked of
every trend rule in Phase 7 before it is implemented.
**Amended by D43 (2026-09-12):** this entry specified the *window* and cited D40, but the
implementation it produced applied the window **without** D40's eligibility filter, losing
a legitimate LUMN value to a phantom period. Read D43 before implementing anything from
this clause: the rule is eligibility **and** window, not window alone.

**(d) `ebitda_interest_cover` with `ebitda <= 0` carries `NEGATIVE_EBITDA`, kind
EVIDENCE.** Neither coverage-table row fits exactly: `NEGATIVE_EARNINGS` is specified for
`ebit <= 0`, and `NEGATIVE_EBITDA` for EBITDA-based *leverage*, while this is EBITDA-based
*coverage*. The code that names the input which actually failed is the right record. The
kind is EVIDENCE under either code, so nothing in scoring turns on the choice.

**(e) A negative-revenue period produces both an integrity `FAIL` and a metric
`NEGATIVE_DENOMINATOR` refusal, and this is not double-counting.** Stated explicitly so a
later reader does not try to deduplicate them: **the check asks whether the data is
possible; the metric asks whether it can be computed.** They are different questions about
the same fact, and both answers are wanted — one marks the period unfit for scoring, the
other explains why a particular number is absent. Zero witnesses in the cache.

**Status note (2026-09-17):** the counts above were **measured at five companies** (F,
JNJ, LUMN, CCL, KHC), before the 43-company universe was adopted (D67). The reasoning is
unaffected; the evidence statement is provisional. **Re-measure before relying on any
count here.**

## D43 — revenue_growth pairs on eligibility AND window; citing a decision is not implementing it
Decision (pre-Phase-6 audit, finding 2, 2026-09-12): `revenue_growth` pairs each period
with **the most recent prior period that actually resolves `revenue`**, and then applies
D36's `continuity_window_days` test to *that* pair. Previously it paired with `ends[i-1]`
— whichever row happened to precede — and applied the window to that.

Reason: the two rules answer different questions and both are needed. **Eligibility**
(D40) asks *which periods are links in the chain*; a period resolving no concepts is not
one. **The window** (D42c/D36) asks *whether an eligible pair is close enough in time*.
Applying only the window makes a phantom period swallow a legitimate comparison; applying
only eligibility would let a genuine five-year gap pass as one-year growth.

Measured: LUMN's phantom `2014-02-20` sits between `2013-12-31` and `2014-12-31`, which
are **365 days** apart. The old pairing compared `2014-12-31` against the phantom, found
no revenue, and returned `INSUFFICIENT_DATA` — **losing one of 17 available values**.
LUMN now produces 17 of 17. Nothing else moved: F 18, JNJ 9, CCL 13, KHC 0 are unchanged,
and CCL's one rejected pair is a genuine 1,826-day gap (2009 to 2014) that must stay
refused. Both directions are now pinned by test.

**The lesson, which matters more than the fix.** D40 established phantom-period
exclusion and stated the sequence-topology hazard explicitly. D42c then **named
`revenue_growth` as the first metric inheriting it** — and the implementation still
reused D36's window without D40's eligibility filter. The decision was cited, understood
and written down, and the code was wrong anyway.

**Citing a decision is not the same as implementing it.** A reference to a prior decision
records that its existence was noticed; only an assertion records that its *content* was
applied. **Phase 7 is entirely sequence-based**, and every trend rule there must apply
the eligibility filter as well as the window — the check being, for each rule: *which
periods does this treat as links, and is a period that resolves nothing one of them?*
That question is to be answered per rule, in a test, not by citing D40 or this entry.

Alternatives: drop phantom periods at mapping (contradicts D17's no-silent-drop, and D40
rejected it for the same reason); apply eligibility without the window (admits real gaps).
Consequences: `compute_metrics` computes the eligible-prior list once per company;
`_revenue_growth` receives an already-filtered `prior_end` and keeps the window test,
so the two rules stay visibly separate in the code rather than merged into one condition.

## D44 — The three superseded ratio helpers are deleted; rule 13's failure observed in miniature
Decision (pre-Phase-6 audit, finding 3, 2026-09-12): `_net_debt_to_ebitda`,
`_ebit_interest_cover` and `_current_ratio` are removed from `metrics/ratios.py`. They
were Task 11's originals, superseded during the Phase 5 completion by `_ebitda_ratio`,
`_interest_cover` and `_simple_ratio`, and left in place with zero call sites.

Reason: CLAUDE.md rule 13. The `NEGATIVE_EBITDA` gate, the interest gate and the general
denominator rules each existed in two places.

**Worth recording because the divergence had already happened, in rule 13's mildest
possible form:** the two copies still agreed on every *reason code* — the thing tests
assert — and disagreed on *payload*. The live `_simple_ratio` carries the offending figure
on a `NEGATIVE_DENOMINATOR` refusal (`('current_liabilities', -5)`); the dead
`_current_ratio` returned `None`, so a warning raised through it would have lost its
number. **That divergence appeared within a single phase**, between the commit that
introduced the shared shapes and the audit days later, with no one editing either copy
deliberately — it arose because only one copy was updated when the `denominator` field was
added.

The generalisable point: duplicated logic does not announce itself by disagreeing on the
obvious thing. It agrees on what the tests check and drifts on what they do not, which is
why "the copies still behave the same" is not a reason to keep them.

Consequences: 64 lines removed, suite unchanged, `metrics/ratios.py` branch coverage
82% -> 100%.

## D45 — Scoring engine: five component treatments, one category-outcome rule, three questions closed
Decision (owner-approved 2026-09-12, Phase 6 design). The scoring engine lives in
`scoring/engine.py` and consumes stored-shape metric and integrity results.

**Spec check first:** `config/thresholds.yaml` and `docs/credit-methodology.md` were
compared number by number before designing — weights, both documented band tables, all six
grade boundaries, and the banded-metric list. **They agree.** The methodology's "rescaled
over the available categories" (GAP) and "weight redistributed pro rata" (NEITHER) are the
same arithmetic — `sum(category_scores) / sum(available_weights) * 100` — so one mechanism
is implemented and the two *causes* are recorded separately. Two mechanisms would be the
same duplication rule 13 forbids.

**Five component treatments, not three.** D41's kinds drive behaviour; two further states
exist that no kind covers:

| Treatment | When | Effect on the category mean |
|---|---|---|
| `scored` | metric computed | band points |
| `evidence_zero` | EVIDENCE reason | **0 points, counted** — never dropped |
| `dropped_gap` | GAP reason | excluded; marks the category gap-touched |
| `dropped_unlevered` | NEITHER reason | excluded; benign |
| `not_yet_implemented` | `ebitda_margin` trend, until Phase 7 | excluded from all counting |

`not_yet_implemented` exists because treating an unbuilt feature as a GAP would cap every
company in every period for something that does not exist yet. The row is still written so
the output shape does not change when Phase 7 fills it.

**Category-outcome rule, stated precisely because this is where the phase's complexity
lives:**
- One or more components `scored` or `evidence_zero` -> the category scores, as the mean
  of exactly those components. A `dropped_gap` beside an `evidence_zero` changes nothing.
- No such components -> the category is **absent**, and its cause is **GAP if any
  component was `dropped_gap`, else NEITHER**. Reason: D10's cap exists so that partial
  data cannot show "Very strong". A category absent purely because the company is
  unlevered is not partial data; one where even a single gap contributed might have shown
  something, so fail-safe caps.
- **Cap and redistribution together:** one rescale over the scoring categories, and the
  cap applies once, from the GAP-caused absence. The cap is a ceiling, never stacked.
- Every absent category is named in the output with its cause.

**Consequence ratified by the owner:** every company's first period is capped, because
`revenue_growth` is `INSUFFICIENT_DATA` (a GAP) and it is business performance's only
Phase 6 component. Growth genuinely unknown is partial data, so the cap is correctly
caused; it is visibly attributed rather than silent.

**Open question 1 — "excluded until reviewed" — closed by amending the methodology.**
A period failing an integrity check is excluded from scoring **until the underlying data is
corrected and re-ingested**; v1 has no interactive review path. A FAIL period gets no score
row at all. Reason: the `overrides` table is value-scoped by design, so a verdict override
would need a new table and a new workflow for a state that occurs **zero times** across all
89 cached company-periods — speculative machinery, which rule 9 rules out. A review
workflow is a v2 feature with its own design if ever wanted.
Alternatives: build a `verdict_overrides` table now (rejected above); score FAIL periods
and mark them (rejected — the methodology is explicit that they are excluded).

**Open question 2 — NO_DEBT redistribution — closed by the component rule, with no special
mechanism.** `fcf_to_debt` returning `NO_DEBT` is a `dropped_unlevered` *component*; cash
flow then scores on `fcf_margin` alone. Only if `fcf_margin` were also absent would the
category question arise, and the category-cause rule above already answers it. The audit's
narrowing holds: `NO_DEBT` fires zero times across all 89 cached company-periods and only
`fcf_to_debt` is a scoring metric. No category-level `NO_DEBT` rule exists to drift.

**Open question 3 — score fingerprint — confirmed, with an explicit allowlist.**
`scoring/fingerprint.py::score_fingerprint()` covers exactly `weights`, `bands` (every
metric's edges, points and direction), `grades`, and the graduated cap settings. It
excludes `trend_materiality` and `warning_escalation_count`: those change trends and
warnings, not scores, and including them would orphan score history on every Phase 7
tuning — the same disjointness D18's scope note requires. The score row stores this
fingerprint only; the composite fingerprint in force is reachable through the period's
metric rows, so reproducibility needs no second column.

**Two smaller readings settled in the methodology rather than in code:**
(a) **"Primary" is dropped from the band table.** Within leverage, `debt_to_capital`
counts equally with `net_debt_to_ebitda` in the plain mean — that is what "mean" says. The
label implied a weighting the spec never defines; the fix is to remove the label, not to
invent the weighting.
(b) **Grade boundaries are half-open intervals on the config's lower bounds** — `[70, 85)`
is grade 2, so 84.9 is grade 2. Stated explicitly because the documented table's integers
could be misread as truncation.

## D46 — The grade cap is graduated by how many categories were scored
Decision (owner call, 2026-09-12): the missing-category cap depends on **N**, the number of
categories that actually scored. `config/thresholds.yaml` carries
`max_grade_by_categories_scored`: **N <= 2 caps at grade 4**, **N = 3-4 caps at grade 3**
(the previous single `max_grade_with_missing_category` value becomes the 3-4 entry). N = 5
is uncapped.

Reason: a 2-of-5 score presents with the same authority as a 4-of-5 score, which overstates
its confidence. A minimum-N floor would refuse to score and lose the information entirely; a
graduated cap keeps every period scoreable while making the confidence difference visible
**in the grade itself**, not only in a caveat a reader may skip.

Witness: **CCL 2007-11-30** scores 60.0 on **2 of 5** categories — leverage, liquidity and
business performance all absent. Under the flat cap it presented as grade 3, the same grade
CCL earns in 2015-2019 on all five categories. Under the graduated cap it is grade 4, and
the difference between a well-evidenced 3 and a thin 3 is legible without reading the
caveat.

Alternatives: a minimum-N floor, e.g. no score below N=3 (rejected — refusing discards a
real if thin signal, and N is already stored and displayed); keep the flat cap (rejected
above).
Consequences: `max_grade_with_missing_category` is superseded by
`max_grade_by_categories_scored` and removed, so one setting cannot disagree with the other.
The cap value used is derived from stored `categories_scored`, never stored separately.

## D47 — Score storage amendments (schema)
Decision (2026-09-12, recorded separately per D35's standing rule that schema changes get
their own entry rather than riding inside a feature commit).

`scores` gains four columns:
- **`config_fingerprint TEXT NOT NULL`** — the score fingerprint (D45). Its absence would
  violate D18's own reasoning the moment a band edge moved: a score that changed for a
  settings reason would be indistinguishable from one that changed for a filing reason.
- **`status`** plus a partial unique index on `(cik, period_end) WHERE status='CURRENT'` —
  the methodology says scores keep their own history (D18); without this the table can only
  be deleted from or duplicated into.
- **`grade_uncapped INTEGER`** and **`cap_binding INTEGER`** — a cap that does not change
  the grade and one that does are different facts. Measured: JNJ carries 18 **binding**
  caps (uncapped 1-2, shown 3) while LUMN's caps are mostly **non-binding** (its scores are
  worse than the cap anyway). `cap_binding` is stored rather than derived because deriving
  it in every consumer is how one consumer forgets to show it.

`score_components` gains:
- **`treatment`'s CHECK extended** with `'dropped_unlevered'` and `'not_yet_implemented'`
  (D45's five treatments; the table shipped with three).
- **`reason_code TEXT`** so an UNAVAILABLE component names its reason in place, rather than
  requiring a join back to `metrics` to explain a zero or an omission.

Consequences: `grade_capped` is retained as "a cap applied at all"; `cap_binding` says
whether it changed the outcome. The databases are gitignored and rebuilt from cache, so no
migration is required.

## D48 — CCL's liquidity scores zero by sector, not by weakness: the first measured case for sector thresholds
Decision (owner call, 2026-09-12): **record, do not adjust.** The generic liquidity bands
score CCL **0 of 10 points in every one of its strong years** — measured 2019-11-30:
`current_ratio` **0.23** against a first band edge of 0.8, and
`cash_to_current_liabilities` **0.06** against a first edge of 0.1.

This is a sector effect rather than weak liquidity: cruise operators carry **deferred ticket
revenue** — cash already collected for future sailings — inside current liabilities, which
inflates the denominator of every liquidity ratio without representing a funding need.

Measured cost: CCL's 2019 total is **56.5, grade 3**. With mid-band liquidity points it
would score into grade 2. The sector effect costs a full grade at the company's peak.

Reason for recording rather than fixing: generic bands behaving conservatively on a sector
outlier is precisely what the methodology's Calibration section says they are — starting
assumptions for this project. Re-tuning a band so one demonstration company scores better
is the backwards move D26 already rejected in another form. **This is the first concrete,
measured instance justifying the post-MVP sector-specific-thresholds item**, and it now
carries numbers rather than an intuition.
Alternatives: widen the liquidity bands (rejected — fits one company, unvalidated for the
rest); exclude liquidity for cruise operators (a sector rule with no sector framework yet).
Consequences: CCL's scores are pinned in tests **as they are**, including the zero liquidity
points, so a future sector-threshold change shows up as a deliberate re-baseline.

**Second measured instance (added by D55, 2026-09-13): CCL's effective tax rate is ~0.19%**
across its two computable periods — cruise operators are taxed under tonnage regimes rather
than corporate income tax, so the statutory 21% stress default overstates their tax burden
just as the generic liquidity bands understate their liquidity. Same shape, same treatment:
a real sector property that a generic parameter handles conservatively, recorded rather than
fixed. Two independent instances now sit behind the sector-thresholds item.

## D49 — Trend classification: per-rule eligibility, change_over_window, mixed units, strict monotonicity
Decision (owner-approved 2026-09-12, Phase 7).

**Spec check:** all seven `trend_materiality` values and `warning_escalation_count` match
the methodology's tables exactly. No disagreement.

**(a) Eligibility is per rule, on that rule's own series.** A period is a link in metric
M's chain when **M itself resolves there** — a period that resolves nothing, or resolves
other metrics but not M, is not one — and a window is valid only when **every** consecutive
day-gap in it sits inside `continuity_window_days`. D40's filter and D36's window, both,
applied to the series each rule actually reads.
**This is D43 discharged, not cited.** D43 records that `revenue_growth` referenced D40's
exclusion without applying it, and that the only artefact distinguishing noticing a
decision from applying it is a test. So there are **seven eligibility tests and seven
window tests**, one per trended metric on its own series, parametrised over `TRENDED` with
a guard test that fails if a metric is added without them. A shared test would prove the
mechanism works somewhere; it would not prove it is wired to each rule.

**(b) `change_3y` is renamed `change_over_window` and means latest minus the earliest of
the three-period window.** The old name was wrong: three consecutive years give t, t-1,
t-2, so the earliest point is **two** intervals back, not three. The label implied three
intervals where the stated minimum gives two. Measured: requiring a fourth period to match
the old name would cost **12% of available windows** (309 -> 271). The name was what was
wrong, not the arithmetic.

**(c) Materiality units are mixed, and the distinction is marked in config.** Five
thresholds are absolute changes in the metric's own units; `fcf` and `total_debt` are
proportions of the base period. `config/thresholds.yaml` now lists `relative: [fcf,
total_debt]` rather than leaving a future editor to infer it from the methodology's prose.
A relative change with a **zero base** yields `INSUFFICIENT_DATA` rather than an undefined
proportion — D34's refusal shape.

**(d) Monotonic is strict.** A flat year breaks it: a stalled series is not "each year
worse than the last".

**(e) `revenue_growth`'s verdict does not mean what the other six mean.** Its trigger is
"growth < 0, **or** growth fell >= 5pp" — an absolute level test OR a change test, where
every other metric uses change alone; and because it trends a growth *rate*, its
`change_1y` is an **acceleration**. Implemented as written (the absolute clause is
deliberate: negative growth is bad regardless of direction of travel), and documented in
the methodology so output presenting the seven verdicts together does not imply they are
the same kind of claim.

## D50 — Trend verdicts score at 10/6/0, and the Phase 6 re-baseline that follows
Decision (owner call, 2026-09-12): `config/thresholds.yaml: trend_points` maps
**Improving 10, Stable 6, Deteriorating 0**. `INSUFFICIENT_DATA` is not in the mapping —
it is a data gap, not a verdict, and scores as `dropped_data_gap`.

Reason for 6 rather than 5: **Stable belongs just above the midpoint.** Holding steady is
better than drifting, and mid-band values elsewhere are reserved for genuinely middling
performance.
`trend_points` joins the **score** fingerprint, not the trend fingerprint: the boundary is
"does this move a score", and a verdict-to-points mapping does. This corrects the Phase 6
reasoning, which had assumed everything trend-shaped belonged outside.

**The re-baseline, measured and deliberate.** `ebitda_margin_trend` moved from
`not_yet_implemented` (excluded from counting) to a real component, so business performance
became a mean of two rather than one. **Nine of 85 grades moved:**

| Company | Moved | Before -> after |
|---|---|---|
| LUMN | 6 | 3x2 4x2 5x8 6x6 -> 3x2 4x3 5x4 6x9 |
| F | 2 | 4x14 5x2 6x2 -> 4x13 5x2 6x3 |
| CCL | 1 | 3x5 4x8 5x3 6x3 -> 3x4 4x9 5x3 6x3 |
| JNJ | 0 | unchanged |
| KHC | 0 | unchanged |

CCL 2019-11-30 is the clearest case: EBITDA margin fell **2.19pp** against a 2pp threshold
in the year before COVID, so the trend scores 0 and the grade moves **3 -> 4**. That is the
component working, not a regression.

**JNJ and KHC show no grade movement but a real behavioural change**, which is why this is
recorded rather than just re-pinned: `ebitda_margin` never resolves for either, so their
trend component went from *excluded from counting* to a **data gap**. Their grades were
already capped for other reasons, so the change is invisible in the grade and visible only
in `score_components.treatment`. A change that moves no number is still a change.

## D51 — Warnings gain an escalation cause; evidence stays concept-linked
Decision (2026-09-12, recorded separately per D35's standing rule for schema changes).

`warnings` gains **`escalation_reason TEXT`** and **`warnings_in_period INTEGER`**, with a
CHECK that `escalated = 1` implies both. The methodology requires recording that escalation
applied **and why**; the table could record only that it applied. The stored reason names
the count that fired and the threshold that triggered it. A unique index on
`(cik, period_end, indicator)` makes a re-run update rather than accumulate.

**Evidence stays linked to `concepts`, and no `warning_metrics` table is added.** A
metric-triggered warning cites the **concepts that fed the metric**, reachable through
`metric_inputs`. The property that matters is that provenance bottoms out in facts and
filings, and it does; a direct warning-to-metric link buys faithfulness already reachable
by join. Revisit only if Phase 9's evidence export needs it.

## D52 — Warnings carry a trend fingerprint, disjoint from the score fingerprint
Decision (2026-09-12): `trends/fingerprint.py` covers `trend_materiality` and
`warning_escalation_count`, and every warning row stores it.

Reason, the same argument D38 makes for integrity thresholds: **a warning that stopped
firing because a threshold moved must be distinguishable from one that stopped because the
company improved.** Only a fingerprint on the row can tell them apart.
It is disjoint from D45's score fingerprint because these settings change *which warnings
fire*, not what a score is — with the single exception of `trend_points`, which moves
scores and therefore belongs to the score fingerprint (D50). The boundary is "does this
move a score", not "does this live in thresholds.yaml".
Consequences: three fingerprints now exist with disjoint scopes — composites
(`store/fingerprint.py`), scores (`scoring/fingerprint.py`) and trends
(`trends/fingerprint.py`). Integrity thresholds deliberately have none (D38): no integrity
row's value moves with them, only its verdict, and the verdict is recomputed from scratch
each run.

## D53 — Stress config settled: fixed_cost_share stays 0.3 with visibility duties; new_debt_rate gets a sanity band
Decision (owner-approved 2026-09-12, Phase 8 step one — design and measurement only; the
engine and the D20-deferred tables remain unbuilt). Measured across the 42 company-periods
that can run both EBITDA modes (LUMN 18, CCL 15, F 9), at the Moderate and Severe presets,
with `fixed_cost_share` swept over {0.2, 0.3, 0.5, 0.7}. The mode-B-at-zero identity
(B with fcs=0 reduces algebraically to mode A) was asserted per period, so the measurement
implements the propagation rules faithfully.

**(a) `fixed_cost_share` stays 0.3 globally, overridable per custom scenario, and every
operating-leverage output must print the value used.**

Measured basis: across the whole plausible range [0.2, 0.7], the stressed grade moves by
at most **one level** in any period, and by **two or more in zero periods** — so the
two-level alarm (stress output becoming a statement about the assumption) does not fire,
and no choice inside the range is materially better-protected than another.

**The honest reason, stated plainly: the grade swing is bounded at one level not because
the assumption is unimportant but because the grade scale is coarse and stressed grades
cluster at 5-6.** The sensitivity lives in the stressed figures: CCL 2019 Severe swings
stressed EBITDA **2.90bn -> 1.36bn** across the range (mode A: 3.52bn), and LUMN 2019
Severe **flips sign** inside it (+0.05bn at 0.2, -1.89bn at 0.7). Hence the visibility
duty: the number is printed inline in every operating-leverage output, not only recorded
in the assumption register.

Also recorded: 0.3 is a **mild** setting — it assumes 70% of costs are variable — and is
likely conservative-light for the asset-heavy names in this set. Mode B is never milder
than mode A in any measured cell, and the mode choice alone flips CCL 2019 Severe from
grade 5 to 6. **Per-sector values join D48's existing sector-thresholds item** rather than
being invented for a five-company set.

**(b) `new_debt_rate` becomes a three-part structure:** explicit `new_debt_rate` override
(null by default) -> the implied rate `interest_expense / total_debt` **if it falls inside
`new_debt_rate_band: [0.02, 0.12]`** -> else `new_debt_rate_default: 0.06`. Every
substitution is surfaced in the stress output, naming which rate was used and why, and
recorded in the assumption register.

**Both failure directions occur in-sample, which is what justifies a band — either alone
would have motivated only a value.** Ford's implied rates are **287-860%** (D25's captive
finance: enterprise-wide interest over a 2018-2020 sliver of resolvable debt); JNJ's
2021-2023 implied rates are **0.51-0.67%**, a ZIRP-era legacy average that would price NEW
stress borrowing at half a percent, understating the cost of exactly the debt a stress
scenario adds. 59 of 65 measured periods sit comfortably inside the band; 6 fall outside,
in both directions. The default 0.06 is deliberately above the 4.12% in-sample median:
debt raised in a stress scenario does not price at the portfolio's calm-times average.

**(c) Presets keep `additional_debt: 0`, deliberately.** Incremental borrowing under
stress is real but company-specific; a preset carrying it would encode a view about how
much a given company borrows in a downturn, which a global scenario cannot assert. It
stays a custom-scenario lever, and the methodology now says so, so the absence reads as a
design choice rather than an omission. Consequence: the new_debt_rate machinery is
exercised only by custom scenarios until an owner chooses otherwise.

**(d) Two propagation gaps written into the methodology rather than left to
implementation:** missing `tax_expense` or `pretax_income` falls back to
`default_tax_rate`, recorded as ASSUMED — the same treatment as the pretax <= 0 case
already specified; and both EBITDA modes run correctly from a negative base margin,
producing deeper-negative stressed EBITDA -> NEGATIVE_EBITDA evidence -> grade 6, so that
path reads as designed rather than incidental.

**(e) Structural finding for PROJECT_STATE: stress is impossible for JNJ and KHC.** Both
modes need `revenue` and `ebitda` in the same period; JNJ's never overlap and KHC has no
revenue. The metric-coverage gap propagates into Phase 8: two of five demonstration
companies cannot be stress tested at all.

Alternatives: raise fixed_cost_share to 0.5 for conservatism (buys <= 1 grade, measured;
rejected as tuning without evidence); per-sector fixed_cost_share now (a sector framework
for five companies); a bare new_debt_rate default without a band (fixes Ford's direction
or JNJ's, not both); presets with additional_debt > 0 (encodes a company-specific view
globally).
Consequences: config keys exist ahead of the engine, like D26's tolerance did — the YAML
notes Phase 8 wires them. The stress engine's output duties (print fcs; name the rate
used) are design requirements recorded before the code exists.

## D54 — floating_share stays 1.0, but "conservative simplification" was the wrong justification
Decision (owner-approved 2026-09-13, Phase 8 step one part two): `floating_share` stays at
**1.0**, the methodology's justification is **replaced**, and every stress output must
**print the value used** — the same duty D53a gives `fixed_cost_share`.

**Why the justification changed rather than the value.** The methodology called 1.0 a
conservative simplification because the floating/fixed split "isn't reliably available from
XBRL". Measured, that is both understated and mis-framed:

*It is not merely unreliable — it is unreachable.* Across all five cached payloads
(360-666 us-gaap tags each): **zero** `FloatingRate`/`VariableRate` tags anywhere, one
`FixedRate`-family tag in KHC, and **no USD-denominated rate-split amount in any company**.
The split cannot be derived from companyfacts at all, so per-company values would need a
non-XBRL source and are out of v1 scope. That is a measurement, not an assumption.

*And 1.0 is not cheap conservatism.* Unlike `fixed_cost_share`, where no period moved a
grade, `floating_share` at 1.0 versus 0.3 **changes the stressed grade in four measured
periods**, and not in the saturated tail: CCL 2015-11-30 and 2018-11-30 both move
**grade 3 -> 4** at Severe, CCL 2014-11-30 moves 5 -> 6, and LUMN 2011-12-31 moves 5 -> 6
at Moderate. Median interest uplift at 1.0 is +29% (CCL Moderate) to +58% (CCL Severe).
So at Severe the parameter is an active assertion that 100% of the debt reprices within the
year — for a cruise operator with a largely fixed-rate bond stack, unlikely — and it costs
CCL a full grade in two of its strongest years.

Ford shows the opposite extreme: +0.3% interest uplift, because its debt barely resolves at
all (D25). The parameter does nothing there.

Reason to keep 1.0 regardless: the data forces the simplification, and the honest response
to a forced assumption that moves grades is **visibility**, not a different invented number.
Alternatives: lower the default to 0.5 (invents a split the data cannot support, and is
less conservative for no evidential gain); derive per company (unreachable, measured above).
Consequences: the print duty is a design requirement recorded before the engine exists,
alongside D53a's.

## D55 — default_tax_rate stays 0.21 on statutory grounds, not empirical ones
Decision (owner-approved 2026-09-13): `default_tax_rate` stays **0.21**, the US federal
corporate rate, and the reasoning is recorded explicitly **because the measurement appears
to contradict it**.

Measured effective rates (`tax_expense / pretax_income` where `pretax > 0`), 39 computable
periods: median **16.31%**, mean **6.20%**, and **10 of 39 (26%) outside [0, 50%]** —
including -220.79% (KHC 2024), -157.22% (LUMN 2017), -132.95% (F 2011) and +206.70%
(LUMN 2013). CCL's two computable periods sit at ~0.19%.

**Recorded so that "measured median 16%, default 21%" does not read as an error:** the
in-sample distribution is dominated by **loss carry-forwards, one-off tax benefits and
sector regimes** — exactly what a stress scenario must *not* project forward. A stressed
period asks what the company would pay on stressed profit, and the statutory rate is the
right kind of number for that question. Adopting the 16.31% median would be **fitting five
companies' tax accidents**, and the mean is worse still: at 6.20% it is below every
plausible statutory rate because loss years drag it down.

**This default is the dominant path, not an edge case:** it is reached in **48 of 87
periods (55%)** — 14 where `pretax_income <= 0` and 34 where the tax inputs are missing
entirely (D53d added the second). A poor default here has far broader effect than
`new_debt_rate`'s, which is currently unreachable (D53c).

**CCL's ~0.2% is a genuine regime effect, not noise** — cruise operators are taxed under
tonnage regimes rather than corporate income tax. It joins **D48's sector-specific
thresholds item** alongside the liquidity finding: the same shape, a real sector property
that a generic parameter handles conservatively, recorded rather than fixed.
Alternatives: use the in-sample median (fits tax accidents, above); use the mean (6.20%,
below any statutory rate); per-sector rates now (D48's item, not a five-company decision).

## D56 — Stress fingerprint covers policy keys only; per-run assumptions are columns, not a config version
Decision (owner-approved 2026-09-13): `stress/fingerprint.py` covers exactly **`presets`,
`sensitivity_grid`, `default_tax_rate`, `new_debt_rate_default`, `new_debt_rate_band`**.
The per-run values — **`ebitda_mode`, `fixed_cost_share`, `floating_share`, the resolved
`new_debt_rate` and why it was chosen** — are **columns on the stress-run row**, not
fingerprinted.

**The principle, which is new and generalises: a value that varies per run is not a config
version.** Fingerprinting one would make two runs with *different* assumptions hash
identically whenever the config file had not changed — **D52's mechanism inverted**. D52
exists so that a warning which stopped firing because a threshold moved is distinguishable
from one that stopped because the company improved; putting a per-run override in a
fingerprint would destroy exactly that distinguishability for stress. A fingerprint answers
"which policy produced this row"; a per-run column answers "which assumptions did this run
make". Conflating them loses both answers.

Storing the per-run values as columns also satisfies D53a's and D54's print duties from the
same source, so the output cannot disagree with what was actually used.

**Four fingerprints now exist with confirmed-disjoint scopes:** composites
(`store/fingerprint.py`), scores (`scoring/fingerprint.py`), trends
(`trends/fingerprint.py`) and stress (`stress/fingerprint.py`). Verified by inspection that
no key appears in two. Integrity thresholds deliberately have none (D38).
**File location is incidental to the split; blast radius is the boundary.** `trend_points`
lives in `thresholds.yaml` beside the trend settings and belongs to the *score* fingerprint
because it moves scores (D50); `default_tax_rate` lives in `stress.yaml` beside per-run
levers and belongs to the *stress* fingerprint because it is policy. Asking "which file is
this in" would have got both wrong.

## D57 — A stressed score carries the base-period trend verdict, and liquidity immobility is surfaced
Decision (owner call, 2026-09-13), settling two questions the stress engine would otherwise
resolve by implementation.

**(a) The stressed score reuses the base period's trend verdict.** A trend is *history*, and
a stress scenario is a hypothetical about one period rather than a rewritten past, so
`ebitda_margin_trend` scores under stress exactly as it does at base.
The alternative — suppressing the trend component under stress — would **drop a scored
category and trigger the grade cap (D10/D46)**, making stressed grades incomparable to base
ones for a presentational reason rather than a credit one. Comparing a capped stressed grade
against an uncapped base grade would misattribute a mechanical artefact to the scenario.
The stressed output must **say** that the trend component carries the base verdict, so the
reuse is visible rather than assumed.

**(b) The liquidity exclusion is surfaced in the stress output, not only in the doc.** The
methodology holds balance-sheet liquidity at base under stress. That means the liquidity
category — **20 of 100 weight** — scores identically in base and stressed, which **caps how
far any stressed grade can fall**. That is a material property of the result, not a footnote:
a reader comparing a base grade 3 to a stressed grade 4 should know that a fifth of the
score could not move by construction.

Consequences: both are output duties recorded before the engine exists, joining D53a's and
D54's. Step two must also measure the `fixed_cost_share` x `floating_share` **joint** worst
case — both push the same direction and were measured independently, so the combined effect
is untested.

## D58 — The three stress tables, specified (D20's deferral discharged)
Decision (owner-approved 2026-09-13, Phase 8 step two; recorded separately per D35).
D20 named `stress_runs`, `stress_results` and `stress_drivers` but never specified their
columns — deliberately, because the config that determines their shape was unsettled. It is
now (D53-D56), so this is a fresh specification rather than an amendment to a sketch.

**`stress_runs`** — one row per (cik, period_end, scenario), append-with-history with a
partial unique index on CURRENT:
- the five shock inputs (`revenue_shock`, `margin_shock`, `rate_shock_bps`,
  `additional_debt`, `capex_shock`);
- **the per-run assumptions D56 requires as columns, not fingerprint**: `ebitda_mode`,
  `fixed_cost_share`, `floating_share`, `new_debt_rate_used`, `new_debt_rate_source`
  (`explicit` | `implied` | `default_substituted`) and `new_debt_rate_reason`;
- `base_score`, `base_grade`, `stressed_score`, `stressed_grade`;
- `config_fingerprint` — the D56 **policy** fingerprint, never the score fingerprint.

**`stress_results`** — one row per (run, metric): `base_value`, `stressed_value`, `change`,
plus `data_status` and `reason_code`, so a stressed metric that refuses (negative stressed
EBITDA) records **why** instead of going null. Same evidence-versus-gap discipline as D9.

**`stress_drivers`** — one row per (run, shock, metric): the change that shock causes
**alone** against base. Natural key `(run_id, shock, metric)`.

Reason the per-run values are columns: D56's principle — a value that varies per run is not
a config version. Storing them here also means the output duties (D53a, D54, D53b) read
from the same row the engine wrote, so output and storage cannot disagree.

## D59 — A stressed grade may never enter the scores table, enforced structurally
Decision (owner call, 2026-09-13): the write path **makes it impossible** to store a
stressed grade as a score, and a test pins it. Not left as implementation discipline.

Reason: a stressed grade written to `scores` would carry the **score** fingerprint (D45)
rather than the stress policy fingerprint, and would occupy the `(cik, period_end)` CURRENT
slot that `uq_scores_current` reserves for the real grade. It would not merely mislead a
reader — it would **corrupt score history**, superseding a genuine grade with a hypothetical
one and leaving no way to tell them apart after the fact. That is the same class of harm
D18 exists to prevent, arriving from a new direction.

Mechanism: `store_company_data` accepts base scores only; stress results go through a
separate writer that has no access to the `scores` table, and a test asserts that running a
stress scenario adds zero rows to `scores` and leaves every existing score row CURRENT and
unchanged.

## D60 — Driver attribution is directional and bounded, never additive
Decision (owner-approved 2026-09-13): driver attribution runs each shock **alone** against
base and reports the metric change it causes in isolation. Tests assert **directional
consistency and a bounded residual against the combined run — never additivity.**

**Additivity is false, and asserting it would assert a falsehood about the arithmetic.**
The propagation is multiplicative (`ebitda_s = revenue_s x margin_s`, so revenue and margin
shocks interact), and interest reaches net income through a floor
(`tax_s = max(0, ebit_s - interest_s) x etr`), which is non-linear by construction. Shocks
applied together therefore do not sum to shocks applied apart, and the residual is a real
property of the model rather than an error to be tuned away. The bound is chosen from the
**measured** residual (rule 14), not picked in advance.

**Joint-parameter measurement, recorded here because it strengthens the print duties rather
than motivating a restructure.** `fixed_cost_share` x `floating_share` over
{0.3, 0.7} x {0.3, 1.0}, all 42 stressable periods at Moderate and Severe:
**no period swings 2 or more grades** — the alarm does not fire. But **two periods reach a
grade under the combined assumptions that neither parameter reaches alone**: CCL 2017-11-30
Moderate (fcs-only 3, floating-only 3, **both 4**) and CCL 2019-11-30 Moderate
(fcs-only 4, floating-only 4, **both 5**). The parameters compound. That is an argument for
printing both values in every output — D53a and D54 already require it — not for changing
either default.

## D61 — Three deliberate v1 boundaries in stress
Decision (owner calls, 2026-09-13), recorded so each reads as a choice rather than a gap.

**(a) The base scenario IS stored as a run.** All-zero shocks, so stressed equals base by
construction — which is precisely why it is worth a row: it makes the driver baseline
explicit, the base-versus-stressed comparison self-documenting, and `stress_runs`
self-contained without a reader needing to join back to `scores`.

**(b) The sensitivity grid is computed on demand, never stored.** 5 x 5 cells x 42
stressable periods is 1,050 rows that are a **pure function of inputs already stored** —
D30's don't-store-what-is-derivable — and every config move would otherwise require
invalidating them.

**(c) No named custom-scenario persistence in v1.** A custom run's shocks are stored on its
row, which gives full reproducibility; naming and reuse is a workflow feature with **no
consumer** (CLAUDE.md rule 9 — no abstractions for problems we do not have). A v2 feature
if a consumer appears, not an omission.

## D62 — rate_shock renamed rate_shock_bps in the propagation block, with the conversion stated
Decision (owner call, 2026-09-13): the methodology's propagation block now writes
`(rate_shock_bps / 10000) x floating_share x total_debt`, and the inputs table names the
shock `rate_shock_bps` to match every preset and the sensitivity grid.

Reason: the block said `rate_shock` while every preset and the config say
`rate_shock_bps`, and the block omitted the unit conversion entirely. **Taken literally the
text multiplies total debt by the basis-point figure** — a preset value of 100 would add
100x debt to interest expense. Only the implied /10000 conversion produces sane numbers, so
an implementer following the text exactly would have produced nonsense and an implementer
producing sane numbers would have been departing from the spec. Neither is acceptable in a
document that is the authority.
Consequences: one name and one conversion; no behaviour changes, because the measurements
and the engine both use the sane reading. Recorded because a specification that only works
when silently corrected is a defect in the specification.

## D63 — The two EBITDA modes disagree in DIRECTION for a loss-making company
Finding (measured during Phase 8 implementation, 2026-09-13). Recorded because it is
counter-intuitive, both behaviours are arithmetically correct, and choosing a mode for a
loss-making company is therefore a real decision rather than a preference.

For a company with **negative** base EBITDA, a revenue fall moves stressed EBITDA in
**opposite directions** under the two modes. Worked from the test fixture (revenue 1000,
EBITDA -50, a -20% revenue shock):

- **Constant margin:** the margin is held at -5% while the base shrinks, so
  `800 x -5% = -40`. **The loss gets smaller.**
- **Operating leverage:** fixed costs stay put while revenue falls —
  `800 - 315 - 588 = -103`. **The loss deepens.**

Mode A's behaviour is not a bug: holding a negative margin constant against a smaller
revenue mathematically produces a smaller absolute loss. But it is the wrong *economics*
for a loss-making company under stress, where the whole concern is that fixed costs do not
fall with revenue. **Mode B is the honest mode for a loss-making company**, and mode A can
make a distressed company look better under a revenue shock than it does at base.

This does not change the default (`constant_margin`, per config) because the effect only
appears when base EBITDA is already negative — at which point every EBITDA-based metric is
already refusing with `NEGATIVE_EBITDA` evidence and the grade is saturated at 6, so no
stressed grade is flattered in practice. Verified: both modes produce
`NEGATIVE_EBITDA` on the stressed metrics in that state.
Consequences: pinned by test in both directions with the arithmetic spelled out, so the
divergence reads as understood rather than discovered; a future change to the default mode
must weigh this case.

## D64 — The base scenario is not a no-op for cash-flow metrics, and that is the point of storing it
Finding (measured during Phase 8 implementation, 2026-09-13), surfaced by D61a's decision
to store the base run. Recorded because it changes how a base-versus-stressed comparison
must be read.

At **zero shock**, five of the seven stressed metrics reproduce their base values
**exactly** — `net_debt_to_ebitda`, `debt_to_ebitda`, `ebit_interest_cover`,
`ebitda_interest_cover` and `ebitda_margin`, 151 exact matches and zero drift. The two
cash-flow metrics do not: `fcf_margin` and `fcf_to_debt` drift in **every** case, with a
**median gap of 59.1% and a maximum of 1934%**.

**Cause, and it is the methodology working as written, not a defect.** The propagation
approximates cash flow as `cfo_s = ebitda_s - interest_s - tax_s` with working capital
held flat — a documented simplification. The **base** composite's `fcf` is
`reported CFO - capex`, where CFO is the filer's actual
`NetCashProvidedByUsedInOperatingActivities`, which includes working-capital movements.
At zero shock the two are therefore **different quantities**, not the same quantity
unshocked.

**Consequence for reading the output: a base-versus-stressed comparison of an FCF metric
contains the approximation gap as well as the shock effect**, and the two are not
separable by inspection. Leverage, coverage and margin comparisons are clean.

**This is precisely the value D61a predicted.** Storing the base run was justified as
making the driver baseline explicit and the comparison self-documenting; it has
immediately made a 59%-median modelling artefact visible that would otherwise have been
silently folded into every stressed FCF figure and mistaken for a shock effect.

Not fixed, deliberately: the alternative is to seed stressed CFO from reported CFO and
adjust it, which would make the stressed figure depend on a working-capital movement the
scenario has no view about — importing a real-world number into a hypothetical.
**Amended by D70 (2026-09-14):** the gap is no longer carried into the stressed grade. At 43
companies it changed the grade in 88 of 647 ZERO-shock runs and made 10 Severe runs look
*better* than base, so the FCF-derived metrics are now reported but excluded from the
stressed grade. The "do not seed from reported CFO" reasoning above stands and was kept.
Consequences: the stress output must say that FCF metrics carry the approximation gap; a
test pins the exact/drifting split so a future change to the CFO treatment shows up as a
deliberate re-baseline rather than a silent improvement.

## D65 — The v1 company universe: 43 demonstration companies and 5 retained fixtures
Decision (owner-approved 2026-09-13, Phase 10). **105 companies screened through the full
pipeline over their entire filing history** (D25's rule: validate before adopting, never on
familiarity). **43 pass every hard filter — a 41% rate.** The open question that has stood
since Phase 0 is closed.

Hard filters applied, each traceable to a finding: US-listed and non-financial (SIC outside
6000-6799, verified per candidate from the submissions endpoint); **joint** input
availability rather than per-concept counts (the JNJ/LUMN empty-intersection trap); at
least **3 consecutive periods where all five scoring categories score** (D10/D46's uncapped
requirement); `revenue` and `ebitda` resolving in the **same** period (D53e's stress
requirement); no structurally impossible metric.

**CCL is one of the 43, not an addition to them** — it now qualifies on the criteria rather
than on its distress-and-recovery arc, which is the outcome the re-screen was for.

The full set with per-company uncapped periods, stressable periods, `debt_subset` witness
counts and thin-path contributions is recorded in `PROJECT_STATE.md`.

**Fixtures, retained for specific witness value only and NOT demonstration companies:**

| Fixture | Why it stays |
|---|---|
| **QCOM** | The sole real `NO_DEBT` witness — FY2014, `ShortTermBorrowings` and `LongTermDebt` both tagged **explicit zero**, giving `total_debt = 0`. **2 occurrences in 1,028 resolved `total_debt` values across 105 companies.** Fails the uncapped-run filter, so a fixture and never a demonstration case (D67). |
| **LUMN** | D27's lease-inclusive branch witness and D43's phantom-period witness. Both irreplaceable; neither is a demonstration. |
| **JNJ** | **Cap-visibility witness only.** Scores 86-97 uncapped and shows grade 3 in all 18 periods. **It must stop being described as the strong reference company anywhere that phrasing survives** — it cannot score uncapped or be stressed at all. |
| **F** | The negative fixture of D25: it earns its place by **refusing to compute**. |
| **KHC** | Second lease-inclusive witness behind LUMN. |

**Thin-path coverage now achieved**, ending gaps that every audit's unvalidated-assumptions
table has carried:
- **`NON_POSITIVE_CAPITAL` has two witnesses** — YUM x5 and MAR x2 — so it is no longer a
  single point of failure.
- **FYE derivation is no longer synthetic-only**: BKNG produces **407** FYE events,
  exercising `FYE_DISAGREEMENT` / `FYE_TIE` / `AMBIGUOUS_FYE` at volume. These have been
  listed as "never exercised by real data" since the pre-Task-9 audit.
- **`NO_DEBT` has QCOM** (D67).
- `debt_subset` has **20 companies with 5+ periods**, against a set-level target of 8+.

**BKNG's grade 6 is understood and accepted — do not re-investigate.** It occurs in
**2020 only**: revenue **-54.9%**, EBITDA negative, EBIT negative. A travel-booking company
in COVID, sitting between grade 1s and a recovery. That is a genuine single-year collapse
and makes BKNG a **better** demonstration case, not a riskier one.

## D66 — A filter on data availability became a filter on industry
Decision (owner call, 2026-09-13): the `Liabilities`-tag requirement is **demoted from a
hard per-company filter to a set-level coverage target** — the set must contain enough
`debt_subset` witnesses (8+ companies with 5+ periods each); individual members need not
qualify.

Reason, measured: as a hard filter it eliminated WMT, MCD, KO, TGT, AZO, FAST, TJX, LUV,
DAL, VZ **and CCL itself** — companies strong on every other axis. It was **selecting for a
reporting convention, not for quality**: hotels and gaming filers tag `Liabilities`,
big-box retail largely does not. The resulting concentration read as a property of the
market when it was an artefact of the screen — the 19-company set was 5/19 hotels and
gaming for that reason alone.

Measured effect of the demotion: **19 -> 43 passing (25% -> 41%)**, 21 distinct 2-digit SIC
groups instead of a leisure-heavy cluster, and set-level coverage **exceeded** at 20
companies with 5+ `debt_subset` periods.

**The generalisable point: a check that not every filer can witness must be a set-level
target, never a per-company gate.** Requiring each member to witness every check selects
for whichever filing convention the check depends on, and silently narrows the universe
along a dimension nobody chose. `debt_subset` is the first check with this shape; the same
test should be applied to any future check before it becomes a selection criterion.
Alternatives: keep it hard (loses CCL and ten strong companies to a tagging convention);
drop the requirement entirely (leaves `debt_subset` with its one usable witness, the
finding that started this).

## D67 — NO_DEBT is reachable and witnessed: a correction, and how the error survived review
Correction (2026-09-13). Recorded in full, including the error, because the reasoning
failure is more instructive than the fact.

**What was claimed, and what is true.** After screening 77 companies and finding zero
`NO_DEBT` occurrences, the assistant reported the path as **"structurally unwitnessable"**
and supplied a mechanism: *"a debt-free filer reports nothing rather than zero, so
`NO_DEBT_DATA` fires at the composite layer before `NO_DEBT` can."*

**Both halves are false, and both were checkable in one query.**
- The **mechanism** is false: filers tag explicit zeros routinely. Measured across 105
  payloads: **213 explicit zero debt tags** — `short_term_debt` 75, `current_ltd` 68,
  `total_ltd_aggregate` 9, and others.
- The **conclusion** is false: **QCOM FY2014** reports `ShortTermBorrowings = 0` **and**
  `LongTermDebt = 0`, so `total_debt` computes to exactly 0 and `NO_DEBT` fires, kind
  `NEITHER`, exactly as D42a designed. The unlevered company is correctly not grade-capped.

**So the answer to the question the claim raised: the path is reachable through the real
pipeline, not synthetic-only, and the `NEITHER` classification defends a real state.** It is
simply rare — **2 occurrences in 1,028 resolved `total_debt` values across 105 companies** —
which is why 77 were not enough to find it.

**The lesson, which is the point of this entry.** Absence of evidence across 77 companies
was treated as **impossibility**, and the gap was filled with an **invented mechanism**
rather than a measurement. CLAUDE.md rule 13 says measure rather than assert; this is
precisely the case where a claim about *unreachability* was asserted. A negative claim needs
the same evidentiary standard as a positive one — arguably a higher one, since "not found
yet" and "cannot exist" are indistinguishable from inside a finite sample, and only the
second licenses removing a code path.

**The error survived review.** The owner read the claim, accepted the theory, and asked for
it to be recorded as a finding — so a second pair of eyes did not catch it either. A
plausible mechanism attached to a true observation ("we found none") is unusually
persuasive, which is exactly why the measurement, not the story, has to carry the weight.
The correction came only from screening one more batch for unrelated reasons.
Consequences: no code changes — `NO_DEBT` and its `NEITHER` kind were always correct. QCOM
is adopted as the fixture that witnesses it (D65).

## D68 — Pinned assertions follow the fixtures; the universe gets structural invariants
Decision (2026-09-13, forced by adopting D65's universe): `tests/test_real_companies.py`
parametrises its **pinned** assertions over the five FIXTURE ciks only, and adds a separate
pass parametrised over **every** cached payload asserting structural invariants with no
pinned numbers.

Reason: the regression net globbed `data/raw/`, so caching 105 screened candidates silently
widened it from 5 companies to 105 while every pinned dict — `METRIC_COVERAGE`,
`CCL_SCORES`, `SCORE_SHAPE`, `STRESSABLE` — remained keyed to the original five.
**Pinning a number per company would have meant ~100 expectations nobody had hand-checked**,
which is precisely the failure CLAUDE.md rule 14 exists to prevent: expectations derived
from output rather than examined.

The split matches what D65 made the two roles mean. A **fixture** is retained to witness a
specific behaviour, so its numbers are examined and pinned. A **demonstration company** is
adopted for coverage, so it is exercised by properties that must hold for any filer — it
stores without raising, every metric has a row per period, every reason code classifies, an
integrity-FAIL period is never scored, no stressed grade reaches `scores`. A new candidate
is therefore exercised the moment it is fetched, without anyone inventing an expectation
for it.
Consequences: the suite runs 816 tests over 105 payloads. D65's thin-path claims are
asserted rather than trusted — a test fails if `NO_DEBT` loses QCOM or
`NON_POSITIVE_CAPITAL` loses YUM and MAR.

## D69 — Refuse-on-disagreement generalised from debt to revenue; and the audit that found the rest
Decision (owner-approved 2026-09-14, after the Phase 10 demonstration run): where a
concept's candidate tags name the **same quantity** and resolve to materially different
values in one period, the concept is **`UNAVAILABLE` with `CANDIDATE_TAG_MISMATCH`**, both
figures recorded. It is no longer computed from the higher-priority tag and flagged.

**The lesson, which matters more than the fix.** D26 replaced compute-and-flag with
refuse-to-compute for the debt components-versus-aggregate case, on exactly this reasoning:
*"the old rule flagged a number as suspect and then used it anyway... a plausible-looking
wrong number stamped with full provenance."* **The identical exposure sat in revenue,
unexamined, for eight phases.** D17's `CANDIDATE_TAG_DISAGREEMENT` fired 6 times for GIS
revenue and the engine used the wrong value anyway, producing a **203% EBITDA margin**.
**When a decision changes how a class of disagreement is handled, every other site with that
shape must be checked at the same time.** D26 changed the class and only one member was
updated.

**The audit, and what it found — the concepts are NOT all the same pattern.** Eight of 34
concepts carry multiple candidate tags; six showed real disagreements across the 43 adopted
companies (324 beyond 5%, 30 companies). Measured, they split in two:

| Class | Concepts | Disagreement profile | Treatment |
|---|---|---|---|
| **Same quantity, different taxonomy era** | `revenue`, `cost_of_revenue`, `dividends` | revenue is **bimodal**: p90 12.4%, p99 89.7% | **refuse** beyond tolerance |
| **Deliberately different quantities** | `equity`, `interest_expense`, `short_term_debt`, `d_and_a`, `short_term_investments` | systematic, not sporadic | priority order **is** the answer |

Class B is not a softer version of Class A — refusing there would **discard a correct
value because a different measure disagrees**. `equity`'s candidates are
`StockholdersEquity` (excludes non-controlling interests) and
`...IncludingPortionAttributableToNoncontrollingInterest` (includes them): WYNN 2013 reports
**-184.5m** and **+132.4m**, and both are right. `short_term_investments` disagrees by
**98.1% at the median**. `d_and_a` reaches **60.6% at p90**. `short_term_debt`'s
`DebtCurrent` case already has D32's targeted guard.

**The tolerance was measured, not guessed (rule 14), and the first guess was badly wrong.**
An initial 0.05 refused **65 concept-periods, nearly all legitimate** — it would have cost
Ford 9 periods and LUMN 8. The disagreements there are real scope differences:
**Ford's `Revenues` 170.6bn includes Ford Credit's financing revenue while `SalesRevenueNet`
154.4bn is automotive only** (5-11% apart across 9 years); LUMN's `Revenues` exceeds ASC 606
contract revenue by 6-10%. Genuine errors sit an order of magnitude away — **GIS tags a
segment figure of 2.0bn against a true 19.9bn, 90% apart**. `0.50` separates them cleanly:
GIS's 6 periods refuse, Ford's and LUMN's 17 are preserved.

**A second net, because the tag rule cannot catch everything:** the new integrity check
`ebitda_margin_plausible` FAILs when `ebitda > revenue`. **CAG needed it** — it resolves a
single wrong `Revenues` tag (1.6bn against ~13bn actual) with **no second candidate to
disagree with**, so no candidate-tag rule could ever catch it. Four CAG periods now FAIL and
are excluded from scoring. FAIL rather than WARN: a margin above 100% means an input is
wrong, not that the company is unusual.
Consequences: `tag_map.yaml` gains two settings keys, filtered out of `config.tag_map()` so
the concept-count invariant and completeness counts are untouched.

**Coverage cost, measured 2026-09-20 and not recorded at the time:** refusing costs **17
stressable periods, 647 -> 630** (2.6%) across five companies — GIS 6, CAG 4, HAS 3, PG 3,
DVN 1 — and **nothing is gained back**. Both EBITDA modes need revenue and EBITDA in the
same period (D53e), so a refused revenue takes the period's stress run with it. It also
costs 4 scored periods (780 -> 776), the CAG periods D45 excludes on their integrity FAIL.
**This is the intended trade and it is still right** — the alternative was stressing GIS
off a revenue figure 90% wrong — but a refusal rule's cost belongs in its own entry rather
than being discovered three commits later while reconciling something else.

## D70 — FCF-derived metrics are excluded from the stressed grade
Decision (owner call, 2026-09-14): `fcf_to_debt` and `fcf_margin` are **reported in the
stress results but excluded from the stressed grade**, which now covers **leverage, coverage
and margin only**. Stated in every stress output. Stressed CFO is **not** seeded from
reported CFO — D64 was right that importing a real number into a hypothetical is worse.

Reason, measured at 43 companies: D64 recorded that the base scenario is not a no-op for
cash-flow metrics and judged the gap acceptable on five. At scale that judgement does not
hold — **88 of 647 base runs (14%) showed a different grade at ZERO shock**, and **10 runs
showed the grade IMPROVING under Severe stress, BKNG 2013 and 2014 by two full grades
(3 -> 1)**. A company cannot get safer under a -20% revenue, -5pp margin, +200bps scenario;
that was the approximation gap overwhelming the shock.

Measured effect of the fix: base-run grade changes **88 -> 1**, Severe improvements
**10 -> 0**. Mean Severe grade move settles at +0.56.

**D64's judgement was not wrong on its evidence — it was made on a sample too small to show
the frequency.** Five companies could not distinguish "occasionally noticeable" from "one in
seven". That is a standing argument for **re-testing accepted trade-offs when the sample
grows**, not for doubting the original call.

## D71 — ebit_interest_cover rebased on the observed distribution
Decision (owner-approved 2026-09-14): band edges move from **[1, 2, 3, 5, 8]** to
**[1, 2.5, 5, 10, 20]**. Points unchanged.

Evidence: across 640 observations from the 43 adopted companies, the old top band (>= 8.0x)
held **354 of 640 (55%)** while **p90 is 38.9x** and the maximum is 6,307x. Above 8x the
metric carried **no information** — a company covering interest 8x scored identically to one
covering it 39x.

**Moving the top edge alone was insufficient**, which the measurement showed before anything
was pinned: `[1, 2, 3, 5, 20]` still left **47%** in one band. The intermediates had to move
with it. New occupancy **[23, 59, 112, 156, 143, 147]**, max share **24%** — all six bands
populated, the best spread of any candidate tested.

Grade impact, measured before pinning: **113 of 776 scored periods (14.6%) move, every one
by exactly one grade worse.** Grade 1 falls 51 -> 38, grade 2 117 -> 98, grade 5 rises
77 -> 98. The rebase is a pure tightening at the top, which is what it was meant to be; the
distribution stays well-shaped and single-peaked.

**Correction 2026-09-20:** re-measured directly, by scoring all 43 companies under both
band sets and comparing period by period rather than differencing the distributions:
**114** periods move, not 113, and grade 5 rises **76 -> 98**, not 77 -> 98. A single
arithmetic slip, propagated — 77 and 113 are consistent with each other, and both are one
out. **The claim that matters is confirmed exactly:** all 114 movers go one grade worse and
**not one improves**, which is what "a pure tightening at the top" asserts. Grade 1
51 -> 38 and grade 2 117 -> 98 are confirmed unchanged. Basis for both figures: the 43
adopted companies, capped grades, 776 scored periods, post-D69.
Consequences: the score fingerprint (D45) changes, so every stored score is correctly
distinguishable from one computed under the old bands. CCL's pinned arc and the other
fixture pins are re-baselined deliberately.

## D72 — Four findings recorded from the demonstration run, deliberately not fixed

**(a) The liquidity band effect is a business-model effect, not a cruise quirk.** D48
recorded CCL scoring 0 liquidity points in its good years and framed it as a sector finding.
Measured across 43 companies: **7 (16%) have a median `current_ratio` below the first band
edge of 0.8** — RCL 0.21, CCL 0.29, CHTR 0.31, MAR 0.50, GIS 0.72, TXRH 0.74, **PG 0.79**.
That spans cruise, cable, hotels, packaged food, restaurants and household products:
**negative-working-capital businesses that collect from customers before paying suppliers.**
**Procter & Gamble appearing on the list is the clearest evidence that a sub-0.8 current
ratio is not a distress marker in this universe.** D48's framing is widened accordingly. The
bands are not changed — that remains the post-MVP sector-thresholds item.

**(b) Escalation fires in 31% of periods.** 245 of 780 company-periods trigger it, escalating
**989 of 1,539 warnings (64%)**. Implemented exactly as specified, but CLAUDE.md rule 12's
principle applies directly: *a signal that fires constantly is indistinguishable from no
signal.* With seven trend-deterioration indicators able to fire together, a threshold of 3 is
low. Recorded for a calibration decision, not changed here.

**(c) Four fail-severity integrity checks have never fired on real data.**
`current_assets_subset`, `current_liabilities_subset`, `cash_subset` and `debt_subset`
produced **zero FAILs across 780 company-periods**. Stated plainly rather than read as a
clean bill of health: **they remain validated only by synthetic fixtures**, and after 780
periods the honest description is that no real violation has ever exercised them. They are
accounting identities a filer would have to mis-tag to break, so this may be correct — but it
is not evidence that they work. (`ebitda_margin_plausible`, added by D69, fires on 4 real
periods and is the first fail-severity check with a real witness.)

**(d) The four demonstration cases, chosen by measurement.**

| Role | Company | Evidence |
|---|---|---|
| **Strong** | **SYK** | mean grade 1.84, 84% at grades 1-2, median leverage 1.28x, coverage 10.2x, 17 of 19 periods uncapped |
| **Deteriorating** | **LYB** | 13 consecutive periods 2013-2025: score -62.5, grade 1 -> 5, leverage 0.23 -> 7.70x, margin 13.9% -> 3.2%, 36 deterioration warnings |
| **Leveraged** | **CHTR** | mean grade 5.31, 81% at grades 5-6, median leverage 4.69x, coverage 1.1x |
| **Resilient** | **TXRH** | 5 of 6 weak base periods hold grade under Severe, score 54.5 -> 52.4 |

**FAST was rejected for the strong role despite a better mean grade (1.79 vs 1.84):** its
median coverage is **125.5x** and leverage **0.16x**, making it a **debt-free company rather
than a strong borrower**. It demonstrates the top band, not credit analysis.

**CHTR scores best on the resilience measurement and was rejected for it.** It holds grade in
14 of 16 weak periods only because it already sits at grades 5-6 — **floor effect, not
strength**. The measure reached for first, "holds grade under stress", accidentally ranks
saturated companies highest.

**The resilient case is the weakest of the four in this universe, and that is a property of
the set rather than the engine.** The universe contains many strong companies, many leveraged
ones and a clear deteriorator, but "weak at base yet robust under stress" is rare — and the
obvious candidates by score are companies whose grades cannot fall further.

## D73 — The evidence pack supplies four things docs/ai-governance.md predates
Decision (owner-approved 2026-09-16, Phase 9). The governance doc was written before
Phases 5-8 existed, and describes an evidence pack the engine has outgrown in four ways.

**(a) The assumption register is built from config at export time, and the `assumptions`
table stays deliberately unwired in v1.** The table exists from Task 8 but **nothing
writes to it** — recorded explicitly so a future reader does not assume a write path
exists. Meanwhile the ASSUMED values genuinely live in `config/`: `fixed_cost_share`,
`floating_share`, `default_tax_rate`, `include_operating_leases`,
`component_aggregate_tolerance` and the rest. The exporter reads them from config and
marks each `source: config`. Building a write path nothing else needs, or shipping an
empty register section, would both have been worse.

**(b) The pack carries the five stress output duties and the cap line**, taken **verbatim**
from `StressRun.assumptions` and D57's `_cap_line` generator, so the pack cannot disagree
with the CLI. A pack carrying stressed figures without `fixed_cost_share`, `floating_share`,
the resolved `new_debt_rate` and its reason, the liquidity-immobility statement and the
trend-carry statement would let a model reason from numbers whose basis it cannot see; a
grade without its cap line would read as judged when it is capped.

**(c) Grade-label matching is longest-first.** "Very strong" contains "strong" and "Very
high risk" contains "high risk", so naive matching classifies **every Grade 1 mention as
Grade 2 and every Grade 6 as Grade 5** — silently inverting the check at both ends of the
scale.

**(d) D30(b)'s obligation fell due here.** `store/provenance.py::filing_url(cik, accession)`
is the single place a filing URL is derived, per D30(b)'s original argument that a stored
copy can only drift. This is the first exporter, so the obligation the decision recorded is
now discharged.

Also supplied beyond the doc: a **"what this pack does not contain"** section naming market
data, management commentary, peer comparison, forward estimates and agency ratings. Stating
the boundary explicitly is what makes the prompt's "Data not available" rule enforceable —
otherwise the model must infer what it is missing.

## D74 — Validator design: match at the memo's stated precision, and state the limits above the results
Decision (owner-approved 2026-09-16). The validator is the control the entire AI workflow
rests on, so both its method and its limits are recorded.

**Number matching is at the precision the memo itself states.** The doc's literal reading —
strip `£$%x,` and compare digits — is too weak to use: a pack holding `20,825,000,000` would
flag a memo's `$20.8 billion`, which is correct and natural writing. **Every memo would be a
wall of false positives, and a validator that cries wolf gets ignored.** A blanket tolerance
is the opposite failure, letting a model shift figures for slack. Matching at the stated
precision verifies the memo's own claim: **write more digits and you are held to more; write
fewer and you are not punished for it.**

Implemented as an **interval**, not by comparing rounded values, because rounding a tie is
ambiguous: 20,825,000,000 to four significant figures is 20.82 under round-half-to-even and
**20.83 under the round-half-up people are taught**. Comparing rounded values rejects one
arbitrarily; asking whether the pack value falls inside the interval the memo's figure
represents accepts both, which is what "rounds to this figure" actually means.

**The low-confidence list, with its rule stated in the output.** A bare number below 100, or
a four-digit year, will coincide with something in a pack of dozens by chance, so counting
those as verified inflates the pass rate and makes the verified count meaningless. They are
listed separately **with the reason printed**, because a reader seeing "3 verified, 12
low-confidence" cannot otherwise tell whether that is good. Precision overrides magnitude —
`2.0206` matching is not a coincidence — but **a year is always low-confidence regardless of
precision**, since it is a date rather than a claim.

**The limitation statement is printed ABOVE the results in every run.** A limitation placed
below the verdict is one a reader can skip, and **a clean validation read as a clean memo is
worse than no validation at all** — it converts an unchecked document into an apparently
checked one.

**Characterised limitations, asserted by test rather than assumed:**
- **A figure cited under the wrong label passes.** Quoting the pack's `cfo` as EBITDA is
  invisible: the validator reads numbers, not labels.
- **True figures assembled into a false claim pass.** This was the expected result of the
  five-violation test and is a **characterised limitation, not a defect** — the validator
  reads numbers, not arguments.
- **A fabricated source passes.** "Q4 2019 earnings call, CFO remarks" is caught by no
  numeric check.
All three are pinned by tests so the boundary cannot drift into being assumed narrower.

**Five-violation reality test, run against a real CCL 2019 pack (334 lines, 541 numeric
tokens):** invented figure **CAUGHT**; legitimate rounding **correctly passed** in both
forms; grade contradiction **CAUGHT**; fabricated source **MISSED**; true-numbers-false-claim
**MISSED**. `REVIEWED` correctly rejected, CLI exit 1.

**The test found four defects in the validator itself**, every one a matching bug that would
have made it useless or dangerous:
1. **Scale alternation was first-match-wins**, so a bare `m` matched before `million`, the
   suffix group failed on "illion", and the scale silently backtracked to None — turning
   "$5,436 million" into 5,436 and reporting a **correct figure as unverified**. The same bug
   class as D73c's grade labels, found twice in one phase.
2. **Accession numbers were tokenised as figures**, reporting three phantom unverified
   numbers per Source line.
3. **The grade check fired on ordinary English** — "leverage is moderate" read as a Grade 3
   claim, "cash flow was strong" as Grade 2 — producing three false positives that would
   have buried the one real violation. Band labels now require a **grading context**.
4. **A figure ending a sentence failed to parse**, because the lookahead rejected the
   trailing full stop.
Recorded because the instruction to "test against reality, not just fixtures" is what found
all four: a fixture-only suite would have tested the matcher against strings the matcher was
written to handle.

## D75 — A metric UNAVAILABLE at base is UNAVAILABLE under stress (v1 final audit, finding 1)
Decision (owner-approved 2026-09-17): `stressed_metrics()` inherits every base refusal,
carrying the **same reason code**. The inheritance is applied last, after all seven
recomputations, so no branch can bypass it. The stress engine must not be able to
manufacture availability.

Reason — the gates are asymmetric and always will be. The stress engine works from
propagated figures (`StressedValues`), not from resolved concepts and the D41 coverage
gates, so its preconditions are necessarily weaker than the metric engine's. Without
inheritance it computes values the base pipeline refused, and a stressed grade then scores
a category the base grade could not — which is not a stress result at all, it is a
different company. Carrying the base reason code rather than inventing a stress-specific
one means the stressed result says *why* it is absent, and says the same thing the base
run said.

**This corrects D70, which fixed the symptoms and left the mechanism live.** D70 measured
its own success honestly — zero-shock grade changes 88 → 1, Severe improvements 10 → 0 —
but it suppressed the two FCF-derived metrics, not the ability to manufacture a metric.
The witness is **AZO 2011-08-27**, the single residual: base capped at four categories
scored, stressed uncapped at five, the fifth arriving through `ebit_interest_cover`. **No
FCF was involved**, so D70's rule could not have caught it and the residual had a
completely different cause from the one D70 addressed.

**The general lesson, and the reason this entry is longer than the fix: this is the third
time in this project that a fix aimed at an instance left the mechanism live.** D69 fixed
the revenue disagreement but not the precondition that let it through; D26's
refuse-on-disagreement shape had to be rediscovered for revenue after being solved once
for debt. **When a defect is fixed, check what class it belongs to, not just where it
appeared.** The audit found this one only because it re-verified against current data
rather than against the fix report.

Measured across the 43 adopted companies, before → after: metrics manufactured from a base
refusal **118 → 0**; base runs changing grade at zero shock **1 → 0**; Severe runs
improving a grade **0 → 0** (already clean).

**D70 was re-measured afterwards and is still load-bearing — it is not redundant, and is
kept unchanged.** With D75's inheritance in place but `FCF_DERIVED` suppression disabled,
**71** base runs change grade at zero shock (Severe improvements stay at 0). The two rules
address different causes: D75 stops the engine inventing a metric the base refused, D70
stops D64's CFO-approximation gap moving a grade at zero shock. Neither subsumes the other.

Alternatives: let the stress engine compute what it can and flag the divergence (rejected —
CLAUDE.md rule 3, and a flagged manufactured metric still enters the stressed score);
strengthen the stress engine's own gates to match the metric engine's (rejected — that is
CLAUDE.md rule 13, one invariant in two layers, and the two would drift apart).
Consequences: a stressed run can now score fewer categories than before, so some stressed
grades are capped where they previously were not — correctly, since the base grade was
capped for the same reason.

## D76 — A period that FAILS a fail-severity integrity check computes no metrics (v1 final audit, finding 3)
Decision (owner-approved 2026-09-17): `compute_metrics()` takes `failed_periods` and emits
`UNAVAILABLE / INTEGRITY_FAILED` for **all 17 metrics** in any period that FAILED a
fail-severity integrity check. `INTEGRITY_FAILED` is a **GAP** kind (D9/D41a): an input is
provably wrong, so nothing derived from it is knowable — that is not evidence about the
company, it is an absence of knowledge, and it caps the grade rather than scoring zero.

Reason — the cleaner option was chosen over the marking one. An arithmetically impossible
figure should not be **reachable**, not merely reachable-behind-a-marker. Marking it makes
every downstream consumer responsible for honouring the marker, and the one that forgets
prints the wrong number; the evidence pack was exactly that consumer, publishing CAG's
**122.5% EBITDA margin** to a model that is instructed the pack is its complete and
exclusive basis. A marker would also have required extending the validator to honour it,
which is a second place the rule has to be remembered (CLAUDE.md rule 13).

**All 17 metrics refuse, not just the one that tripped the check.** `_ebitda_margin_plausible`
proves `ebitda` and `revenue` disagree but not **which** is wrong, so `debt_to_ebitda` and
`ebitda_interest_cover` are equally unsafe. **Failed periods are also removed from the
`revenue_growth` pairing anchors** — growth measured against an impossible base is itself
impossible, and without this the wrongness escapes the suppressed period into a healthy one.

Measured blast radius across the 43 adopted companies: **4 periods, 1 company, 67 computed
metric values suppressed** — CAG 2012-05-27, 2013-05-26, 2014-05-25 and 2016-05-29, all
from `ebitda_margin_plausible`, the only fail-severity check with a live witness (D69).
16 values for 2012-05-27 and 17 for the rest; the earliest has no prior revenue anchor so
`revenue_growth` was already absent. **Nothing else in the universe is affected.** CAG's
122.5% is confirmed gone from the evidence pack.

Alternatives: mark the figures and leave them (above); suppress only `ebitda_margin`
(rejected — the check does not identify which input is wrong); exclude the period from the
pipeline entirely (rejected — the integrity results themselves must still be exported, and
a silently absent period is less honest than a visibly refused one).
Consequences: scoring already excluded integrity-FAIL periods, so no grade changes; the
evidence pack's metrics table now shows `INTEGRITY_FAILED` for these periods; the trends
engine sees fewer resolved points for CAG, which is correct.

## D77 — The golden set: four company-years hand-verified against their filings
Decision (owner-approved 2026-09-20, Phase 11 follow-on): **CCL FY2019, YUM FY2023, MCK
FY2023 and BDX FY2009** are hand-verified against the human-readable statements and
footnotes of their filing documents, stored as evidence in `tests/golden/*.md` and enforced
by `tests/test_golden.py`, which **parses those files rather than restating their numbers**
so evidence and enforcement cannot drift (CLAUDE.md rule 13).

**The independence constraint is the whole point.** Every other test in the suite compares
the engine to hand-built fixtures or to its own prior output, so all of them share one
failure mode: if the engine misreads a filing consistently, nothing notices. Expected values
taken from the same XBRL payload the engine reads would inherit that blind spot exactly. So
every figure was read from the income statement, balance sheet, cash-flow statement and
notes — never from `companyfacts`, the cached JSON, or any pipeline output.

Selection covers all three `total_debt` branches (components/CCL, lease-inclusive/YUM,
aggregate/MCK), fallback tags at rank 1 and rank 2, and a real refusal. **All four are
adopted companies, not fixtures**: the lease-inclusive branch turned out to be exercised by
20 adopted companies, so D27 did not need LUMN or KHC as the brief assumed.

**Four engine defects found, none of which any other test could have detected.** Each is
recorded with its measured exposure across the adopted 43 and **deliberately not fixed
here** — every one changes published figures, and each deserves its own decision with its
own before/after measurement, in the D72 mould:

1. **`cfo` tag-map gap.** `tag_map.yaml` carries only `NetCashProvidedByUsedInOperatingActivities`.
   BDX tags `...ContinuingOperations` = 1,691,520k, plainly on the cash-flow statement.
   **74 periods across 19 of 43 companies** lose `cfo`, and with it `fcf`, `fcf_margin`,
   `fcf_to_debt` and `cfo_to_debt`.
2. **`total_debt` double-count in `debt_from_lease_inclusive_ltd`.** YUM's Note 11 shows the
   balance-sheet "Short-term borrowings 53" **is** the 56 of current maturities net of 3 of
   issuance costs; the engine adds both. Overstates by 56 (0.5%). **Up to 65 periods across
   8 companies** are exposed — not all wrong, since KO has genuine commercial paper.
3. **`total_debt` double-count in `debt_from_aggregate`.** MCK's lease note shows finance
   lease liabilities are presented *within* "Current portion of long-term debt" and
   "Long-term debt", so the 202 is already inside `LongTermDebt` 5,594; the engine adds it
   again. Overstates by 202 (2.8%).
4. **`d_and_a` rank order.** The map ranks `DepreciationDepletionAndAmortization` above
   `DepreciationAndAmortization`, assuming the first is broader. For MCK it is narrower —
   272 against 608, the latter tying exactly to the cash-flow statement. **16 periods, 2
   companies; MCD is understated 80–86%**, which is material to a grade.

Findings 2 and 3 are **one shape**: `short_term_debt` overlapping a current-maturities
figure. **D32 already guards exactly this hazard on the components branch.** The
lease-inclusive and aggregate branches have no equivalent. That is the same
fix-the-instance-not-the-mechanism pattern recorded at D75 — now the **fourth** occurrence,
and the first found by an external check rather than an audit.

**D32 is vindicated, and the golden set quantified what it prevents.** BDX FY2009 refuses
`total_debt` because `DebtCurrent` (402,965) may already contain `current_ltd` (200,085).
The filing's debt note settles it: *Loans Payable Domestic 200,000 + Foreign 2,880 + Current
portion of long-term debt 200,085 = 402,965.* **It does contain it.** Adding both would have
double-counted 200,085 — a **13% overstatement** of BDX's total debt. A rule written on
suspicion, with no witness at the time, turns out to have been right about a real company.

**The restatement finding, which shapes what any golden test can assert.** BDX restated
FY2009 in its FY2010 10-K after a divestment: revenue 7,160,874 → 6,986,722, operating
income 1,650,353 → 1,589,682, CFO 1,691,520 → 1,658,486. The engine reports the restated
figures and is **right** to (D14/D15). Five of BDX's ten disagreements are therefore neither
defects nor tagging artefacts. The general consequence: **"verify the engine against the
filing" is ambiguous whenever a period has been restated**, and a golden file must name
which filing it means. BDX was kept in the set precisely because it forces that question.

**A limit on the method, found by using it.** Two figures needed a footnote rather than the
face of a statement — YUM's gross interest (602, Note 11 prose, against 513 presented net on
the income statement) and MCK's finance-lease split. Footnotes are still the filing, so both
remain independently verified. But **where a figure exists only as an XBRL fact with no
human-readable presentation, this method has nothing to check it against.** Recorded as a
limit rather than worked around, per the brief.

Consequences: `tests/golden/` holds 4 evidence files plus a README stating what the set does
and does not establish; 17 tests enforce it; sabotage-verified three ways (breaking a tag
fires the AGREES assertions on all four files; fixing either recorded defect fires the
DIFFERS pin and demands the evidence file be updated). The unmet Phase 10 definition-of-done
recorded in `docs/build-plan.md` is now met. **Four companies is four companies** — the set
verifies that the engine reads these four filings correctly and nothing wider.

## D78 — A component is never added to a figure that may already contain it (golden-set defects 2 and 3)
Decision (owner-approved 2026-09-20): D32's containment rule is generalised from the
components branch to the other two. **Fixed as one mechanism, not two defects** — fixing
them separately would have been the fifth instance of the pattern they demonstrate.

**The mechanism.** `short_term_debt` and a current-maturities figure may be the same debt
tagged twice; `total_ltd_aggregate` may already contain the finance leases added to it.
D32 guarded the first case for `DebtCurrent` only. The golden set found the same hazard
live in both other branches:

- **YUM FY2023** — the balance-sheet "Short-term borrowings 53" **is** the 56 of current
  maturities net of 3 of issuance costs (Note 11); the engine added both.
- **MCK FY2023** — the lease note shows finance leases are presented *within* "Current
  portion of long-term debt" (29) and "Long-term debt" (173), so the 202 was already inside
  `LongTermDebt` 5,594; the engine added it again.

**This is the fourth occurrence of fixing an instance rather than a mechanism** (D69's
precondition, D26's shape in revenue, D75's stress inheritance) — and **the first found
outside an audit**, by a test that checks the engine against a source document rather than
against itself.

**The rule, in order of reliability.** A cross-check where one exists; refusal where the
overlap is merely possible was tried and rejected:

1. `short_term_debt == 0` → nothing to double-count, proceed.
2. `ltd_incl_leases_aggregate` present → it reconciles the question. Sitting at the pair
   means the component is already inside; sitting at pair + component means they are
   disjoint. Cross-check only, never a value source (D27(4)).
3. No cross-check, and the two agree within `component_aggregate_tolerance` → the same
   figure twice → refuse.
4. Otherwise → distinct magnitudes → add.

**Refusing on possibility alone was measured and abandoned.** The first implementation
refused whenever no cross-check existed. It cost **9 of KHC's 12** lease-inclusive periods,
where `short_term_debt` runs at **0.6% of current maturities** and one period tags it at
**exactly zero** — none of which can double-count anything. A guard that fires on ordinary
reporting behaviour is CLAUDE.md rule 12's failure, and this one did.

**No threshold could be measured, and none was invented.** The deviation between
`short_term_debt` and `ltd_incl_leases_current` runs **continuously from 0% to 100% across
95 periods with no bimodal gap** — so unlike D69, where 0.50 came from a measured
bimodality, there is nothing here to derive a number from. The existing
`component_aggregate_tolerance` is reused rather than a second constant invented (D36's
precedent).

**The cost of that honesty, stated plainly: YUM FY2023 is still wrong.** Its deviation is
**5.36%**, 0.36pp outside the tolerance, and its only aggregate is the *gross* figure before
issuance costs, which sits closer to pair+std than to pair and would answer backwards. YUM
FY2019, FY2020, FY2022 and FY2025 are caught; FY2023 is not. **The tolerance was not widened
to capture it** — tuning a constant until one known case passes is fitting to the test, the
inverse of rule 14. What would settle it is footnote prose XBRL does not carry, which is a
real limit on a deterministic XBRL engine.

Measured across the 43 adopted companies, before → after:
- `total_debt` values **666 → 654**: 7 periods refuse under (a) — RCL 4, YUM 2, GIS 1 — and
  5 under (b) — LUV 4, MCK 1. New reason code `LEASE_CONTAINMENT_UNVERIFIABLE`.
- **6 MCK periods keep `total_debt` but correctly drop the finance leases** the aggregate
  already contained, which is the fix rather than a refusal.

Alternatives: refuse whenever both resolve (measured above — over-refuses badly); widen the
tolerance until YUM FY2023 passes (fitting to the test); use the gross aggregate as a
discriminator (answers backwards for the one case that needs it).
Consequences: `debt_from_components` is deliberately untouched — `LongTermDebtCurrent`/
`Noncurrent` exclude finance leases by element definition, and the measurement bears that
out at **1 anomaly in 81 periods**, against a 6-vs-7 coin flip on the aggregate branch.

## D79 — Two tag-map gaps the golden set found, and why each sits where it does
Decision (owner-approved 2026-09-20): two candidate tags added, both ranked **last**.

**`cfo` gains `NetCashProvidedByUsedInOperatingActivitiesContinuingOperations`.** Where a
filer reports the total, that is the complete figure and must keep winning — so the new tag
is a fallback, not a promotion. It is the only operating-cash-flow tag **19 of the 43
companies** offer in some periods. Measured: **75 periods across 19 companies** now resolve
`cfo`, and with it `fcf`, `fcf_margin`, `fcf_to_debt` and `cfo_to_debt`.

**`short_term_investments` gains `OtherShortTermInvestments`**, same reasoning, **26 periods
across 3 companies** (BDX 18, KO 5, SYK 3). Without it `net_debt` was overstated by the
whole investment balance in those periods — BDX FY2009 carries 551,561k of short-term
investments plainly on the face of its balance sheet.

**D77 undercounted.** It summarised four engine defects; the BDX evidence file classified
**five**, and `short_term_investments` was the one the summary dropped. Recorded because the
discrepancy is exactly the kind D77 itself warns about — a count stated without being
re-derived from the evidence behind it.

Consequences: **LUMN gains 3 uncapped periods** (2011-2013, where the continuing-operations
tag resolves and the cash-flow category can finally score). It previously had none, so the
fixtures that can never score uncapped go from four of five to **three** — F, JNJ and KHC.
Verified: LUMN 3, CCL 13, F 0, JNJ 0, KHC 0.
`TAG_MAP_SETTING_KEYS` replaces the inline single-name exclusion in `config.tag_map()`,
which broke when D69 added a settings key and broke again here; a named set makes the next
addition safe (CLAUDE.md rule 13).

## D80 — d_and_a takes the largest candidate, not the first (golden-set defect 4)
Decision (owner-approved 2026-09-20): `tag_map.yaml` gains
`prefer_largest_candidate: [d_and_a]`, and `map_concepts` honours it.

**Rank order assumes earlier candidates are at least as complete as later ones. For
`d_and_a` that is false, and filer-dependent in both directions:**

| | `DepreciationDepletionAndAmortization` | `DepreciationAndAmortization` |
|---|---|---|
| MCD FY2023 | 382m — an income-statement expense line | **1,978m — the cash-flow add-back** |
| MCK FY2023 | 272m — depreciation 248 + finance-lease ROU 24 | **608m — depreciation 248 + amortisation 360** |
| YUM FY2009 | **580m** | 553m |
| SBUX FY2024 | **1,592m** | 1,513m |

**A reorder would fix MCD and MCK and break YUM and SBUX** — measured, rank-0 is larger in
25 periods and rank-1 larger in 16. So the fix is a selection rule, not a ranking one.
**Both directions were verified against the filings**: MCK's 608 is Depreciation 248 +
Amortization 360 on its cash-flow statement, and MCD's 1,978.2 is the operating-activities
add-back while 381.7 is a separate income-statement line.

**Why "largest" is the right criterion for this concept specifically:** D&A is an add-back
to EBIT, so completeness is what matters. A narrower tag means the filer split D&A across
elements, and the narrower figure understates EBITDA. This is a deliberate departure from
pure rank order, scoped to one concept by config rather than applied globally.

Measured: **16 periods across 2 companies** change — MCD 8, MCK 8. **MCD's D&A was
understated by 80-86%**, which moves EBITDA by ~13% and is material to a grade.

Alternatives: reorder (breaks YUM and SBUX, above); refuse on disagreement (D69's shape, but
these tags are *deliberately different* measures where D69 itself says priority is the
answer — here the priority was simply wrong); take the largest across all three candidates
(pulls in `DepreciationAmortizationAndAccretionNet`, which includes accretion and is not
D&A).

## Combined effect of D78-D80 across the 43 adopted companies
Basis: 43 adopted companies, capped grades, 776 scored periods, before `e9bee36` → after.

| | before | after | delta |
|---|---|---|---|
| Metric values computed | 10,848 | **10,975** | **+127** |
| Metric values refused | 2,616 | **2,489** | **-127** |
| Scored periods **carrying a cap** | 316 | **267** | **-49** |
| `total_debt` values | 666 | **654** | **-12** |
| Warnings | 1,505 | **1,522** | +17 |
| Distinct reason codes | 14 | **15** | +1 |
| Grade distribution 1→6 | 38/98/273/221/98/48 | **43/110/259/217/101/46** | |

**49 periods escape the grade cap** because a category that could not be scored now can —
overwhelmingly cash flow, from D79's `cfo`. The grade distribution shifts modestly toward
the strong end, which is the expected direction: the fixes add coverage and correct an
understated EBITDA, and both raise scores.
