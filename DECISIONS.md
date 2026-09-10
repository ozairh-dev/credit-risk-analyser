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
Consequences: leverage will be higher for lease-heavy companies; ex-lease figure always
shown alongside.

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
