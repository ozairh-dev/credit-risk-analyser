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
  flagged for Phase 9/10: short_term_debt/DebtCurrent overlap — resolved at
  Task 9 by D32's ST_DEBT_SCOPE_UNCERTAIN guard; equity
  disagreement warnings will be routine for NCI companies; pretax_income likely
  needs tag variants added.

- Task 8 (2026-09-10, on Opus per the model protocol) — SQLite schema, designed
  and approved before implementation per build-plan's two-stage requirement,
  then built with four owner amendments. src/credit_risk/store/: schema.py (raw
  DDL, 14 tables, 12 indexes, STRICT where supported with a tested fallback
  — 15 tables since Task 10 added integrity_results, D37),
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

- Task 9 (2026-09-11, on Opus — owner approved proceeding after a Fable
  handoff was offered) — composite concepts. metrics/composites.py:
  total_debt with four mutually exclusive branches (plain components with the
  D26 reconciliation, aggregate-only, lease-inclusive per D27, NO_DEBT_DATA),
  total_debt_ex_leases (both lease kinds excluded, D33), net_debt (STI
  zero-by-absence, D33), ebitda (labelled, never falls back to EBIT), fcf, and
  gross_profit's calculated fallback. DebtCurrent guard added as D32
  (ST_DEBT_SCOPE_UNCERTAIN; fires zero times in-sample — latent-hole guard).
  Four methodology gaps resolved and written into the doc (D33); deviation
  edge semantics owner-decided (D34: both-zero computes, contradiction and
  negative input refuse; abs() only on the difference). Store: concepts.detail
  column added (zero-by-absence + refusal figures), composites stored with
  concept_inputs provenance and no accession, gross_profit fill skips
  mapping's UNAVAILABLE row to keep re-store idempotent. Branch counts on real
  data match D26/D27's tables exactly: LUMN 15 lease-incl + 2 mismatch (93.6%,
  99.8%), CCL 17 components + 1 mismatch (2010-11-30, 7.9%), JNJ 18
  components, KHC 12 lease-incl, F 3 components. Sabotage-verified: flipping
  branch precedence emits LUMN 2009's 14,507M double-count and fails exactly
  the expected 3 tests; hardcoding the tolerance fails exactly the
  mismatch-related 8.

- Task 10 (2026-09-11, Opus) — integrity checks + data-quality summary.
  metrics/integrity.py: eight stored checks over four outcomes
  (PASS/WARN/FAIL/SKIP), plus abnormal movement as D23 events. New
  integrity_results table keyed (cik, period_end, check_name); the period
  verdict is derived in a query, never stored (D37). New config/integrity.yaml,
  deliberately outside D18's fingerprint (D38). Summary now separates four
  kinds of absence — reported / calculated / missing_tags / refused_composites
  — so a refused composite no longer inflates the tag-gap count.
  Five decisions: D36 day-gap continuity, D37 own table, D38 config home,
  D39 zero-denominator SKIP + two-row split, D40 phantom-period exclusion.
  Real data: zero FAILs anywhere; the only warnings are KHC 2014-12-28
  (23.4%) and 2016-01-03 (7.0%) balance-sheet, both genuine merger-era
  presentation gaps. Sabotage-verified: subset `<=` -> `<` fails exactly the
  equality test; disabling D40 fails exactly LUMN's and KHC's continuity
  tests.

- Task 11 (2026-09-11, Opus) — the first three ratios end to end.
  metrics/ratios.py: net_debt_to_ebitda, ebit_interest_cover, current_ratio,
  with every coverage edge case and a REASON_KIND mapping splitting reasons
  into EVIDENCE / GAP / NEITHER (D9, D41a) — three kinds, not two, because an
  unlevered company must not cap the grade. New pipeline.py assembles the
  stages in their one correct order; new `credit-risk metrics <TICKER>` prints
  each ratio with its full provenance chain read back from the database —
  ratio -> composite -> composite -> tag -> filing. Metrics are
  append-with-history with metric_inputs provenance and no accession.
  D41 records six calls. Measured: CCL 2019 recomputed by hand end to end
  (ebitda 3,276+2,160=5,436; net_debt 11,502-518=10,984; ratio 2.0206).
  Sabotage-verified: letting NEGATIVE_EBITDA fall through to a value fails the
  evidence-distinction test plus exactly the three companies that have such a
  period.

**Five of the seven coverage edge cases have zero real-data witnesses** and are
synthetic-only: `NO_INTEREST_NO_DEBT`, `INTEREST_MISSING_WITH_DEBT` in both its
forms (interest missing, and interest zero), `ZERO_DENOMINATOR`,
`NEGATIVE_DENOMINATOR`. Measured across all 89 cached company-periods:
`interest_expense` resolves positively in every one, `total_debt` is never
exactly zero, and `current_liabilities` is never zero or negative. Only
`NEGATIVE_EBITDA` (6 periods) and `NEGATIVE_EARNINGS` (10) have real witnesses.

- Phase 5 completed (2026-09-12, Opus) — the remaining fourteen ratios; all
  seventeen in the metric table now implemented. Shared shapes
  (_simple_ratio, _ebitda_ratio, _debt_denominated, _interest_cover) write the
  general denominator rules once; four metrics keep their own functions because
  their edge cases are genuinely unlike the rest. Four new reason codes, all
  classified: NO_DEBT (NEITHER, D42a), NON_POSITIVE_CAPITAL, INVENTORY_UNKNOWN,
  INSUFFICIENT_DATA (GAP). D42 records five calls. CCL 2019 recomputed by hand
  across all seventeen before pinning. Sabotage-verified: making quick_ratio's
  cross-period inventory rule per-period fails two unit tests plus exactly
  LUMN, the only company with partial inventory.

- Pre-Phase-6 audit fixes (2026-09-12, Opus) — findings 2, 3, 4, 5, 7 and 8
  from docs/audits/2026-09-11-pre-phase-6-audit.md cleared. revenue_growth now
  pairs on eligibility AND window (D43): LUMN recovers a value lost to a
  phantom period, 16 -> 17. Three superseded ratio helpers deleted (D44) —
  they had already diverged on NEGATIVE_DENOMINATOR payload within a single
  phase. Three undefended branches tested; the metrics CLI and pipeline.py
  now have tests, and test_real_companies.py's fixture drives pipeline.analyse
  rather than reassembling the stages. Coverage: ratios 82% -> 100%,
  pipeline 42% -> 100%, cli 29% -> 90%, total 90% -> 98%.
  **Findings 1 and 6 are NOT fixed — they are company-set problems, not code.**

- Phase 6 (2026-09-12, design on Fable per the model protocol, build on Opus)
  — scoring engine. scoring/engine.py: band lookup (one bisect_right for both
  directions, pinned to the methodology's two printed tables including every
  edge), category aggregation, graduated grade cap, and the explain output.
  scoring/fingerprint.py over thresholds.yaml only, disjoint from the
  composite fingerprint (D45). Five component treatments, not three — D41's
  kinds plus not_yet_implemented for Phase 7's trend, which would otherwise
  cap every company for an unbuilt feature. D45-D48 record the design, the
  three previously-open questions, the graduated cap, the schema amendments
  and CCL's liquidity sector finding.
  `credit-risk score <TICKER>` prints the explain output with the cap line
  leading. Sabotage-verified: disabling the cap fails all five companies'
  shape tests plus JNJ's and CCL's; dropping EVIDENCE instead of scoring it
  zero fails two unit tests and four companies' reconciliation.

- Phase 7 (2026-09-12, Opus) — trends and early warnings. trends/engine.py:
  seven trend rules over three consecutive eligible years, the eleven warning
  indicators, and the escalation rule with its cause recorded.
  trends/fingerprint.py is the third disjoint fingerprint (composites, scores,
  trends). D49-D52. **D43 discharged, not cited:** seven eligibility tests and
  seven window tests, one per trended metric on its own series, plus a guard
  that fails if a metric is added without them. Sabotage-verified both halves
  independently — computing eligibility on all periods rather than the rule's
  own series, and dropping the window test — each failing its own seven.
  Phase 6's ebitda_margin_trend transitioned from not_yet_implemented to a
  real component without the row shape changing, exactly as designed.

## Phase 6 re-baseline from Phase 7 (D50)

`ebitda_margin_trend` became a real scoring component, so business performance
is now a mean of two rather than one. **Nine of 85 grades moved:**

| Company | Moved | Before -> after |
|---|---|---|
| LUMN | 6 | 3x2 4x2 5x8 6x6 -> 3x2 4x3 5x4 6x9 |
| F | 2 | 4x14 5x2 6x2 -> 4x13 5x2 6x3 |
| CCL | 1 | 3x5 4x8 5x3 6x3 -> 3x4 4x9 5x3 6x3 |
| JNJ | 0 | unchanged |
| KHC | 0 | unchanged |

CCL 2019-11-30 is the clearest case: EBITDA margin fell **2.19pp** against a
2pp threshold in the year before COVID, so the trend scores 0 and the grade
moves **3 -> 4**. The component working, not a regression.

**JNJ and KHC moved no grade but changed behaviour**: `ebitda_margin` never
resolves for either, so their trend component went from *excluded from
counting* to a **data gap**. Their grades were already capped for other
reasons, so the change is invisible in the grade and visible only in
`score_components.treatment`. A change that moves no number is still a change.

- Phase 8 step one (2026-09-12, Fable) — stress config settled, engine NOT
  built (D20's tables stay deferred until it is). D53: fixed_cost_share stays
  0.3 with a printed-in-output duty (grade swing across [0.2, 0.7] measured at
  <= 1 level in all 42 mode-comparable periods, but stressed EBITDA swings
  2.1x for CCL 2019 Severe and flips sign for LUMN); new_debt_rate becomes
  override -> implied-if-in-band [2%, 12%] -> default 6%, because both failure
  directions occur in-sample (Ford 287-860%, JNJ 0.51-0.67%); presets keep
  additional_debt: 0 deliberately; the ETR missing-inputs rule and the
  negative-base-margin path are now written in the methodology.

- Phase 8 step one part two (2026-09-13, Opus) — remaining stress config
  settled (engine built in step two, below). D54: floating_share stays 1.0 but its
  justification was *corrected* — the fixed/floating split is unreachable in
  companyfacts (measured: no rate-split USD amount in any of the five), and
  1.0 is not cheap conservatism since it moves the stressed grade in four
  periods (CCL 2015/2018 fall 3->4 at Severe). D55: default_tax_rate stays
  0.21 on statutory grounds against a 16.31% in-sample median, recorded so
  the gap does not read as an error. D56: the stress fingerprint covers
  policy keys only; per-run assumptions are columns — a value that varies per
  run is not a config version. D57: stressed scores carry base trend
  verdicts, and the liquidity exclusion is surfaced in the output.

- Phase 8 step two (2026-09-13, Opus) — the stress engine and D20's three
  deferred tables. stress/engine.py: both EBITDA modes, the full propagation
  block, new_debt_rate resolution with source and reason, driver attribution
  (each shock alone), and the sensitivity grid computed on demand.
  stress/fingerprint.py is the fourth disjoint fingerprint. D58-D64.
  `credit-risk stress <TICKER> [--grid]`.
  **Two findings came out of implementing it:**
  D63 — the two EBITDA modes move a loss-making company's stressed EBITDA in
  OPPOSITE directions (constant margin shrinks the loss, operating leverage
  deepens it); both are arithmetically right and mode B is the honest one.
  D64 — the base scenario is NOT a no-op for cash-flow metrics: five of seven
  metrics reproduce base exactly, but fcf_margin and fcf_to_debt drift by a
  median 59% because the propagation approximates CFO with working capital
  flat while the base composite uses reported CFO. D61a's decision to store
  the base run is what exposed it.
  Sabotage-verified: breaking driver isolation and dropping the basis-point
  conversion each fail their own tests.

## Stress coverage (Phase 8/10 input, measured 2026-09-12)

**Stress is structurally impossible for JNJ and KHC.** Both EBITDA modes need
`revenue` and `ebitda` in the same period — the mode-A margin and the mode-B
cost base are both built from that pair — and JNJ's never overlap while KHC
has no revenue at all. The metric-coverage gap propagates directly into
Phase 8: **two of five demonstration companies cannot be stress tested in any
period.** Mode-comparable coverage: LUMN 18, CCL 15, F 9 periods (42 total).
Implied new-debt rates are sensible in 59 of 65 measurable periods; the six
outliers are Ford's three (captive finance, D25) and JNJ's three ZIRP-era
lows — both directions, which is what made D53's band necessary.

**The fixed/floating debt split is unreachable** (measured 2026-09-13): across
all five payloads, zero `FloatingRate`/`VariableRate` tags and no
USD-denominated rate-split amount anywhere, so `floating_share` cannot be
derived per company from XBRL at all. **Effective tax rates are computable in
only 39 of 87 periods**, and 10 of those 39 fall outside [0, 50%] — so
`default_tax_rate` is reached in 48 of 87 periods (55%), the dominant path.

## Trends and warnings on real data (measured 2026-09-12)

| Company | Warnings | Escalated | Periods with escalation |
|---|---|---|---|
| LUMN | 46 | 39 | 11 |
| CCL | 38 | 27 | 6 |
| JNJ | 20 | **0** | **0** |
| F | 19 | 3 | 1 |
| KHC | 16 | 6 | 2 |

**JNJ never escalates** across 18 periods — the negative witness, and
consistent with it being the strong reference company.

Structurally impossible trends, inherited from the known tag-map gaps:
`ebitda_margin` for JNJ and KHC, `revenue_growth` for KHC, `fcf` for Ford.
Ford's `net_debt_to_ebitda` and `total_debt` trends have exactly one window
each — technically possible, evidentially meaningless.

## Scoring on real data (measured 2026-09-12)

| Company | Scored | Uncapped | Binding caps | Grades |
|---|---|---|---|---|
| **CCL** | 19 | **13** | 1 | 3×5, 4×8, 5×3, 6×3 |
| LUMN | 18 | 0 | 2 | 3×2, 4×2, 5×8, 6×6 |
| F | 18 | 0 | 3 | 4×14, 5×2, 6×2 |
| JNJ | 18 | 0 | **15** | **3×18** |
| KHC | 12 | 0 | 0 | 3×1, 4×5, 5×6 |

**JNJ is the cap-visibility witness and the clearest argument for the company
work:** it scores **86-97** — uncapped grade 1 — and shows **grade 3 in every
one of its 18 periods**, because `ebit` and `revenue` never resolve together
so coverage and business performance keep emptying. Without the cap line, JNJ
and LUMN's best periods are indistinguishable in the output at grade 3.

CCL's arc is the band validation: 2.1-3.1x leverage scoring 4-5 through the
crisis, grade 3 at its 2015-2019 peak, grade 6 through the COVID negative-EBITDA
years, then 5, 5, 4 as it recovers. One grade per year of recovery, no jumps.

## Metric coverage — all seventeen (Phase 10 input, measured 2026-09-12)

Periods producing a value. Company period counts: LUMN/F/JNJ/CCL 19 each, KHC 13.

| Metric | LUMN | F | JNJ | CCL | KHC | total |
|---|---|---|---|---|---|---|
| debt_to_ebitda | 14 | 3 | 6 | 14 | 10 | 47 |
| net_debt_to_ebitda | 14 | 3 | 6 | 14 | 10 | 47 |
| debt_to_capital | 15 | 3 | 18 | 17 | 12 | 65 |
| ebit_interest_cover | 15 | 7 | 6 | 16 | 10 | 54 |
| ebitda_interest_cover | 17 | 9 | 6 | 16 | 10 | 58 |
| current_ratio | 17 | 11 | 18 | 18 | 12 | 76 |
| quick_ratio | **2** | 11 | 18 | 18 | 12 | 61 |
| cash_to_current_liabilities | 17 | 11 | 18 | 18 | 12 | 76 |
| cash_to_debt | 15 | 3 | 18 | 17 | 12 | 65 |
| fcf_margin | 3 | **0** | 10 | 15 | **0** | 28 |
| fcf_to_debt | **0** | **0** | 18 | 17 | 12 | 47 |
| cfo_to_debt | 10 | 3 | 18 | 17 | 12 | 60 |
| capex_to_revenue | 6 | **0** | 10 | 15 | **0** | 31 |
| revenue_growth | 17 | 18 | 9 | 13 | **0** | 57 |
| ebitda_margin | 18 | 9 | **0** | 15 | **0** | 42 |
| ebit_margin | 18 | 9 | **0** | 15 | **0** | 42 |
| net_margin | 18 | 13 | 10 | 15 | **0** | 56 |

**Three structural gaps, all tag-map problems rather than thin luck:**

1. **Ford reports no `PaymentsToAcquirePropertyPlantAndEquipment` at all** — the
   tag is absent from its payload entirely, so `capex` never resolves, `fcf`
   never computes, and `fcf_margin`, `fcf_to_debt` and `capex_to_revenue` are
   **zero for Ford in every period**. LUMN resolves capex in only 6 of 18.
2. **JNJ's `revenue` and `ebit` periods do not overlap at all.** `ebit` resolves
   2010-2014, `revenue` 2017-2025 — the intersection is **empty**, so
   `ebit_margin` and `ebitda_margin` are not merely thin for JNJ but
   *structurally impossible*. The designated strong reference company cannot
   produce either margin in any period.
3. **KHC's revenue gap costs six of seventeen metrics** — every
   revenue-denominated ratio plus `revenue_growth`.

**Synthetic-only refusals, confirmed across all 89 company-periods:** `NO_DEBT`
never fires (`total_debt` is never exactly zero) and `NON_POSITIVE_CAPITAL`
never fires — negative equity does occur (LUMN 1 period, F 3) but
`total_debt + equity` stays positive throughout. Both are defended by unit
tests only.

**What this sharpens for Phase 10 selection:** a candidate must be checked for
`capex`, `revenue` *and* `ebit` resolving **over the same periods** before
adoption. Three of five current companies fail at least one, and JNJ's failure
is an empty intersection that per-concept period counts alone would not reveal.

## Integrity witness coverage (Phase 10 input, measured 2026-09-11)

How many of the five cached companies can actually exercise each check
end-to-end. A check with one usable witness is validated by one filer's
conventions, so Phase 10's universe selection should deliberately cover the
thin rows.

| Check | Witnesses | Periods | Companies |
|---|---|---|---|
| cash_subset | 5 | 76 | JNJ 18, CCL 18, LUMN 17, KHC 12, F 11 |
| current_assets_subset | 5 | 76 | JNJ 18, CCL 18, LUMN 17, KHC 12, F 11 |
| period_continuity | 5 | 82 | F 18, JNJ 18, CCL 18, LUMN 17, KHC 11 |
| revenue_non_negative | 4 | 62 | F 19, LUMN 18, CCL 15, JNJ 10 |
| balance_sheet_balances | 3 | 48 | F 18, JNJ 18, KHC 12 |
| current_liabilities_subset | 3 | 41 | JNJ 18, KHC 12, F 11 |
| **debt_subset** | **2** | **21** | JNJ 18, F 3 |

**`debt_subset` effectively has one usable witness.** Its second is Ford's 3
periods — from the company D25 retired as unusable — so Phase 10's selection
**must deliberately include filers reporting a `Liabilities` tag alongside
plain (non-lease-bundled) debt**. LUMN and KHC contribute zero periods because
every lease-inclusive period has `total_debt_ex_leases` UNAVAILABLE under D27,
and CCL contributes zero because Carnival reports no `Liabilities` tag at all
(D25's known limitation). This is the thinnest coverage in the check set and
the one most likely to ship untested behaviour.

Two figures corrected against the Task 10 proposal, both from measurement:
`debt_subset` has two witnesses rather than one (Ford's 3 periods qualify),
and splitting "current subset of total" into two checks (D39b) showed the
asset comparison has 5 witnesses while the liability comparison has 3 — the
combined row had hidden that asymmetry.

**Two tag-map gaps for Phase 9/10, not witness questions.** JNJ resolves
`OperatingIncomeLoss` in only **6 of 19 periods**, so the designated *strong*
reference company is the thinnest evidence for both headline metrics. That is
**two of five demonstration companies with a tag-map hole in a headline
metric** — KHC's revenue being the other. Phase 10's company selection must
treat headline-metric coverage as a **selection criterion**, not a property
discovered after adoption.

KHC resolves `revenue` in **zero of its 12 periods**. No candidate in `tag_map.yaml`
matches how Kraft Heinz tags revenue, so the non-negative-revenue check can
never run for it and no revenue-based metric will ever compute. Worth a tag
investigation before KHC is relied on for anything revenue-derived.

## Tests
- 623 passing, 36 skipped (7 setup + 3 env + 6 ingest/tickers + 12 ingest/companyfacts (all
  HTTP-mocked) + 4 cli wiring + 3 fixture guards + 31 selection + 10 mapping +
  42 composites (deviation edges, all four branches, guards, toggles, storage) +
  28 integrity (every check pass/fail/skip, the 1% boundary, D23's three codes,
  a real 52/53-week sequence, phantom periods) +
  53 ratios (seventeen formulas, every coverage edge case, the three reason
  kinds, quick_ratio's cross-period rule, revenue_growth's adjacency) +
  180 real-data (36 invariants x 5 cached companies) + 53 store:
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
  **Sharpened by the pre-Phase-6 audit into a blocker for demonstrating Phase 6:** four of
  the five current companies can never produce a five-category score, so every grade they
  generate is capped at 3 by D10 for coverage reasons rather than credit reasons. Only CCL
  clears the cap, in 13 of 19 periods. Ford can never score cash flow (no capex tag); KHC
  can never score business performance (no revenue); LUMN and JNJ top out at 4 of 5.
  Phase 6 can be BUILT on CCL alone — it exercises every scoring path — but cannot be
  demonstrated on this set without the output misleading a reader.

## Next priorities
- Phase 9 (evidence pack / AI governance workflow) and Phase 10 (company universe).
  The company-selection work is now the binding constraint on demonstrating anything:
  four of five companies cannot score uncapped, three of five cannot be stressed, and
  two of five cannot be stressed at all. See Open questions and the coverage tables.
- The company-selection work remains the blocker for *demonstrating* Phase 6: four of
  five companies can never score uncapped. See Open questions.

