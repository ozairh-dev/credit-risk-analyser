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
- [x] Phase 10 selection must check capex, revenue AND ebit resolve over the SAME
      periods before adopting a company — per-concept counts hide an empty overlap.
      Implemented as D65's joint-availability filter
- [~] **Tag-map gaps on F, JNJ and KHC — accepted, not fixed.** All three are now
      **fixtures retained for specific witness value, not demonstration companies**
      (D65), so none of these gaps affects a reported result. Ford reports no
      `PaymentsToAcquirePropertyPlantAndEquipment` at all, so capex never resolves;
      JNJ's `revenue` (2017-2025) and `ebit` (2010-2014) periods do not overlap at all;
      KHC resolves `revenue` in zero of 12 periods. Fixing any of them needs
      period-scoped tag candidates — a `tag_map.yaml` format change that one company
      cannot justify (D25), and the change v2 should make if the need recurs
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
- [~] **PARKED BY DECISION, not outstanding work** — the three calibration items (D72).
      Each was measured and argued; see PROJECT_STATE.md "Next priorities".
      - Escalation threshold (D72b) — **the "no evidence base" reason is retired
        (2026-09-26).** A2 measured an escalated warning reaching 50% of failures against
        37% of survivor company-cutoffs — 13 points of separation — so the layer hardly
        discriminates. This is evidence about the LAYER, not about which threshold to pick,
        and none is proposed. Phase B question now, with D82 behind it.
      - Sector thresholds (D48/D72a) — **three independent instances**: CCL's liquidity,
        CCL's ~0.19% tonnage-tax effective rate (D55), and the negative-working-capital
        liquidity finding including P&G. **The first item v2 should take up.**
      - The never-failing fail-severity checks (D72c) — five of the six never fail on real
        data; only `ebitda_margin_plausible` has a witness (4 CAG periods). `debt_subset`
        went from 21 runnable periods to 287 and still never fails, which is the outcome
        that would have changed the call.

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
- [~] Finding 4 was the three parked calibration items — still parked by decision, above

## Phase 11 — documentation and write-up (2026-09-20)
- [x] Staleness audit of the four original docs before touching them. `ai-governance.md`
      current; `credit-methodology.md` one stale count (31 -> 34 concepts);
      `data-sources.md` one five-company-era measurement, now flagged provisional;
      `build-plan.md` five items, all corrected
- [x] `docs/architecture.md` — nine stages, four disjoint fingerprint scopes, the
      three-kind reason model, where authority for each kind of decision lives
- [x] `docs/risk-scoring.md` — band tables generated from config and checked against
      `band_points`, missing-data treatments, the graduated cap, what is not calibrated
- [x] `docs/interview-notes.md` — five components, each with its hardest problem
- [x] `docs/case-study.md` — readable without the repo, calibration sentence verbatim
- [x] CLAUDE.md, PROJECT_STATE.md and TODO.md describe the finished state
- [x] **`tests/golden/` built 2026-09-20 (D77)** — CCL FY2019, YUM FY2023, MCK FY2023,
      BDX FY2009, read from the filing documents rather than the XBRL. 17 enforcing tests,
      sabotage-verified. Found five engine defects no other test could detect

## Engine defects found by the golden set — ALL FIXED 2026-09-20 (D78-D80)
- [x] **`d_and_a` rank order** (D80) — `prefer_largest_candidate` added; rank order assumed
      earlier candidates were broader and for MCD/MCK they were narrower. 16 periods,
      2 companies; MCD was understated 80-86%
- [x] **`cfo` tag-map gap** (D79) — continuing-operations variant added as a fallback.
      75 periods across 19 companies regain cfo, fcf, fcf_margin, fcf_to_debt, cfo_to_debt
- [x] **`short_term_investments` tag-map gap** (D79) — `OtherShortTermInvestments` added,
      26 periods across BDX/KO/SYK. **D77's summary said four defects; its own evidence file
      classified five.** This was the one the summary dropped
- [x] **`total_debt` double-count, two branches** (D78) — fixed as ONE mechanism, since
      fixing them separately would have been the fifth instance of the pattern they
      demonstrate. D32's containment rule generalised: cross-check where one exists, refuse
      where the two agree and nothing reconciles them, add where magnitudes differ
- [ ] **KNOWN, NOT FIXED: YUM FY2023 `total_debt`** overstated by 56 (0.5%). Its deviation
      is 5.36%, 0.36pp outside the component/aggregate tolerance, and its only aggregate is
      the gross figure which answers backwards. **No threshold was invented** — the
      deviation distribution is continuous from 0% to 100% with no bimodal gap, so unlike
      D69 nothing can be measured. Settling it needs footnote prose XBRL does not carry

## CLI defects — FIXED 2026-09-26 (D81)
- [x] **`credit-risk score` never ran in any v1 commit** (D81) — two wiring faults in
      `cli.py`: a 6-name unpack of `pipeline.analyse()`'s 8-tuple (`ValueError`), and a
      read of `report['trend_note']`, a key `explain()` has never returned (`KeyError`).
      Fault 2 was only observable once fault 1 was fixed. Presentational fix, `cli.py`
      only; no engine logic touched. Sabotage-verified against each fault separately
- [x] **Four CLI commands had no test at all** (D81) — `score`, `stress`,
      `export-evidence`, `validate-memo`. 6 tests added, 886 → 892 passing. The engine
      under `score` was tested heavily; nothing tested that the CLI could reach it
- [ ] **No check that every registered command is exercised.** The three untested
      commands beside `score` were found by reading `cli.py`, not by anything that would
      catch the next one. A test enumerating `app`'s registered commands and asserting
      each is exercised somewhere would close it. Not done — it is a testing-policy
      change, and D81 was deliberately scoped to the defect in front of it

## Benchmark — Phase A (2026-09-26, in progress)

Freeze a benchmark BEFORE any engine change, so improvement is demonstrated not asserted.
Engine, config and tests must stay byte-identical throughout Phase A.

- [x] **A2 external discrimination backtest** — 19 Chapter 11 cases verified from EDGAR
      Item 1.03 8-Ks with the petition date read from each document, 18 admitted, 43
      adopted companies as the matched survivor panel, point-in-time filtered so no
      restatement filed after the cutoff can leak in. Flag rule frozen at `grade >= 5`
      on band semantics (D82). Baseline in `benchmark/results/a2_baseline.md`
- [x] **Point-in-time harness** — `benchmark/harness/pit.py` filters the payload on
      `filed`, outside the engine, so no engine module changes. Without it D14/D15
      supersession would use post-bankruptcy restatements to "predict" the bankruptcy
- [x] Hold-out split for A2 — stratified by SIC group then deterministic by CIK, so it
      cannot have been chosen to flatter a version. 10 dev / 8 held-out
- [x] **A4 consistency — determinism** (`benchmark/harness/run_a4.py`): 7 companies x 3
      repeats, reversed order, and four explicit `PYTHONHASHSEED` values in fresh
      interpreters, all bit-identical across eleven output blocks. Asserts only that the
      output does not move, never that it is correct
- [~] **DESCOPED by owner decision 2026-09-26, not outstanding work.** A5 and the grader
      rubric are downstream of an LLM judgment layer that does not exist; A1 and A3 did
      not justify their cost on the available timeline; the LLM half of A4 has nothing to
      run five times. Recorded rather than deleted so the benchmark's coverage can be read
      off it:
      - A1 numerical and extraction accuracy — golden-set extension against filing
        documents. **This is the gap that matters: nothing built checks an engine figure
        against a filing. D77's four company-years remain the only external check**
      - A3 eight failure-mode cases with expected findings written first. Hertz already
        witnesses one of the eight (missing information that should reduce confidence)
      - A5 unsupported qualitative claims against a written rubric
      - the blind separate grader for judged output

## Proposal, not implemented — negative book equity from buybacks (2026-09-27)

An external review raised three claims about this project; two were wrong on their
central premise when checked against the actual code, config and git history (a
mismatched sample size and a look-ahead-bias claim disproved by direct testing — both
recorded in the session, not repeated here). **This is the one that held up.** Verified
against the code before writing this up (`scoring/engine.py`, `metrics/ratios.py`,
`config/thresholds.yaml`) — the mechanism is real; only the review's specific line
citations were wrong. Scoring engine untouched, per owner instruction — this is a
write-up only.

**The problem, with a live witness already in this repo.** `debt_to_capital =
total_debt / (total_debt + equity)` (`_debt_to_capital`, `metrics/ratios.py:198-213`;
it returns `UNAVAILABLE` only when `total_debt + equity <= 0` — deeply negative equity
that stops just short of that has no such guard). A
company that has bought back enough stock to push book equity deeply negative — without
quite exceeding total debt — produces a ratio above 1.0, and the band table
(`config/thresholds.yaml:42-45`) has no edge above 0.8: anything past it scores 0, the
worst band, with no further gradient. AutoZone is the exact case, already in this
README's own example output: `net_debt_to_ebitda 2.733, 6 pts` against `debt_to_capital
1.642, 0 pts` — **the two leverage components disagree by six points on the same
company, in the same category, for the same period.**

That is sharper than a cross-category framing alone would suggest. Two separate things
are happening:

1. **Within the leverage category**, `_score_category` (`scoring/engine.py:169`) takes a
   plain mean of `net_debt_to_ebitda` and `debt_to_capital`. Once equity is deeply
   negative from buybacks rather than from losses, book capital stops meaning what the
   ratio assumes it means — the company hasn't gotten riskier, it has returned capital —
   but the metric is averaged in as if it carried the same information content as the
   cash-flow-based `net_debt_to_ebitda`, pulling a 6 down to a 3.
2. **Across categories**, `score_period` (`scoring/engine.py:208`) sums each category's
   weighted contribution independently — nothing in `coverage` (8/10 for AZO) or
   `cash_flow` (7/10) can reach back and inform the `leverage` score. This is D45's
   design, working as specified; it just was not designed with this failure mode in mind.

Real capital structures do this deliberately and are not automatically weaker for it —
rating agencies routinely look through negative book equity from buybacks to
cash-flow-based leverage, which is exactly why `net_debt_to_ebitda` exists as a separate
component already. The engine computes the right evidence; it just doesn't reason about
it once `debt_to_capital` has gone unreliable.

**A candidate direction, not a spec.** Two shapes worth comparing rather than picking
blind:

- **Localized:** treat `debt_to_capital` the way `NON_POSITIVE_CAPITAL` already treats
  the fully-negative case (`_debt_to_capital`, same function) — when capital is positive
  but thin *because* equity is negative, drop the component from the leverage mean
  instead of scoring it 0, and let `net_debt_to_ebitda` carry the category alone. Smallest
  change, stays inside one function, but a company could then earn a full leverage score
  from one metric alone.
- **Cross-category overlay:** cap how far a weak `leverage` score can drag the total when
  `ebit_interest_cover` and `fcf_to_debt` both land in a top band — the shape the review
  suggested. Bigger change, touches `score_period`'s aggregation, and needs its own
  threshold for what "strong" means in each of those two metrics.

**Why this is not a quick patch.** Either direction changes real, already-published
grades for real companies — not just AZO, every negative-book-equity name in the 43. It
needs the same discipline as everything else that moved a number in this project: a
hand-computed unit test for the new behaviour, a before/after measurement across the 43
adopted companies (the D72/A2 pattern — freeze the measurement, then change the code, then
re-measure), a sabotage check, and its own DECISIONS entry with the alternatives this note
only sketches. Checked and this is genuinely leverage-specific, not a wider pattern:
`CATEGORIES` (`scoring/engine.py:36`) pairs `debt_to_capital` with a cash-flow-based metric
inside one category, but `liquidity`'s two components (`current_ratio`,
`cash_to_current_liabilities`) are both book-based and `cash_flow`'s two
(`fcf_to_debt`, `fcf_margin`) are both cash-based — neither mixes the two the way leverage
does, so this isn't the same shape recurring elsewhere. `cash_to_debt` and `cfo_to_debt`
aren't scored at all (not in `CATEGORIES`), so there's nothing there to fix.

**The closer parallel is already a parked, evidenced item, not a new discovery:**
liquidity's own bands already misjudge a real business-model pattern — 7 of the 43 adopted
companies score zero liquidity points despite negative working capital being ordinary for
their business (D48, D72a). Same shape as this one: a generic ratio misreading a deliberate,
non-distressed capital or working-capital structure. Worth deciding together rather than
fixing in isolation, since both are "the bands assume a balance-sheet shape most companies
have, and some companies deliberately don't."

**Measured whether this explains A2's 21% survivor false-positive rate**
(`benchmark/harness/negative_equity_check.py`, tracked and reproducible): 33.3% of the 21
flagged survivors (7) had negative book equity at a cutoff where they were flagged,
against 13.6% of the 22 never-flagged (3) — a real +19.7pp gap. But AZO and YUM, the two
companies with the most persistent negative equity in the entire 43-company panel (18/18
cutoffs each), were never flagged at all — so this is a partial contributor to the
false-positive rate, not the explanation for it.

## Proposal, not implemented — no cash-conversion metrics (2026-09-27)

Verified absence, not inference: `metrics/ratios.py`'s `METRICS` tuple has no CFO/EBITDA
ratio, no CFO-versus-net-income comparison, and no accrual-quality measure — the
`cash_flow` category comprises `fcf_to_debt` and `fcf_margin` only, checked directly
against the code. Carried over from the original brief's Phase B candidate list; not yet
given its own decision.

**The consequence stated plainly.** "Cash flow contradicting reported profitability" is a
named credit-analysis failure mode the engine currently has no way to detect. A company
with strong reported net income and deteriorating cash generation — the classic
aggressive-accrual warning sign — scores on `net_margin` and `revenue_growth` with nothing
flagging the divergence between them.

**Direction, not a spec.** `cfo_to_ebitda` and `cfo_to_net_income` are both computable from
concepts the engine already resolves (`cfo`, `ebitda`, `net_income`); the harder design
work is in the trend layer, not the ratio itself — a level alone says little, a
*diverging* trend against reported earnings is the actual signal. Needs the same
discipline as anything that would move a score: a hand-computed test, a before/after
measurement across the 43, and its own DECISIONS entry if it becomes a scored component
rather than a display-only metric.

## Proposal, not implemented — no refinancing or maturity-wall risk (2026-09-27)

Verified absence, not inference: `config/tag_map.yaml` maps no debt-maturity-schedule tag
— `LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths` and its multi-year
successors are absent, checked directly against the file. Carried over from the original
brief's Phase B candidate list; not yet given its own decision.

**The consequence stated plainly.** The engine can grade leverage and coverage as strong
in a period immediately before a large tranche of debt comes due, with nothing in the
output naming that as a distinct risk from ordinary leverage.

**Measure before designing, not the other way round.** Check this tag family's actual
resolution rate across the 43-company universe before building anything around it — the
same discipline D66 applied to `Liabilities`: "a check that not every filer can witness
must be a set-level target, never a per-company gate," and the same test should be run
before a tag becomes a metric. If coverage turns out thin, that finding — which maturity
tags exist and how often — is worth recording on its own before any code is written.

## Later
- See docs/build-plan.md. First two items for v2: sector thresholds (D48/D72a), then the
  hand-verified golden set above.
