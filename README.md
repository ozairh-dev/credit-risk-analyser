# Credit Risk Analyser

Portfolio-scale credit analysis for US-listed non-financial companies, built on free
SEC XBRL data. Deterministic metrics, explainable scoring, early warnings and stress
testing, with full data provenance. No LLM in the calculation path.

Not a bank rating model, not a regulatory capital model, not investment or credit advice.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env               # then put your real name and email in it
```

The SEC requires a User-Agent header identifying you on every request. Requests without
one are blocked. That is what `.env` is for.

## Check it works

```bash
pytest              # 6 passed
credit-risk version
```

## Where things are

| Path | What it is |
|---|---|
| `CLAUDE.md` | Project rules — Claude Code reads this every session |
| `docs/credit-methodology.md` | Every formula, threshold and edge case |
| `docs/data-sources.md` | Where the data comes from and how it is selected |
| `docs/ai-governance.md` | Where AI is and is not allowed |
| `docs/build-plan.md` | Scope, phases, first ten tasks |
| `config/*.yaml` | Thresholds, weights, stress presets, XBRL tag map |
| `PROJECT_STATE.md` / `TODO.md` | Where the build has got to, and what is next |

## Status

Phase 1 complete — project skeleton, configuration and setup tests.
Next: Phase 2, SEC ingestion. See `TODO.md`.
