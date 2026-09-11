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
