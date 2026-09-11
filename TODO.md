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
- [ ] Task 10 (Phase 4): integrity checks + per-period data-quality summary; a failing
      period is stored, marked integrity = FAIL, and excluded from scoring. Passing and
      failing fixture per check
- [ ] Task 11 (Phase 5): net_debt_to_ebitda, ebit_interest_cover, current_ratio end to
      end on a real cached company, with provenance printed

## Later
- See docs/build-plan.md
