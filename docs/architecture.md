# Architecture

How the system is put together and where each kind of decision is made. This is a map, not
a rationale: every "why" below is one line and a pointer into `DECISIONS.md`, which holds
76 entries with their evidence, alternatives and consequences. **Read this to find your way
around; read the decision entries for the argument.**

Numbers quoted here carry their basis — population, grade type, period count, commit —
because the project has already been caught once by a count that was true at a different
commit than the one it was printed under (see `docs/audits/2026-09-14-v1-final-audit.md`,
the `†` correction note).

## The shape of it

```
SEC companyfacts JSON  (cached, gitignored)
        │
        ▼
  ┌───────────────────────────────────────────────┐
  │  pipeline.analyse()  — pure, no I/O           │
  │                                               │
  │  select → map → compose → integrity → ratios  │
  │                    → trends/warnings          │
  │                    → score → stress           │
  └───────────────────────────────────────────────┘
        │                                  │
        ▼                                  ▼
  SQLite (append-with-history)       evidence pack (Markdown)
                                           │
                                           ▼
                              manual AI memo → validate-memo
```

`pipeline.analyse(raw)` runs every stage and returns an 8-tuple. It touches no disk and no
network, which is why the CLI and the real-data tests can drive the identical sequence
instead of each re-deriving it. Storage is a separate call.

## The nine stages

| # | Stage | Module | Produces | Governed by |
|---|---|---|---|---|
| 1 | **select** | `normalise/select.py` | one fact per concept-period | D13–D16, D21, D29, D31 |
| 2 | **map** | `normalise/map_concepts.py` | 34 internal concepts from 46 XBRL tags | D11, D17, D27, D69 |
| 3 | **compose** | `metrics/composites.py` | `total_debt`, `net_debt`, `ebitda`, `fcf` | D6, D26, D32–D34 |
| 4 | **integrity** | `metrics/integrity.py` | 8 checks per period, 6 fail-severity | D37–D39, D69, D76 |
| 5 | **ratios** | `metrics/ratios.py` | 17 metrics | D41–D43 |
| 6 | **trends / warnings** | `trends/engine.py` | verdicts + 11 indicators (7 trend, 4 level) | D36, D40, D49–D52 |
| 7 | **score** | `scoring/engine.py` | components → categories → grade | D45–D48, D50 |
| 8 | **stress** | `stress/engine.py` | 3 scenarios + driver attribution | D53–D58, D70, D75 |
| 9 | **export** | `export/evidence.py` | the evidence pack | D73, and `export/validator.py` for D74 |

### The order is not arbitrary

Four of the eight in-process stages are pinned by a real dependency, and getting any of
them backwards produces plausible wrong answers rather than errors:

- **compose before integrity** — the subset checks compare `total_debt` against
  liabilities, so the composites must exist first. This is why task order interleaves
  Phases 4 and 5 in `build-plan.md`.
- **integrity before ratios** — a period that fails a fail-severity check computes no
  metric at all (D76). The failure must be known before the metrics are attempted, not
  after.
- **trends before score** — the `ebitda_margin_trend` component is scored from a trend
  verdict, not a metric value (D50).
- **score before stress** — a stress run reports base versus stressed, so it needs the base
  score to exist.

## The three-kind reason model

Every refusal carries a reason code, and every reason code has exactly one **kind**. The
kind — not the code — decides what scoring does with it. This is the single idea that most
of the engine's behaviour hangs off (D9, D41a; the mapping lives in `metrics/ratios.py`).

| Kind | Means | Scoring does | Example codes |
|---|---|---|---|
| **EVIDENCE** | we know, and the answer is bad | scores **0** — worst band | `NEGATIVE_EBITDA`, `NEGATIVE_EARNINGS` |
| **GAP** | we do not know | **drops** the component and **caps** the grade | `MISSING_INPUT`, `INTEGRITY_FAILED`, `NON_POSITIVE_CAPITAL` |
| **NEITHER** | a good thing, not a shortfall | **redistributes** the weight, no cap | `NO_DEBT`, `NO_INTEREST_NO_DEBT` |

The distinction is load-bearing in both directions. Scoring a gap as zero would punish a
company for a tagging deficiency in its filing. Scoring negative EBITDA as a gap would let
a distressed company escape the worst band by failing to have earnings. An unlevered
company is neither: it has no coverage ratio because it has no debt, which is not a
shortfall and must not cap its grade.

The full vocabulary with one line per code is in `data-sources.md`; the arguments are in
D41 and D42.

## Five component treatments

Where reason kinds describe *why* a value is absent, treatments describe *what the scorer
did about it*. Every component row carries one, so an explain output can always be read
back (D45):

`scored` · `evidence_zero` · `dropped_data_gap` · `dropped_unlevered` ·
`not_yet_implemented`

The last is empty today and deliberately kept: it is the mechanism that lets a future
component join the row shape before it can be scored. Before Phase 7 it carried
`ebitda_margin_trend` — treating an unbuilt feature as a data gap would have capped every
company in every period.

## The four fingerprint scopes

A computed value is not config-independent. `total_debt` moves with
`include_operating_leases`; a grade moves with a band edge. Every stored row therefore
records a fingerprint of the config that fed it, so a number that changed for a settings
reason can be told apart from one that changed for a filing reason.

There are **four** fingerprints, and they are **disjoint** — no config key appears in two.
`tests/test_project_setup.py::test_the_four_fingerprint_scopes_are_disjoint` enforces it.

| Scope | Module | Covers | Blast radius |
|---|---|---|---|
| composites | `store/fingerprint.py` | `include_operating_leases`, `include_st_investments`, `component_aggregate_tolerance` | **values** — concepts and metrics |
| scores | `scoring/fingerprint.py` | `bands`, `weights`, `grades`, `max_grade_by_categories_scored`, `trend_points` | **scores** |
| trends | `trends/fingerprint.py` | `trend_materiality`, `warning_escalation_count` | **which warnings fire** |
| stress policy | `stress/fingerprint.py` | `presets`, `default_tax_rate`, `new_debt_rate_default`, `new_debt_rate_band`, `sensitivity_grid` | **stress runs** |

### Why disjoint, and why the split is by blast radius rather than by file

**The boundary is "what does this key move", not "which file does it live in."** Two keys
in `thresholds.yaml` land in different scopes: `trend_points` moves scores, so it belongs
to the score fingerprint, while `trend_materiality` moves which warnings fire and belongs
to the trend one. `default_tax_rate` lives in `stress.yaml` and belongs to the stress scope.
File location is incidental (D18, D38, D45, D52, D56).

Merging any two would break in both directions at once: a score would be fingerprinted
against config that **cannot affect it**, while the config that **can** would be invisible.
A warning that stopped firing because a threshold moved would be indistinguishable from one
that stopped because the company improved.

One thing is deliberately **not** fingerprinted: the per-run stress assumptions
(`ebitda_mode`, `fixed_cost_share`, `floating_share`, the resolved `new_debt_rate`). They
are columns on the run row instead. A value that varies per run is not a config version —
fingerprinting one would make two runs with different assumptions hash identically whenever
the file had not changed (D56).

## Storage

18 SQLite tables, stdlib `sqlite3`, no ORM. The two structural ideas:

- **Append-with-history.** Reported values are never overwritten (CLAUDE.md rule 5). A
  restatement or override is appended alongside the original with a supersession record,
  and a partial unique index on `status='CURRENT'` enforces that exactly one row per
  `(cik, concept, period_end)` is live. D18(a) records what happened when the same
  invariant was also encoded as a CHECK constraint: the two became mutually unsatisfiable.
  One invariant, one layer — CLAUDE.md rule 13.
- **Provenance is a chain, not a column.** A metric resolves backwards through
  `metric_inputs → concepts → concept_inputs → facts` to the filing and the XBRL tag it
  came from. No stored URLs: `store/provenance.py::filing_url(cik, accession)` derives them
  at export, because a stored copy can only drift (D30b).

## Where authority lives

The most useful thing to know about this codebase is which artefact decides what. Nothing
is decided in two places.

| Kind of decision | Lives in | Not in |
|---|---|---|
| Thresholds, weights, band edges, stress defaults | `config/*.yaml` (CLAUDE.md rule 6) | code — a missing key raises rather than defaulting (D28) |
| Which XBRL tags map to which concept, in rank order | `config/tag_map.yaml` | code |
| Formulas, edge-case semantics, what a metric means | `docs/credit-methodology.md` | code comments |
| Which fact wins for a concept-period | `normalise/select.py`, per `docs/data-sources.md` | anywhere downstream |
| What a reason code *means* for scoring | the `_KINDS` mapping in `metrics/ratios.py` | the scorer — it reads the kind, never the code |
| Whether a rule was right, and what was measured | `DECISIONS.md` | any of the above |
| Where AI may and may not act | `docs/ai-governance.md` | the engine — there is no LLM in it |

**`DECISIONS.md` is the authority on rationale and the others are the authority on
behaviour.** When they disagree, the code is what runs and the decision entry is what
should have been implemented — that gap is a bug, and CLAUDE.md rule 12 exists to catch it
before a task is called done.

## Finding your way in

- **"Why does this company refuse to produce a leverage ratio?"** → run
  `credit-risk metrics <ticker> --all-periods`; the reason code is printed per metric, and
  `data-sources.md` has a line per code.
- **"Why is this grade capped?"** → `credit-risk score <ticker>`; the cap line leads every
  period and names the missing categories and their causes (D57).
- **"Why did this number change?"** → compare the fingerprint on the stored row. Different
  fingerprint means a config change; same fingerprint means a filing change.
- **"Was this rule considered, and what was measured?"** → `DECISIONS.md`. It is searchable
  by reason code, by concept name and by ticker.
