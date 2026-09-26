# The benchmark

A frozen measurement of **quality of credit analysis**, built before any improvement was
made to the engine, so that "better" can be demonstrated rather than asserted.

Two rules govern it:

1. **It is not graded by the thing being tested.** Deterministic metrics are computed by
   `harness/score_*.py`. Anywhere judgment is scored, the grader is a separate agent with
   fresh context that never sees which version produced the output.
2. **Nothing in `src/` or `config/` changes to serve it.** The point-in-time filter is a
   payload transform (`harness/pit.py`), not an `as_of` parameter threaded through
   `normalise/selection.py`. Every engine module is byte-identical to `901ce53`.

## Status

| Part | What it measures | State |
|---|---|---|
| **A1** extraction accuracy | engine figures vs figures read from filing documents | **not built — descoped** |
| **A2** discrimination backtest | pre-event grades for real Chapter 11 filers vs survivors | **built and baselined** |
| **A3** failure-mode cases | eight credit situations, expected findings written first | **not built — descoped** |
| **A4** consistency | engine determinism | **built and passing** |
| **A4** LLM variance | five runs on one pack | **not built — nothing to run** |
| **A5** unsupported claims | unverified figures and unsupported qualitative claims | **not built — descoped** |
| rubric + hold-out | written grading rubric; dev/held-out split | split done for A2; **rubric descoped** |

A2 was built first because it is the part that can be wrong in the most expensive way —
a backtest with hindsight leakage produces a flattering number that looks rigorous.

**A1, A3, A5 and the grader rubric were descoped by the owner on 2026-09-26.** A5 and the
rubric are downstream of an LLM judgment layer that does not exist, so there is nothing for
them to measure; A1 and A3 were judged not to justify their cost on the available timeline.
They are recorded here as deliberately not built rather than deleted, because a benchmark
with parts removed silently is a benchmark whose coverage cannot be read off it. **The
consequence is specific and should be stated wherever the benchmark is cited: nothing in
what was built checks the engine's figures against a filing document.** That check is A1,
and the golden set of D77 remains the only instance of it — four company-years.

## Layout

```
benchmark/
├── README.md                      this file
├── cases/
│   └── a2_discrimination/
│       ├── failures.yaml          19 verified Chapter 11 cases, 5 rejected candidates
│       └── survivors.yaml         the 43 adopted companies as the survivor panel
├── harness/
│   ├── pit.py                     point-in-time payload filter
│   ├── run_a4.py                  A4 determinism assertion
│   ├── edgar_events.py            event sourcing from EDGAR
│   ├── assess.py                  one PIT assessment — failures and survivors share it
│   ├── build_a2_cases.py          regenerates failures.yaml
│   ├── run_a2.py                  runs the backtest, writes the raw record
│   └── score_a2.py                turns the raw record into metrics
└── results/
    ├── a2_raw.json                every assessment, unjudged
    ├── a2_scored.json             the metrics
    ├── a2_baseline.md             the readable V1 baseline, with its limits
    └── a4_determinism.json        the determinism result
```

`data/benchmark/raw/` holds the cached companyfacts for the failure cohort. It is
deliberately **separate from `data/raw/`** so the benchmark does not silently widen
`tests/test_real_companies.py`, which globs that directory — the exact accident D68
records. Both are gitignored.

## Reproducing

```bash
.venv/bin/python benchmark/harness/build_a2_cases.py   # regenerate the case file
.venv/bin/python benchmark/harness/run_a2.py           # ~20s, writes a2_raw.json
.venv/bin/python benchmark/harness/score_a2.py         # writes a2_scored.json
.venv/bin/python benchmark/harness/run_a4.py           # determinism; exit 1 on failure
```

`build_a2_cases.py` needs `data/benchmark/raw/` populated; the CIKs and the fetch are in
its docstring. Everything else runs offline from the cache.

## What the benchmark cannot measure

Stated here rather than only in each results file, because the limitations are mostly
shared and a reader should meet them before any number.

**It cannot measure calibration.** Nothing maps a grade to a default probability, a credit
spread or a loss rate, and no amount of this data could — the project has no default,
loss or rating data and cannot buy any at £0. Every grade remains a point on an internal
analytical scale. A2 measures *discrimination*: whether the engine ranked companies that
failed below companies that did not. That is a real and useful property and it is a
strictly weaker claim.

**The event sample is small and concentrated.** 18 events, of which 11 are 2020. XBRL does
not exist before ~2011, so the 2008-09 credit cycle — the most informative default period
in living memory — is unreachable. Every conclusion is conditioned on two shocks: COVID
and the 2022-23 rate rise.

**A backtest cannot separate "saw the vulnerability" from "was lucky about the shock".**
A 2018 balance sheet cannot contain COVID. What is testable is whether the pre-event
financials were already weak enough not to survive a shock. That is the question a credit
analyst asks, and it is narrower than "did the engine predict the default".

**Survivor false-positive rates are pseudo-replicated.** 43 companies observed at many
cutoffs are not many independent observations. Both the pooled rate and the
distinct-company share are reported, and they differ by more than a factor of two.

**It cannot measure whether the analysis would be *useful* to an analyst.** Nothing here
scores readability, whether the right question was asked, or whether a memo would survive a
credit committee.

**A4 proves only that the output does not move.** A consistently wrong engine passes it
perfectly. Determinism is a precondition for the rest of the benchmark meaning anything,
not evidence of correctness.

**Nothing built here checks a figure against a filing document.** That was A1, which is
descoped. The golden set (D77) remains the project's only external check and covers four
company-years — which on first contact found five engine defects, so the base rate of
defects per company-year hand-checked is not reassuring. **Every A2 number therefore rests
on figures verified only against the engine's own reading of the XBRL.**

**A benchmark frozen before the work is still a benchmark chosen by the person doing the
work.** The cases, the metrics and the flag rule were all selected by the same session that
will propose the improvements. The hold-out split limits that; it does not eliminate it.
The blind separate grader that rule 1 above describes was **descoped along with the judged
parts**, so rule 1 currently constrains nothing — there is no judged output to grade. It is
kept in place because it governs any future judged part, but it must not be read as a
control presently in force.
