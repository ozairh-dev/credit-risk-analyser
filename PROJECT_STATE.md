# Project state

_Update at the end of every working session._

## Phase
Phases 1-3 complete — Tasks 1-8 done. Task 9 (composite concepts, Phase 5) next, then
Task 10 (integrity + data quality, Phase 4): task order interleaves the phases there
because the integrity checks depend on the composites. See docs/build-plan.md.

## Completed
- Specification: CLAUDE.md, docs/, DECISIONS.md D1-D10
- Task 1 — project skeleton: pyproject.toml, package layout under src/credit_risk/,
  .gitignore, .env.example, empty subpackages for each phase
- Task 2 — config in place: config/thresholds.yaml, stress.yaml, tag_map.yaml;
  config loader (src/credit_risk/config.py); CLI stub with a `version` command
- Task 3 — ticker -> CIK lookup: credit_risk/env.py (.env / env var reader for
  SEC_USER_AGENT), credit_risk/ingest/cache.py (shared raw-JSON cache with
  fetched_at, 24h staleness, reused by Task 4), credit_risk/ingest/tickers.py
  (fetch_company_tickers, ticker_to_cik). Verified against the real SEC endpoint
  (AAPL -> 320193, MSFT -> 789019); cache written to data/raw/company_tickers.json.
- Project review (2026-09-09): git repo initialized and initial commit made (Task 1's
  "repo" item was checked off but never actually done until now); config/ingestion.yaml
  added so the 24h cache staleness window is no longer hardcoded in cache.py (CLAUDE.md
  rule 6); docs/data-sources.md's lease-liability tags split into current/noncurrent to
  match config/tag_map.yaml (DECISIONS D11); docs/credit-methodology.md's stress Inputs
  table no longer restates margin_shock values that had drifted out of sync with
  config/stress.yaml (DECISIONS D12); TODO.md Task 4 and build-plan.md's task list now
  explicitly include wiring a `credit-risk fetch <ticker>` CLI command; two tests
  strengthened to assert exact values instead of just structure. Fixes committed
  separately from the skeleton (commit 5c6b706).
- Task 4 (2026-09-10) — credit_risk/ingest/companyfacts.py: `fetch_companyfacts(cik)`,
  caches raw JSON to `data/raw/CIK{cik:010d}.json` (doc updated to match), reuses
  `ingest/cache.py` + `config/ingestion.yaml` staleness exactly as Task 3; `timeout=30`
  on the request; non-200 responses wrapped in a clear `RuntimeError` instead of a bare
  HTTPError; `time.sleep(0.12)` after every live (non-cached) request to stay under the
  10 req/s ceiling. CLI: `credit-risk fetch <ticker> [--force]`, wiring
  `ticker_to_cik` -> `fetch_companyfacts`. Verified live against three real companies
  (chosen for sector + credit-profile spread): **F** (Ford Motor Co, CIK 37996 — leveraged
  industrial, the user's pick), **JNJ** (Johnson & Johnson, CIK 200406 — Health Care,
  strong/low-leverage anchor case), **LUMN** (Lumen Technologies, CIK 18926 —
  Communication Services, heavily leveraged/weak case). All three fetched real SEC data
  (589-666 us-gaap concepts each) and a repeat fetch confirmed the cache hit path
  (0.014s, no network round trip). **Ford was later replaced as the leveraged case by
  CCL (2026-09-10) — see "Demonstration companies" below and DECISIONS D25.**
- Task 5 (2026-09-10, on Fable per the model protocol) — hand-built
  tests/fixtures/companyfacts_minimal.json: fictional Fixture Manufacturing Co
  (CIK 999999), 3 filings, 13 facts across Revenues / NetIncomeLoss /
  CostOfGoodsAndServicesSold (fallback-tag case; primary CostOfRevenue absent) /
  Cash (instant) / one dei shares fact. Covers: two clean fiscal years, a
  restatement (100 -> 90 via the next year's 10-K), a same-value comparative
  duplicate, a quarterly fact, a 274-day duration trap stamped fp=FY/form=10-K,
  and an off-fiscal-year-end instant fact. Expected selection results hand-written
  in tests/fixtures/companyfacts_minimal_expected.md BEFORE any selection code
  exists; 3 structural guard tests protect the fixture's geometry. No selection
  code written (that is Task 6). No DECISIONS entry — interpretation flags below
  were deliberately left for the owner, not decided.

- Task 6 (2026-09-10, on Fable per the model protocol) —
  src/credit_risk/normalise/selection.py: select_annual_facts implementing
  docs/data-sources.md rules 1-6 in D14's order (filter 1-3, then dedup 4), with
  D13 FYE derivation (NO_FYE_ANCHOR / AMBIGUOUS_FYE fail-safes), D15 equal-value
  provenance (supersession only on changed values), rule 5 FOREIGN_UNIT markers,
  and rule 6 provenance on every output fact. Period identity is always
  (tag, end), never the fy stamp. Reproduces every row of
  tests/fixtures/companyfacts_minimal_expected.md exactly — no disagreement with
  the specification document arose. Four underdetermined plumbing details
  resolved fail-safe and recorded as DECISIONS D16, each with a synthetic test;
  the 10-K/A acceptance branch the fixture leaves uncovered is also
  synthetically tested.

- Task 7 (2026-09-10, on Fable per the model protocol) —
  src/credit_risk/normalise/mapping.py: map_concepts consumes select_annual_facts
  output; candidate lists and their order come only from config/tag_map.yaml
  (a test proves reversing the list flips the winner); first-found-wins per
  concept per period; source_tag + reported label on every value (label carried
  by a new SelectedFact.label field); data_status=REPORTED; no candidate for a
  period -> UNAVAILABLE NO_CANDIDATE_TAG (fixture: 7 resolved / 55 unavailable
  of 62 slots); differing candidate values -> CANDIDATE_TAG_DISAGREEMENT warning
  (owner call), equal-value co-tagging silent (D17). Composites and the
  gross_profit CALCULATED fallback deferred to Task 9 as scoped. Tag-map review
  flagged for Phase 9/10: short_term_debt candidates overlap current_ltd
  (DebtCurrent includes current LTD -> double-count risk in total_debt); equity
  disagreement warnings will be routine for NCI companies; pretax_income likely
  needs tag variants added.

- Task 8 (2026-09-10, on Opus per the model protocol) — SQLite schema, designed
  and approved before implementation per build-plan's two-stage requirement,
  then built with four owner amendments. src/credit_risk/store/: schema.py (raw
  DDL, 14 tables, 12 indexes, STRICT where supported with a tested fallback),
  db.py (connections with PRAGMA foreign_keys=ON), fingerprint.py (config
  fingerprints, documented allowlist), writer.py (stores selection + mapping
  output), queries.py (the five queries the app runs). data_status constrained
  to the six allowed values at DB level; supersession of facts is a self-FK
  relationship, never a deletion; concepts/metrics are append-with-history with
  a partial unique index on the CURRENT row (D18); no index on fy anywhere, by
  design and asserted by a test (D19); stress tables deferred (D20);
  filings.form CHECK dropped with reasons (D21). Also completed the flagged
  string->structured refactor: selection and mapping warnings are now
  DataQualityEvent records (normalise/quality.py) persisted to
  data_quality_events, so only one shape exists in the codebase.

## Demonstration companies (current set)

Cached in `data/raw/`. Every adoption must be validated by running the full pipeline over
the company's entire filing history first (DECISIONS D25) — not assumed from familiarity.

| Ticker | CIK | Role | Pipeline-verified |
|---|---|---|---|
| CCL | 815097 | leveraged borrower | all five of total_debt / ebitda / interest_expense / cfo / capex resolve for 18 periods, **15 consecutive after D26** (2011-11-30 -> 2025-11-30; 2010-11-30 is a 7.9% component/aggregate mismatch); no config changes needed; debt/assets 22-69% |
| JNJ | 200406 | strong / low-leverage anchor | total_debt 18/19 periods, but `ebit` only 2010-2014, so EBITDA leverage is limited to those years |
| LUMN | 18926 | weak / deteriorating | ebitda 18/18; **total_debt 15/18 under D27's lease-inclusive branch** (2011-2025). 2009/2010 stay UNAVAILABLE — an uncorrected filer tagging error makes their inputs self-contradictory, and refusing them is correct (D27) |

Still needed for Phase 10's four documented cases: one that looks weak at base but
survives Severe stress. CCL's 2020-2022 distress and recovery may serve.

**Cached fixtures that are NOT demonstration companies** — they do not count toward the
v1 universe of 25-50 names and are not reported on:

| Ticker | CIK | Why it is cached |
|---|---|---|
| F | 37996 | negative fixture: no period produces both total_debt and ebitda, so no leverage metric can ever compute. Retained deliberately as a test that the tool refuses rather than inventing a number (D25). Also the reason D27's aggregate is cross-check-only — F resolves that tag in 13 periods and the pair in zero |
| KHC | 1637459 | second independent witness for D27's lease-inclusive branch (12 periods, no conflicts). A rule with one witness is worth less than one with two, so LUMN alone was not enough |

## Known dependencies (not open questions)
- **SIC code has no source in v1 data.** companyfacts JSON does not carry it, and
  docs/data-sources.md excludes SIC 6000-6799 (banks, insurers, REITs) from the
  universe — so that exclusion cannot be enforced programmatically until SIC has
  a source. The SEC submissions endpoint
  (https://data.sec.gov/submissions/CIK{cik:010d}.json) is the likely source; it
  is a scope addition to ingestion. Needed before Phase 10 validation.

- Pre-Task-9 audit (2026-09-10, report in docs/audits/) and its four blocking
  fixes (2026-09-11): composite toggles moved into config/composites.yaml with a
  config-driven test and a raise-on-missing guard (D28); fact identity widened to
  (tag, period type, period end) in selection, schema and writer, which fixed a
  crash that made KHC unstorable and a latent wrong-shape-wins path (D29);
  the writer's SUPERSEDED insertion sort now matches D16(4)'s accession tiebreak;
  the methodology's total_debt_ex_leases contradiction resolved (line 33 qualified,
  D6 amended to point at D27); and tests/test_real_companies.py added as the
  regression net — select -> map -> store over every cached filing, asserting
  against selection's own output rather than pinned counts. Verified the net
  catches the D29 bug by reverting the fix and watching all nine KHC cases fail.
  Branch coverage 95% -> 98%; store/writer.py 85% -> 99%.

## Tests
- 174 passing (7 setup + 3 env + 6 ingest/tickers + 12 ingest/companyfacts (all
  HTTP-mocked) + 4 cli wiring + 3 fixture guards + 31 selection + 10 mapping +
  45 real-data (9 invariants x 5 cached companies) + 53 store:
  constraint-rejection tests for every CHECK, the six-value
  data_status constraint, FK enforcement, STRICT + fallback, the circular-FK
  path, the fixture's exact stored rows, the fy-trap at storage, the
  supersession self-join, Q1/Q2 shapes, and append-with-history)
- Rule 5 unit handling corrected (D24): FOREIGN_UNIT now fires only for genuine
  ISO-4217 non-USD currencies. Measured on the three cached companies, spurious
  markers went from 3,845 to 1 (JNJ's single real EUR fact); selected facts and
  all mapped values unchanged.

## Non-blocking audit cleanup (2026-09-11)
- Findings 8, 9, 10-12, 13, 14 from docs/audits/2026-09-10-pre-task-9-audit.md
  cleared. Two decisions written down that had only ever been made in
  conversation (D30: no currency column, no source_url column) and one that had
  never been made at all (D31: the cache window is exclusive — nothing chose the
  original `>`). D2 amended: "migration is mechanical via SQLAlchemy" predated
  D22 removing SQLAlchemy from the stack.
- docs/data-sources.md gained a `## Codes` section documenting both vocabularies
  separately — 4 data-quality event codes and 6 UNAVAILABLE reason codes. The
  audit had listed AMBIGUOUS_FYE and NO_FYE_ANCHOR as event codes; they are fact
  reason codes and never become data_quality_events rows.
- Measured across all five cached companies: CANDIDATE_TAG_DISAGREEMENT 82 events
  (LUMN 15, F 32, JNJ 16, KHC 19, CCL 0) and 2 FOREIGN_UNIT facts (JNJ, KHC).
  Every other code is synthetic-only.
- Both new config tests were verified by sabotage: re-hardcoding 24h into cache.py
  fails test_max_age_hours_is_config_driven and nothing else; reverting `>=` to `>`
  fails test_cache_at_exactly_max_age_is_stale and nothing else.
- Finding 14's dead FileNotFoundError fallback in fingerprint.py needed no work —
  the D28 rewrite had already removed it. Finding 15 left alone by decision (Phase
  10's job; several assumptions need more companies before they can be exercised).

## In progress
- nothing

## Known bugs
- none

## Open questions
- Which 25-50 companies form the v1 universe? (US-listed, non-financial, 3+ years of 10-K data)

## Next priorities
- Task 9 — composite concepts (total_debt / net_debt / ebitda / fcf) with a test per
  rule in the methodology. One open item carries in: the short_term_debt/DebtCurrent
  double-count risk flagged in Task 7. (config/composites.yaml now exists and holds
  both toggles, and store/fingerprint.py reads them from it and raises on a missing
  key — D28. Task 9 must add component_aggregate_tolerance to that allowlist, since
  it changes whether total_debt computes at all.)
