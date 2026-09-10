# Expected selections for companyfacts_minimal.json

Hand-built fixture (Task 5). Every correct answer below was decided by a human reading
docs/data-sources.md — **before** any selection code existed. Task 6's tests must assert
these results; if code and this document disagree, the code is wrong until the owner
says otherwise.

Values are deliberately small round numbers so every check is mental arithmetic.
The JSON shape (facts.<taxonomy>.<Tag>.units.<unit>[] with per-fact keys start/end/val/
accn/fy/fp/form/filed/frame) is faithful to real SEC companyfacts responses; instant
facts have no `start` key, which is how they are distinguished from duration facts.

## The company

Fixture Manufacturing Co, CIK 999999, calendar fiscal year (FYE 31 Dec). Three filings:

| Filing | Accession | Filed |
|---|---|---|
| FY2022 10-K | 0000999999-23-000001 | 2023-02-15 |
| Q2-2023 10-Q | 0000999999-23-000042 | 2023-08-01 |
| FY2023 10-K | 0000999999-24-000001 | 2024-02-15 |

**Deliberate trap:** facts reported in the FY2023 10-K carry `fy: 2023` even when their
*period* is 2022 (N2, R2 below) — SEC stamps `fy` with the filing's fiscal year, not the
fact's period. Selection must key periods on `start`/`end`, never on `fy`.

## Fact inventory

| ID | Tag | Period | Val | Filing | Days | Why it's here |
|---|---|---|---|---|---|---|
| R1 | Revenues | 2022-01-01 → 2022-12-31 | 1000 | -23-000001 | 364 | baseline FY2022 |
| R2 | Revenues | 2022-01-01 → 2022-12-31 | 1000 | -24-000001 | 364 | comparative duplicate of R1 (same value, later filing) |
| R3 | Revenues | 2023-01-01 → 2023-12-31 | 1200 | -24-000001 | 364 | baseline FY2023 |
| R4 | Revenues | 2023-04-01 → 2023-12-31 | 800 | -24-000001 | 274 | duration outside 350–380 window, but stamped fp=FY/form=10-K |
| R5 | Revenues | 2023-04-01 → 2023-06-30 | 260 | -23-000042 | 90 | quarterly fact (fp=Q2, form=10-Q) |
| N1 | NetIncomeLoss | 2022-01-01 → 2022-12-31 | 100 | -23-000001 | 364 | original FY2022 value |
| N2 | NetIncomeLoss | 2022-01-01 → 2022-12-31 | 90 | -24-000001 | 364 | restatement of N1 in a later filing |
| N3 | NetIncomeLoss | 2023-01-01 → 2023-12-31 | 110 | -24-000001 | 364 | baseline FY2023 |
| C1 | CostOfGoodsAndServicesSold | 2023-01-01 → 2023-12-31 | 600 | -24-000001 | 364 | fallback tag; primary `CostOfRevenue` is absent from the file |
| K1 | Cash... (instant) | end 2022-12-31 | 50 | -23-000001 | — | baseline FY2022 balance |
| K2 | Cash... (instant) | end 2023-12-31 | 70 | -24-000001 | — | baseline FY2023 balance |
| K3 | Cash... (instant) | end 2023-06-30 | 55 | -24-000001 | — | instant fact whose end ≠ fiscal year end |
| — | dei/EntityCommonStockSharesOutstanding | end 2024-01-31 | 50000000 | -24-000001 | — | structural fidelity: real responses always include dei + non-USD units; v1 selection must ignore it |

## Expected results after selection (Task 6) and mapping (Task 7)

### Selected (current) rows

| Concept | Period end | Value | From accession | Notes |
|---|---|---|---|---|
| revenue | 2022-12-31 | 1000 | 0000999999-24-000001 | R2 wins over R1 per rule 4 (most recently filed); values equal, provenance shifts — see flag C |
| revenue | 2023-12-31 | 1200 | 0000999999-24-000001 | R3 |
| net_income | 2022-12-31 | **90** | 0000999999-24-000001 | N2, the restated value |
| net_income | 2023-12-31 | 110 | 0000999999-24-000001 | N3 |
| cost_of_revenue | 2023-12-31 | 600 | 0000999999-24-000001 | C1; `source_tag = CostOfGoodsAndServicesSold` (2nd candidate — first-present-wins) |
| cash | 2022-12-31 | 50 | 0000999999-23-000001 | K1 |
| cash | 2023-12-31 | 70 | 0000999999-24-000001 | K2 |

### Superseded — kept, never deleted (rule 4)

| Fact | Value | Marked |
|---|---|---|
| N1 (net income FY2022 original) | 100 | superseded_by = 0000999999-24-000001 |
| R1 (revenue FY2022 original copy) | 1000 | superseded_by = 0000999999-24-000001 |

`superseded_by` is an **output annotation produced by our selection**, not a field in
SEC's JSON — the fixture must never contain that string (a test enforces this).

### Excluded

| Fact | Excluded by | Detail |
|---|---|---|
| R5 | Rule 1 | fp=Q2 and form=10-Q (fails both halves; would also fail rule 2 at 90 days) |
| R4 | Rule 2 | 274 days outside 350–380 — despite passing rule 1 (fp=FY, form=10-K) |
| K3 | Rule 3 | instant end 2023-06-30 ≠ fiscal year end 2023-12-31 |
| dei fact | out of scope | non-us-gaap taxonomy, `shares` unit (rule 5: shares/pure ignored) |

## Interpretation flags — owner to settle before/during Task 6

Flagged, not decided; nothing added to DECISIONS.md yet.

- **A. Source of "fiscal year end" for rule 3.** Real companyfacts JSON has no
  per-company FYE field. Here it is Dec 31 by construction, but Task 6 must derive it
  (plausibly from accepted duration facts' `end` dates). Docs don't specify how.
- **B. Rule ordering.** Answers are determinate only if rules 1–3 filter first and
  rule 4 dedups survivors. Proof in this fixture: R4 and R3 share (Revenues,
  end 2023-12-31) *within the same filing* — dedup-before-filter would be an
  unresolvable tie. Confirm, then record in DECISIONS.md.
- **C. Equal-value duplicates.** Rule 4 read literally makes the later (comparative)
  filing the current provenance for FY2022 revenue even though the value is unchanged.
  If original-filing provenance is preferred when values are equal, amend the rule now.
- **Minor.** 350–380 treated as inclusive; boundary values not tested here.

## Deliberately not covered (candidates for later fixture additions)

- Rule 5 foreign-unit handling (fixture is all-USD).
- Restatement via 10-K/A (this fixture restates via the next year's 10-K — the more
  common real-world route; the 10-K/A form-acceptance branch of rule 1 is untested).
- Balance-sheet comparative duplicates (duplicate case is modelled on Revenues only).
