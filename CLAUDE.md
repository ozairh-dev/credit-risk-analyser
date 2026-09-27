# Credit Risk Analyser — project rules

## Status

**v1 is complete (2026-09-20).** All eleven phases built, run on real data, committed.
892 tests pass, 44 skip by design. Anything beyond v1 is a v2 question — see
`docs/build-plan.md`, whose first two items are sector thresholds and the hand-verified
golden set. The three parked calibration items are **decisions with their measurements
recorded**, not gaps: see `PROJECT_STATE.md` "Next priorities".

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
10. **Validate before adopting.** Any company added to the universe or used as a fixture
    must have the full pipeline run over its entire filing history first, including the
    components-versus-aggregate audit of `total_debt`. Familiarity is not validation.
    *Why: Ford was adopted on familiarity and turned out to have no period where both
    `total_debt` and `ebitda` resolve, so no leverage metric can ever compute for it (D25).*
11. **Never approximate a refused value.** When a value is `UNAVAILABLE`, do not derive a
    substitute from adjacent periods, related tags, or subtraction from a different figure.
    A refusal is an answer.
    *Why: decided independently three times — `LEASES_NOT_SEPARABLE`,
    `COMPONENT_AGGREGATE_MISMATCH`, and mapping's `NO_CANDIDATE_TAG`.*
12. **Signals fire on divergence, not presence.** Before adding any warning, flag or
    marker, ask whether it would fire on ordinary reporting behaviour. A signal that fires
    constantly is indistinguishable from no signal.
    *Why: D15, D17, the same-day tiebreak and the unit fix all resolved this way; the unit
    rule was producing 3,845 non-events across three companies.*
13. **One invariant, one layer.** Enforce a rule in exactly one place. Encoding it twice
    doesn't double the safety — it creates states where the rule cannot be satisfied at
    all, and makes the layers disagree.
    *Why: D18(a) — the supersession CHECK and the partial unique index were mutually
    unsatisfiable. D21 — the form CHECK duplicated a selection rule and rejected valid
    audit records.*

## Stack (fixed for v1 — do not add to it)

Python 3.11+, pandas, pydantic, SQLite via stdlib sqlite3, requests, typer (CLI), pytest,
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
│   ├── architecture.md     how it fits together; where each decision lives
│   ├── risk-scoring.md     bands, weights, treatments, the graduated cap
│   ├── credit-methodology.md
│   ├── data-sources.md
│   ├── ai-governance.md
│   ├── build-plan.md
│   ├── interview-notes.md  per-component notes, including what went wrong
│   ├── case-study.md       the write-up, readable without the repo
│   └── audits/             point-in-time audits, corrections appended not rewritten
├── src/credit_risk/
│   ├── ingest/             SEC fetch + raw cache
│   ├── normalise/          tag mapping, period selection, provenance
│   ├── metrics/            composites, integrity checks, ratio calculations
│   ├── scoring/            bands, weights, grades, explanations
│   ├── trends/             trend classification + early warnings
│   ├── stress/             scenario engine
│   ├── export/             evidence pack + memo validator
│   ├── store/              SQLite models and queries
│   ├── pipeline.py         the stages in their one correct order
│   └── cli.py
├── tests/
│   ├── fixtures/           hand-built statements with known answers
│   ├── golden/             four company-years read from the FILINGS, not the XBRL —
│   │                       the only check against something other than the engine (D77)
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
11. Commit completed work before starting a new task. Don't leave changes uncommitted
    across task boundaries.
12. Before declaring a task done, check backwards: does this task's work contradict any
    decision in `DECISIONS.md`, or leave any doc asserting something the code no longer
    does? Name what you checked and what you found, even if the answer is nothing.
    Recording a new decision is not the same as checking it doesn't break an existing one.
13. Verify against real data, don't assert. Where a claim about behaviour can be checked
    against the cached companies, check it and report the measurement rather than stating
    the expectation.
    *Why: D27's cross-check-only restriction was proved by measuring that Ford resolves
    only the aggregate — 13 periods — and the pair in zero.*
14. Measure before pinning. When writing real-data assertions, examine the output first
    and confirm each value is correct before making it an expected value. Pinning
    unexamined output turns a test suite into a bug preservative — it defends whatever
    the code currently does, correct or not.
    *Why: D40's three false continuity warnings would have become the expected baseline
    had assertions been pinned before the phantom-period finding.*

## Model protocol

Default to Sonnet for mechanical, low-judgment work: project setup, the SEC fetcher,
wiring, writing tests once the logic is agreed, small fixes.

Escalate to Opus for judgment-heavy work: Task 8 (database schema design), Phase 6
(scoring logic). Also escalate any time a task involves interpreting an edge case or rule
from `docs/credit-methodology.md` that isn't already spelled out step-by-step.

Escalate to Fable for the highest-judgment work: Phase 3 (fact selection and
normalisation — Tasks 5–7), and any other task where an error would produce a
plausible-but-wrong result rather than a visible failure — the category the deterministic
engine can least afford to get subtly wrong.

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
| Finding your way around at all | `docs/architecture.md`       |
| Fetching or mapping SEC data  | `docs/data-sources.md`        |
| Any ratio, score, trend, stress | `docs/credit-methodology.md` |
| Bands, weights, caps, missing-data rules | `docs/risk-scoring.md` |
| Anything involving an LLM     | `docs/ai-governance.md`       |
| What to build next / not build | `docs/build-plan.md`         |
| Why a choice was made, and what it cost | `DECISIONS.md` — 82 entries, the project's best artefact |

**Do not restate `DECISIONS.md` in a doc.** The docs point into it; duplicating an entry
creates a second place for it to go stale, which is CLAUDE.md rule 13 applied to prose.
