# Project state

_Update at the end of every working session._

## Phase
Phase 1 complete. Phase 2 (SEC ingestion) complete — Task 4 done. Phase 3 next.

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
  (0.014s, no network round trip).
- 27 tests passing (6 setup + 3 env + 6 ingest/tickers + 9 ingest/companyfacts (all
  HTTP-mocked) + 3 cli wiring)

## In progress
- nothing

## Known bugs
- none

## Open questions
- Which 25-50 companies form the v1 universe? (US-listed, non-financial, 3+ years of 10-K data)

## Next priorities
- Task 5 — hand-build tests/fixtures/companyfacts_minimal.json (2 fiscal years, one
  restated value, one fallback tag, one quarterly fact that must be excluded)
