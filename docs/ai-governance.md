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

- Company identifiers and latest filing details
- Every `REPORTED` concept used, with value, period, source tag and filing link
- Every `CALCULATED` metric, with formula name and inputs
- Trend classifications and early warnings, with evidence rows
- Stress table and driver attribution
- Score breakdown and explain output
- Data-quality summary and integrity check results
- The assumption register

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

- Every number in the memo text (after normalising £/$/%/x/commas) must appear in the
  evidence pack. Any that don't are listed under **"Unverified figures"**.
- Any sentence containing a grade word ("Grade", "strong", "high risk", etc.) is checked
  against the pack's grade; mismatches are flagged.
- The memo cannot be marked `REVIEWED` while unverified figures exist.
- Every section of the memo is stamped `AI_INTERPRETED` unless it is a verbatim copy of
  a pack table (then it keeps its original status).

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
