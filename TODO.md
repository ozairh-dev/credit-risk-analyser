# TODO

Ordered. Top unchecked item is next.

## Phase 0 - spec
- [ ] Read docs/credit-methodology.md end to end; be able to explain every formula
      and the stress propagation rules
- [x] Choose the v1 company universe (25-50 names) — 43 adopted 2026-09-13 from 105
      screened, plus 5 retained fixtures (D65). Open since Phase 0
- [x] Settle the remaining open question in PROJECT_STATE.md (company universe) — D65

## Phase 1 - foundation
- [x] Task 1: repo, pyproject.toml, layout, .gitignore, passing pytest run
- [x] Task 2: docs + CLAUDE.md in place; config/*.yaml created with methodology defaults

## Phase 2 - ingestion
- [x] Task 3: fetch company_tickers.json, cache it, ticker -> CIK lookup
- [x] Task 4: fetch_companyfacts(cik) with User-Agent from .env, rate limiting,
      raw cache to data/raw/, --force flag; wire a `credit-risk fetch <ticker>` CLI
      command that calls it; tests with mocked HTTP

## Phase 3 - selection, normalisation, store
- [x] Task 5: hand-build tests/fixtures/companyfacts_minimal.json (2 fiscal years,
      one restated value, one fallback tag, one quarterly fact that must be excluded;
      also a bad-duration fact and an off-FYE instant fact). Expected answers in
      tests/fixtures/companyfacts_minimal_expected.md — owner to verify before Task 6
- [x] Task 6: select_annual_facts passes that fixture
- [x] Task 7: tag mapping with source_tag recorded; fallback case tested
- [x] Task 8: SQLite schema - write the DDL, review it, then implement
      (14 tables; stress tables deferred to Phase 8 per D20)

## Phase 4-5 - composites, integrity, metrics
Task order interleaves the phases here: composites (Phase 5) come before the integrity
checks (Phase 4) because the checks depend on them. See docs/build-plan.md.

- [x] Pre-Task-9 audit fixes: config toggles (D28), fact identity incl. period type
      (D29), methodology ex-leases contradiction, real-data regression net.
      Report: docs/audits/2026-09-10-pre-task-9-audit.md
- [x] Non-blocking audit cleanup: findings 8, 9, 10-12, 13, 14. Findings 6 and 7 were
      already covered by the real-data regression net. Finding 15 (unvalidated spec
      assumptions) is deliberately left for Phase 10 — several of its rows cannot be
      exercised until the universe has more companies
- [x] Task 9 (Phase 5): metrics/composites.py — total_debt (four mutually exclusive
      branches incl. the D26/D27 mismatch refusals), total_debt_ex_leases,
      net_debt, ebitda, fcf, gross_profit calculated fallback. DebtCurrent guard
      (D32); four spec gaps resolved in the methodology (D33); deviation edge
      semantics (D34). component_aggregate_tolerance joined the fingerprint
      allowlist. Branch selection and tolerance both sabotage-verified
- [x] Task 10 (Phase 4): metrics/integrity.py — eight checks over PASS/WARN/FAIL/SKIP,
      abnormal movement as D23 events, integrity_results table with a derived verdict,
      config/integrity.yaml, summary split into four kinds of absence. D36-D40.
      Witness coverage measured and recorded in PROJECT_STATE.md as a Phase 10 input
- [x] Task 11 (Phase 5): metrics/ratios.py — three ratios, all seven coverage edge
      cases, REASON_KIND splitting EVIDENCE/GAP/NEITHER (D41). pipeline.py assembles
      the stages; `credit-risk metrics <TICKER>` prints each ratio with its full
      provenance chain down to tags and filings
- [x] Rest of Phase 5 (2026-09-12): the remaining fourteen ratios — all seventeen
      implemented, four new reason codes classified, D42's five calls recorded.
      Full coverage table in PROJECT_STATE.md as a Phase 10 input

## Pre-Phase-6 audit (docs/audits/2026-09-11-pre-phase-6-audit.md)
- [x] Finding 2: revenue_growth pairs on eligibility AND window (D43)
- [x] Finding 3: three superseded ratio helpers deleted (D44)
- [x] Finding 4: the three undefended branches tested
- [x] Finding 5 + 8: metrics CLI and pipeline tests; fixture drives pipeline.analyse
- [x] Finding 7: D30(b) marked an obligation on the first exporter
- [ ] Finding 1 (BLOCKER for demonstrating, not for building): four of five companies
      can never produce a five-category score — every grade capped at 3 by coverage.
      Company-set problem; see Open questions in PROJECT_STATE.md
- [ ] Finding 6: debt_subset still has one usable witness (JNJ); same selection work
- [ ] Phase 6 must state the capped-category list in every explain output, so a capped
      grade is never mistaken for a judged one (required regardless of company set)

## Phase 9/10 inputs raised by Task 10
- [x] `debt_subset` coverage solved at set level, not per company (D66): 20 adopted
      companies witness it with 5+ periods each, against an 8+ target
- [x] Phase 10 selection treats headline-metric coverage as a selection criterion —
      applied as the joint-availability filter in the 2026-09-13 screen (D65). JNJ's
      6-of-19 OperatingIncomeLoss resolution is what demoted it to a fixture
- [ ] Tag-map gap: Ford reports no `PaymentsToAcquirePropertyPlantAndEquipment` at
      all, so capex never resolves and fcf_margin / fcf_to_debt / capex_to_revenue
      are zero for it in every period. LUMN resolves capex in 6 of 18
- [ ] Tag-map gap: JNJ's `revenue` (2017-2025) and `ebit` (2010-2014) periods do not
      overlap at all, so ebit_margin and ebitda_margin are structurally impossible
      for it — not thin, empty. Needs tag variants for one or both concepts
- [ ] Phase 10 selection must check capex, revenue AND ebit resolve over the SAME
      periods before adopting a company — per-concept counts hide an empty overlap
- [ ] Tag-map gap: KHC resolves `revenue` in zero of 12 periods — no candidate matches
      how Kraft Heinz tags it. Investigate before relying on KHC for anything
      revenue-derived
- [x] Phase 6: "excluded until reviewed" resolved by amendment — exclusion lasts until
      the data is corrected and re-ingested; v1 has no review path (D45)

## Phase 6
- [x] Scoring engine (2026-09-12): bands, categories, graduated cap (D46), explain
      output with the cap line leading, score fingerprint (D45), schema amendments
      (D47), CCL liquidity sector finding recorded not fixed (D48).
      `credit-risk score <TICKER>`
- [x] Phase 7 (2026-09-12): trends/engine.py — seven trend rules, eleven warning
      indicators, escalation with recorded cause, trend fingerprint. D49-D52.
      D43 discharged with 7 eligibility + 7 window tests, one per rule
- [x] Phase 8 step one (2026-09-12): stress config settled without building the
      engine — fixed_cost_share 0.3 kept with a print-in-output duty; new_debt_rate
      override -> band [2%,12%] -> default 6%; presets keep additional_debt 0
      deliberately; ETR missing-inputs rule written in (D53)
- [x] Phase 8 step one part two (2026-09-13): floating_share justification corrected
      (split unreachable, measured); default_tax_rate 0.21 on statutory grounds;
      stress fingerprint = policy keys only, per-run values as columns; stressed scores
      carry base trend verdicts; liquidity exclusion surfaced (D54-D57)
- [x] Phase 8 step two (2026-09-13): stress/engine.py + D20's three tables. Both
      modes, driver attribution, sensitivity grid on demand, five output duties each
      pinned by a test. D58-D64, including two findings from implementation: the modes
      diverge in direction for loss-makers (D63) and the base run is not a no-op for
      FCF metrics (D64). `credit-risk stress <TICKER> [--grid]`

## From the demonstration run (docs/audits/2026-09-13-demonstration-run.md)
- [x] D69 revenue refuse-on-disagreement + concept audit + ebitda_margin_plausible check
- [x] D70 FCF metrics excluded from the stressed grade
- [x] D71 ebit_interest_cover bands rebased on the observed distribution
- [ ] Escalation threshold calibration (D72b) — 31% of periods, 64% of warnings
- [ ] Sector thresholds (D48/D72a) — now two measured instances plus 7 companies on the
      liquidity finding, including P&G
- [ ] The never-failing fail-severity integrity checks remain synthetic-only (D72c) —
      measured 2026-09-17: **five of the six** never fail on real data; only
      `ebitda_margin_plausible` has a witness (4 CAG periods)

## Phase 9
- [x] Evidence export + memo validator (2026-09-16): export-evidence,
      prompts/credit_memo.md, validate-memo. D73-D74. Five-violation reality test run;
      invented figure and grade contradiction caught, legitimate rounding passes,
      fabricated source and true-numbers-false-claim missed by design

## v1 final audit (docs/audits/2026-09-14-v1-final-audit.md)
- [x] Finding 1 — stressed metrics inherit base refusals (D75). D70 re-measured after
      and kept: still load-bearing, 71 zero-shock grade changes without it
- [x] Finding 2 — the evidence exporter has tests: 16, one per D73 duty plus the
      no-artefact checks, every one sabotage-verified
- [x] Finding 3 — a fail-severity integrity FAIL suppresses every metric for the
      period (D76). CAG's 122.5% margin confirmed gone from the pack
- [x] Finding 5 — D32 status note corrected with its population; D29/D33/D36/D37/D41/
      D42 annotated as five-company-era counts
- [x] Finding 6 — README rewritten against measured numbers, calibration sentence intact
- [ ] Finding 4 was the three parked calibration items — still parked, see above

## Later
- See docs/build-plan.md
