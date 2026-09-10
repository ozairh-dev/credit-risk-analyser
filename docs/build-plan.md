# Build plan

## v1 scope (the whole of it)

1. Ticker → CIK lookup and companyfacts fetch with raw cache
2. Fact selection (annual, deduplicated, restatement-aware) and tag normalisation
3. SQLite store with full provenance on every value
4. Integrity checks and data-quality summary
5. Metrics engine (every formula in `docs/credit-methodology.md`)
6. Scoring, grades, explain output
7. Trends and early warnings
8. Stress engine with presets, custom scenario, driver attribution, simple sensitivity grid
9. CLI: `fetch`, `analyse`, `score`, `stress`, `export-evidence`, `validate-memo`
10. Test suite (see below)
11. Validation on 25–50 companies including four demonstration cases

**Output of v1 is a CLI and a set of exported reports (markdown/CSV).** No web UI.

## v2 (after v1 is complete and validated)

- Dashboard. Decision point: a Python dashboard library (one language, fast) versus a
  proper web frontend (Next.js). Default is the Python option unless there's a reason.
- Monitoring / change detection across periods (period-over-period credit change summary)
- Quarterly data
- Local-LLM option for the memo workflow (see `docs/ai-governance.md`)

## v3 / maybe

- Sector-specific threshold sets
- Debt maturity and refinancing analysis (partly available in XBRL)
- Covenant headroom analysis
- Companies House ingestion
- Borrower comparison, watchlists

## Never (in this project)

Automated lending decisions, regulatory capital / Basel, black-box ML default
prediction, multi-agent systems, vector databases, microservices, paid data.

## Phases and definitions of done

**Phase 0 — Spec review (no code).** Owner has read all four docs and can explain
each metric formula and the stress propagation rules. Open questions logged in
`PROJECT_STATE.md`.

**Phase 1 — Repository foundation.** Git repo, Python project (`pyproject.toml`), layout
from `CLAUDE.md`, `.gitignore` covering `data/`, empty test suite passes, README stub.

**Phase 2 — Ingestion.** `fetch <ticker>` writes `data/raw/{cik}.json` with `fetched_at`;
respects rate limit and User-Agent; refuses to re-fetch within 24h without `--force`.
Test: mocked HTTP, cache behaviour.

**Phase 3 — Fact selection + normalisation + store.** Annual facts selected per
`data-sources.md`; restatements recorded; tag map applied with `source_tag` recorded;
SQLite schema created; provenance complete on every row. Test: a hand-built companyfacts
fixture with known duplicates, restatements and a fallback tag, checked value by value.
**This phase is where most of the time will go.**

**Phase 4 — Integrity + data quality.** All checks in the methodology implemented; a
period with a failing check is excluded from scoring; data-quality summary printed.

**Phase 5 — Metrics engine.** Every formula implemented as a pure function taking a
period's normalised concepts and returning a provenance-carrying result. Every edge case
row in the methodology has a test. No metric without a test.

**Phase 6 — Scoring.** Bands and weights read from `config/thresholds.yaml`; missing-data
rules implemented; explain output produced. Test: fixtures for a clean company, an
unlevered company, a negative-EBITDA company, a company missing interest expense.

**Phase 7 — Trends + early warnings.** Three-year fixtures for improving, stable,
deteriorating; escalation rule tested.

**Phase 8 — Stress engine.** Both EBITDA modes; presets; custom; driver attribution
(each shock alone); sensitivity grid. Test: hand-computed stressed values for one fixture.

**Phase 9 — Evidence export + memo validator.** `export-evidence` and `validate-memo`
per `ai-governance.md`.

**Phase 10 — Validation on real companies.** Universe of 25–50 US-listed non-financials
across sectors and risk profiles (owner approves the list). For four of them, metrics are
checked by hand against the 10-K and recorded in `tests/golden/`. Every tag-map fallback
that was needed is recorded. Demonstration cases documented: a strong borrower, a
deteriorating one, a highly leveraged one, and one that looks weak at base but survives
Severe stress.

**Phase 11 — Docs and write-up.** README, methodology finalised, decisions log complete.

## First ten tasks

1. Create the repo, `pyproject.toml`, layout, `.gitignore`, empty `pytest` run.
2. Copy the four docs and `CLAUDE.md` in; create `config/*.yaml` with the defaults from
   the methodology.
3. Implement `ingest.fetch_company_tickers()` and `ingest.ticker_to_cik()` with a cached
   copy of `company_tickers.json`.
4. Implement `ingest.fetch_companyfacts(cik)` with User-Agent, rate limiting, raw cache,
   `--force`, and a `credit-risk fetch <ticker>` CLI command wired to it. Tests with
   mocked requests.
5. Build `tests/fixtures/companyfacts_minimal.json` by hand: two fiscal years, one
   restated value, one concept only available under a fallback tag, one quarterly fact
   that must be excluded.
6. Implement fact selection (`normalise.select_annual_facts`) against that fixture until
   every expected row matches.
7. Implement tag mapping with `source_tag` recording; test the fallback case.
8. Design and create the SQLite schema (`companies`, `filings`, `facts`, `concepts`,
   `metrics`, `assumptions`, `overrides`, `scores`, `warnings`, `stress_runs`) — write
   the DDL, review it, then implement.
9. Implement composite concepts (`total_debt`, `net_debt`, `ebitda`, `fcf`) with every
   rule in the methodology and a test per rule.
10. Implement the first three ratios (`net_debt_to_ebitda`, `ebit_interest_cover`,
    `current_ratio`) end-to-end from a real cached company, with provenance printed.

## Testing strategy

- **Unit tests per formula** using small hand-built dictionaries with expected values
  computed by hand, not by the code.
- **Edge-case fixtures** covering: missing revenue, missing D&A, zero revenue, negative
  EBITDA, negative FCF, negative equity, zero debt, zero and missing interest expense,
  restated value, missing middle year, duplicate fact, a 300%+ jump.
- **Golden tests**: four real companies with 10-K-verified numbers in `tests/golden/`.
- **Integrity tests**: each check has a passing and a failing fixture.
- **Config tests**: changing a band edge in YAML changes the score; nothing is hard-coded.

## Complexity, honestly

Phases 3–5 carry most of the work and most of the learning. Expect the tag map to need
extending for most companies in the universe. Everything after Phase 5 is comparatively
mechanical because the hard decisions are already written down.

## Cost

£0. SEC data is free and public domain; SQLite is a file; nothing is hosted.

## Risks

| Risk | Mitigation |
|---|---|
| XBRL tag inconsistency across companies and years | ordered candidate tags in config; record every fallback; golden tests |
| D&A absent or split across tags | EBITDA goes UNAVAILABLE rather than guessed; extend tag map case by case |
| Fiscal year alignment and restatements | explicit selection rules; supersession records; fixture tests |
| Lease treatment changes leverage materially | toggle in config; always show ex-lease figure alongside |
| Scope creep | scope guard in CLAUDE.md; v2/v3 lists above |
| Owner learning curve | Phase 0 gate; every task explained in plain language; tests double as worked examples |
