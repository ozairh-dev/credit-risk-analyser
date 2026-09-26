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
| **A1** extraction accuracy | engine figures vs figures read from filing documents | not built |
| **A2** discrimination backtest | pre-event grades for real Chapter 11 filers vs survivors | **built and baselined** |
| **A3** failure-mode cases | eight credit situations, expected findings written first | not built |
| **A4** consistency | engine determinism; LLM variance over five runs | not built |
| **A5** unsupported claims | unverified figures and unsupported qualitative claims | not built |
| rubric + hold-out | written grading rubric; dev/held-out split | split done for A2 |

A2 was built first because it is the part that can be wrong in the most expensive way —
a backtest with hindsight leakage produces a flattering number that looks rigorous.

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
│   ├── edgar_events.py            event sourcing from EDGAR
│   ├── assess.py                  one PIT assessment — failures and survivors share it
│   ├── build_a2_cases.py          regenerates failures.yaml
│   ├── run_a2.py                  runs the backtest, writes the raw record
│   └── score_a2.py                turns the raw record into metrics
└── results/
    ├── a2_raw.json                every assessment, unjudged
    ├── a2_scored.json             the metrics
    └── a2_baseline.md             the readable V1 baseline, with its limits
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

**It cannot measure whether the analysis would be *useful* to an analyst.** No part of
this scores readability, whether the right question was asked, or whether a memo would
survive a credit committee. A4 and A5 measure consistency and unsupported claims — both
necessary, neither sufficient.

**It cannot validate the engine against filings at scale.** A1 checks a handful of
company-years by hand against source documents. Four companies found five defects (D77);
eight would find more. The benchmark measures the engine's *behaviour*, and only A1
measures whether it *reads a filing correctly* — on a sample small enough to count on
one hand.

**A benchmark frozen before the work is still a benchmark chosen by the person doing the
work.** The cases, the metrics and the flag rule were all selected by the same session
that will propose the improvements. The hold-out split and the separate blind grader
limit that, they do not eliminate it.
