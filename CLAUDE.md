# Credit Risk Analyser — project rules

## What this is

A portfolio-scale credit-risk analysis tool for US-listed, non-financial companies.
It pulls SEC XBRL financial data, normalises it into standard concepts, computes credit
metrics, scores and grades the borrower, flags deterioration over time, and runs
deterministic stress scenarios. Every number carries its source.

It is not a bank rating model, a regulatory capital model, or a substitute for credit
judgement. Say so in any user-facing output.

## Non-negotiable rules

1. **The deterministic engine is authoritative.** Ratios, scores, grades, trends,
   warnings and stress results are computed by code only. No LLM anywhere in that path.
2. **Every stored number has a `data_status`:** `REPORTED | CALCULATED | ESTIMATED |
   ASSUMED | AI_INTERPRETED | UNAVAILABLE`. Never mix them, never silently upgrade one.
3. **Never fabricate.** A missing input produces `UNAVAILABLE` with a reason code, and
   anything that depends on it is also `UNAVAILABLE`. No default values for financial inputs.
4. **No infinities, no misleading numbers.** Division by a zero or negative denominator
   returns `UNAVAILABLE` plus a reason code (rules in `docs/credit-methodology.md`).
5. **Reported values are never overwritten.** Restatements and analyst overrides are stored
   alongside the original with a supersession or override record.
6. **Thresholds, weights, band edges and stress defaults live in `config/*.yaml`,** never
   in code.
7. **Cost is £0.** No paid APIs, no paid hosting. SEC data only in v1.
8. **No runtime AI in v1.** AI use is a manual, documented workflow — see
   `docs/ai-governance.md`.
9. **Fail safe.** Bad input raises a validation error or produces `UNAVAILABLE`. It never
   produces a plausible-looking wrong number.

## Stack (fixed for v1 — do not add to it)

Python 3.11+, pandas, pydantic, SQLite via SQLAlchemy, requests, typer (CLI), pytest,
PyYAML. No web framework, no frontend, no Postgres, no Docker, no vector database.
The UI is a v2 decision recorded in `docs/build-plan.md`.

## Repository layout

```
credit-risk-platform/
├── CLAUDE.md               this file
├── PROJECT_STATE.md        what is done, in progress, broken
├── TODO.md                 prioritised next work
├── DECISIONS.md            why we chose what we chose
├── README.md
├── config/
│   ├── tag_map.yaml        XBRL tag → internal concept mapping
│   ├── thresholds.yaml     metric bands, weights, grade edges
│   └── stress.yaml         preset scenarios and propagation defaults
├── docs/
│   ├── data-sources.md
│   ├── credit-methodology.md
│   ├── ai-governance.md
│   └── build-plan.md
├── src/credit_risk/
│   ├── ingest/             SEC fetch + raw cache
│   ├── normalise/          tag mapping, period selection, provenance
│   ├── metrics/            ratio calculations
│   ├── scoring/            bands, weights, grades, explanations
│   ├── trends/             trend classification + early warnings
│   ├── stress/             scenario engine
│   ├── store/              SQLite models and queries
│   └── cli.py
├── tests/
│   ├── fixtures/           hand-built statements with known answers
│   └── ...
└── data/
    ├── raw/                cached companyfacts JSON (gitignored)
    └── credit.db           SQLite (gitignored)
```

## How to work — every task

1. Read `PROJECT_STATE.md` and `TODO.md` first.
2. Read the relevant `docs/` file before touching anything methodological.
3. Propose the change in 5–10 plain-language lines before implementing.
4. Make the smallest change that completes the task.
5. Every calculation gets a unit test with a hand-computed expected value.
6. Run `pytest` before saying anything is done.
7. Update `PROJECT_STATE.md` and `TODO.md`. If a methodology or architecture choice was
   made, add it to `DECISIONS.md` (decision, reason, alternatives, consequences).
8. Don't refactor working code without a stated reason.
9. Don't add abstractions for problems we don't have yet.
10. Explain what you're doing in plain language — the owner is learning as this is built.

## Model protocol

Default to Sonnet for mechanical, low-judgment work: project setup, the SEC fetcher,
wiring, writing tests once the logic is agreed, small fixes.

Escalate to Opus for judgment-heavy work: Phase 3 (fact selection and normalisation —
Tasks 5–7), Task 8 (database schema design), Phase 6 (scoring logic). Also escalate any
time a task involves interpreting an edge case or rule from `docs/credit-methodology.md`
that isn't already spelled out step-by-step.

Escalate mid-task, regardless of phase, if: a test keeps failing after two fix attempts
on the current model, the proposed approach contradicts something stated in
`docs/credit-methodology.md` or `docs/data-sources.md`, or you're about to make a
financial-methodology judgment call that isn't already decided in `DECISIONS.md` — stop
and flag it for a decision rather than picking one.

Before starting a new phase, state which model you're using and why, in one line.

## Scope guard

If a proposed feature is not listed under **v1** in `docs/build-plan.md`, stop and ask
before building it.

## Docs to read before working on an area

| Area                          | Read                          |
|-------------------------------|-------------------------------|
| Fetching or mapping SEC data  | `docs/data-sources.md`        |
| Any ratio, score, trend, stress | `docs/credit-methodology.md` |
| Anything involving an LLM     | `docs/ai-governance.md`       |
| What to build next / not build | `docs/build-plan.md`         |
