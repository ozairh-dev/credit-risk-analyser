# AI governance

## v1: no runtime AI

The v1 application contains no LLM calls. It runs entirely without one. This is a hard
constraint (cost: £0; and the deterministic engine must stand on its own).

AI is used in two places only:

1. **During development** — Claude Code writes and explains code. That is not part of
   the product.
2. **A manual analysis workflow** — described below — where an analyst uses Claude (or
   any other model) outside the application, on evidence the application exported.

## The manual workflow

```
credit-risk export-evidence <ticker>
        ↓
evidence pack: evidence/<ticker>_<period>.md
        ↓
analyst pastes pack + prompts/credit_memo.md into Claude
        ↓
analyst pastes response into memos/<ticker>_<date>.md
        ↓
credit-risk validate-memo memos/<ticker>_<date>.md evidence/<ticker>_<period>.md
        ↓
memo marked REVIEWED only after a human signs it off
```

### Evidence pack contents

Everything the model is allowed to reason from, and nothing else:

- Company identifiers and the filing that **sourced this period's data** (not the
  company's newest filing — in a period-specific pack that is misleading), with the
  filing URL derived from `(cik, accession)` at export (D30b, D73d)
- The grade **with its cap line**, so a capped grade never reads as a judged one (D73b)
- The four engine config fingerprints, so a figure computed under different settings is
  not silently compared with one computed under these
- Every `REPORTED` concept used, with value, period, source tag and filing link
- Every `CALCULATED` metric, with formula name and inputs
- Trend classifications and early warnings, with evidence rows
- Stress table and driver attribution, **carrying the five stress output duties
  verbatim** — `fixed_cost_share`, `floating_share` and the unreachability of the debt
  split, the resolved `new_debt_rate` with its reason, the liquidity-immobility
  statement and the trend-carry statement (D73b). Stressed figures without the
  assumptions behind them let a model reason from numbers whose basis it cannot see
- Score breakdown and explain output
- Data-quality summary and integrity check results
- The assumption register, **built from config at export time** — the `assumptions`
  table exists but is deliberately unwired in v1 (D73a)
- A **"what this pack does not contain"** section naming market data, management
  commentary, peer comparison, forward estimates and agency ratings. Stating the
  boundary is what makes the "Data not available" rule enforceable

### Prompt template (`prompts/credit_memo.md`)

The prompt instructs the model to:

- use **only** numbers present in the evidence pack, quoted exactly as given;
- write each finding in the required format below;
- put "Data not available" wherever the pack has no evidence, rather than guessing;
- never state or imply a credit grade other than the one in the pack;
- never invent sources, quotations, management statements or industry figures.

### Required output format for every AI finding

```
Finding:
Evidence:            (numbers/rows copied from the evidence pack)
Source:              (the filing or calculation the evidence came from)
Interpretation:
Confidence:          High | Medium | Low
Requires human review: Yes
```

### Validator (`validate-memo`)

Deterministic checks on the pasted memo:

- Every number in the memo text must appear in the evidence pack, **matched at the
  precision the memo states** (D74). Stripping `£$%x,` and comparing digits — the
  original wording — flags "$20.8 billion" against a pack holding 20,825,000,000, so
  every memo becomes a wall of false positives and the validator gets ignored. Any
  figure that does not match is listed under **"Unverified figures"**.
- Bare numbers below 100 and four-digit years go to a separate **low-confidence** list
  rather than counting as verified: they coincide with something in a pack of dozens by
  chance, and counting them inflates the pass rate (D74).
- Any sentence claiming a grade other than the pack's is flagged. An explicit "Grade N"
  always counts; a band label counts only **inside a grading context** — taken
  literally, "any sentence containing a grade word" fires on "leverage is moderate" and
  "cash flow was strong", burying real violations under false positives. Label matching
  is **longest-first**: "Very strong" contains "strong" (D73c).
- The memo cannot be marked `REVIEWED` while unverified figures exist.
- Every section of the memo is stamped `AI_INTERPRETED` unless it is a verbatim copy of
  a pack table (then it keeps its original status).

### What the validator cannot check

Stated here and printed **above the results of every run** (D74), because a limitation
below the verdict is one a reader can skip, and a clean validation read as a clean memo
is worse than no validation:

- **A figure cited under the wrong label passes.** Quoting the pack's cash-flow figure as
  EBITDA is invisible — the validator reads numbers, not labels.
- **True figures assembled into a false claim pass.** It reads numbers, not arguments.
- **A fabricated source passes.** No numeric check sees it.

All three are characterised limitations pinned by test, not defects. **A human signs off
every memo.**

## What AI may and may not do (applies to v1 workflow and any future integration)

**May:** summarise filings, describe the business model, interpret trends already
computed, list plausible risks and mitigants, draft diligence questions, draft memo prose.

**May not:** produce or alter any financial number, override a calculation, state or
change a grade, modify an input, create a source, cite something not in the pack.

## Control flow that must hold in every version

```
AI output → validator → unverified items flagged → human review → presentation
```

Never:

```
AI output → grade
AI output → stored as REPORTED or CALCULATED
```

## v2 options (decision required before any of these)

- **Local model via Ollama**, fed the same evidence pack, output through the same
  validator. Free; quality on a laptop will be modest. Adds a learning surface.
- **Claude API.** Only if the £0 constraint is explicitly relaxed and recorded in
  `DECISIONS.md`. Same evidence pack, same validator, same controls. A Claude.ai
  subscription does **not** provide API access.
