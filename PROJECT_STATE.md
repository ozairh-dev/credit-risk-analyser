# Project state

_Update at the end of every working session._

## Phase
Phase 1 complete. Phase 2 (SEC ingestion) in progress — Task 3 done, Task 4 next.

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
- 15 tests passing (6 setup + 3 env + 6 ingest/tickers), all with mocked HTTP

## In progress
- nothing

## Known bugs
- none

## Open questions
- Which 25-50 companies form the v1 universe? (US-listed, non-financial, 3+ years of 10-K data)
- Keep operating leases in total debt by default? (currently yes, config-toggled)
- Default `fixed_cost_share` for stress mode B - keep 0.3 or vary by sector?

## Next priorities
- Task 4 — companyfacts fetcher with User-Agent, rate limit, raw cache (--force),
  reusing credit_risk/ingest/cache.py from Task 3
