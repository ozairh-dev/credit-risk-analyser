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

- [ ] Task 9 (Phase 5): total_debt / net_debt / ebitda / fcf with a test per rule in the
      methodology, including D26's COMPONENT_AGGREGATE_MISMATCH refusal. config/composites.yaml
      now exists (holds component_aggregate_tolerance); Task 9 adds include_operating_leases
      and include_st_investments to it, and must add the tolerance to the fingerprint
      allowlist in store/fingerprint.py (D18/D26)
- [ ] Task 10 (Phase 4): integrity checks + per-period data-quality summary; a failing
      period is stored, marked integrity = FAIL, and excluded from scoring. Passing and
      failing fixture per check
- [ ] Task 11 (Phase 5): net_debt_to_ebitda, ebit_interest_cover, current_ratio end to
      end on a real cached company, with provenance printed

## Later
- See docs/build-plan.md
