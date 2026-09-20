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
9. CLI: `fetch`, `metrics`, `score`, `stress`, `export-evidence`, `validate-memo`
10. Test suite (see below)
11. Validation on 25–50 companies including four demonstration cases

**Output of v1 is a CLI and a set of exported reports (markdown/CSV).** No web UI.

## v2 (after v1 is complete and validated)

- Dashboard. Decision point: a Python dashboard library (one language, fast) versus a
  proper web frontend (Next.js). Default is the Python option unless there's a reason.
- **Sector-specific threshold sets — the first thing v2 should take up.** Moved here from
  v3 on 2026-09-20: the v1 final audit assessed it as having crossed from anecdote to
  pattern, on three independent instances (CCL's liquidity in D48, CCL's ~0.19% tonnage-tax
  effective rate in D55, and the 7-of-43 negative-working-capital liquidity finding in
  D72a). Still correctly parked for v1 — a sector framework over 43 companies across 21 SIC
  groups would be fitting noise.
- Monitoring / change detection across periods (period-over-period credit change summary)
- Quarterly data
- Local-LLM option for the memo workflow (see `docs/ai-governance.md`)

## v3 / maybe

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
period with a failing check is excluded from scoring **and, since D76, computes no metric
at all**; data-quality summary printed.

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

### Definition-of-done not met, recorded rather than deleted (2026-09-20)

**`tests/golden/` is empty.** Phase 10 above and the Testing strategy below both require
"four real companies with 10-K-verified numbers in `tests/golden/`" — metrics checked **by
hand against the filing**. That was never done. The directory has held only `.gitkeep`
since the repo was created.

What exists instead, and why it is not the same thing:

- **The four demonstration cases were chosen, by measurement** (D72d — SYK strong, LYB
  deteriorating, CHTR leveraged, TXRH resilient), with the rejected candidates and the
  reason for each rejection recorded. That satisfies the *demonstration* half of Phase 10.
- **`tests/test_real_companies.py` pins real-data expectations** across the five fixture
  companies, and runs structural invariants over all 105 cached payloads (D68).

Neither is an independent check against the source document. Every pinned figure was
produced by this engine, so the whole suite shares one failure mode: **if the engine
misreads a filing consistently, nothing here would notice.** A hand-verified golden set is
the only test in the plan that would, which is why it was specified — and it is the one
thing in v1 specified and not built. It stays on the list rather than being quietly
dropped, because deleting an unmet requirement is how a plan stops being evidence.

## Task sequence

Every task names the phase it belongs to. This list and the phase list above are the
same plan at different granularity and must stay in step — if a phase has no task, the
list is incomplete.

Task order is not always phase order: Phase 5's composite concepts come before Phase 4's
integrity checks because the checks depend on them (see Task 9). Where they interleave,
the task order is the one to follow.

1. (Phase 1) Create the repo, `pyproject.toml`, layout, `.gitignore`, empty `pytest` run.
2. (Phase 1) Copy the four docs and `CLAUDE.md` in; create `config/*.yaml` with the
   defaults from the methodology.
3. (Phase 2) Implement `ingest.fetch_company_tickers()` and `ingest.ticker_to_cik()` with
   a cached copy of `company_tickers.json`.
4. (Phase 2) Implement `ingest.fetch_companyfacts(cik)` with User-Agent, rate limiting,
   raw cache, `--force`, and a `credit-risk fetch <ticker>` CLI command wired to it.
   Tests with mocked requests.
5. (Phase 3) Build `tests/fixtures/companyfacts_minimal.json` by hand: two fiscal years,
   one restated value, one concept only available under a fallback tag, one quarterly
   fact that must be excluded.
6. (Phase 3) Implement fact selection (`normalise.select_annual_facts`) against that
   fixture until every expected row matches.
7. (Phase 3) Implement tag mapping with `source_tag` recording; test the fallback case.
8. (Phase 3) Design and create the SQLite schema (`companies`, `filings`, `facts`,
   `concepts`, `metrics`, `assumptions`, `overrides`, `scores`, `warnings`) — write the
   DDL, review it, then implement. Stress tables are deferred to Phase 8 (DECISIONS D20).
   *Delivered as 14 tables at Task 8, 18 once Phase 8 added the three stress tables and
   `warning_evidence`.*
9. (Phase 5) Implement composite concepts (`total_debt`, `net_debt`, `ebitda`, `fcf`)
   with every rule in the methodology and a test per rule. **Before Task 10:** the
   `Debt ⊆ liabilities` check tests `total_debt_ex_leases`, and the abnormal-movement
   check covers composite concepts as well as reported ones, so the integrity checks
   cannot be completed until the composites exist.
10. (Phase 4) Implement the integrity checks from the methodology and the per-period
    data-quality summary: a period with a failing check is stored but marked
    `integrity = FAIL` and excluded from scoring. Each check needs a passing and a
    failing fixture. The completeness and fallback-count half of the summary is already
    queryable (`store.queries.data_quality_by_period`).
11. (Phase 5) Implement the first three ratios (`net_debt_to_ebitda`,
    `ebit_interest_cover`, `current_ratio`) end-to-end from a real cached company, with
    provenance printed.
    **Phase 5 completed 2026-09-12:** the remaining fourteen followed in the same
    pass, giving all seventeen in the metric table. ROA and ROE stay dropped.

## Testing strategy

- **Unit tests per formula** using small hand-built dictionaries with expected values
  computed by hand, not by the code.
- **Edge-case fixtures** covering: missing revenue, missing D&A, zero revenue, negative
  EBITDA, negative FCF, negative equity, zero debt, zero and missing interest expense,
  restated value, missing middle year, duplicate fact, a 300%+ jump.
- **Golden tests**: four real companies with 10-K-verified numbers in `tests/golden/`.
  **Not built — see "Definition-of-done not met" above.**
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
