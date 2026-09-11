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
Consequences: migration to Postgres later is mechanical via SQLAlchemy if ever needed.

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
