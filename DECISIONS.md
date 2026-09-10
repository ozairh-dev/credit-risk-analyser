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
