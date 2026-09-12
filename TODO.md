# TODO

Ordered. Top unchecked item is next.

## Phase 0 - spec
- [ ] Read docs/credit-methodology.md end to end; be able to explain every formula
      and the stress propagation rules
- [ ] Choose the v1 company universe (25-50 names)
- [ ] Settle the remaining open question in PROJECT_STATE.md (company universe)

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

## Phase 9/10 inputs raised by Task 10
- [ ] Phase 10 universe selection must cover `debt_subset`: it has one usable witness
      (JNJ), since lease-inclusive filers have total_debt_ex_leases UNAVAILABLE and CCL
      reports no `Liabilities` tag. Needs filers with plain debt AND a Liabilities tag
- [ ] Phase 10 selection must treat headline-metric coverage as a selection criterion:
      JNJ resolves OperatingIncomeLoss in only 6 of 19 periods, so the designated
      strong reference company is the thinnest evidence for both headline metrics —
      two of five demonstration companies now have a tag-map hole in a headline metric
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
- [ ] Phase 6: resolve "excluded from scoring until reviewed" — build a review
      mechanism or amend the methodology (open question in DECISIONS.md)

## Later
- See docs/build-plan.md
