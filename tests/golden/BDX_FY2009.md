# Golden set — BDX FY2009

**Becton, Dickinson and Company** · fiscal period ended **2009-09-30**

## Independence statement

**Every figure in the "Filing" column below was read from the human-readable
financial statements and footnotes of the filing document itself** — the income
statement, balance sheet, cash-flow statement and notes, as a person reads them.
**No value here was taken from the SEC `companyfacts` API, the cached JSON payload,
or any output of this pipeline.** The engine column is looked up only to compute the
verdict; it never sources an expected value.

**Source filing:** 10-K `0000950123-09-066233`, filed 2009-11-25  
<https://www.sec.gov/Archives/edgar/data/10795/000095012309066233/y79446e10vk.htm>

*Figures are as FIRST REPORTED in the FY2009 10-K. BDX restated FY2009 comparatives in its FY2010 10-K (0000950123-10-108757) after a divestment; the engine correctly prefers the restated values (D14/D15).*

All figures below are in **dollars** (the filing presents thousands; converted here).

## Filing metadata

| Field | Filing | Engine | Verdict |
|---|---|---|---|
| Accession | `0000950123-09-066233` | `0000950123-09-066233` | AGREES |
| Form | 10-K | 10-K | AGREES |
| Filed | 2009-11-25 | 2009-11-25 | AGREES |
| Period end | 2009-09-30 | 2009-09-30 | AGREES |

## Reported line items

| Concept | Filing | Engine | Verdict | Source |
|---|---|---|---|---|
| `revenue` | 7,160,874,000 | 6,986,722,000 | DIFFERS | Consolidated Statements of Income — *Revenues* |
| `ebit` | 1,650,353,000 | 1,589,682,000 | DIFFERS | Consolidated Statements of Income — *Operating Income* |
| `d_and_a` | 470,193,000 | 464,604,000 | DIFFERS | Consolidated Statements of Cash Flows — *Depreciation and amortization* |
| `interest_expense` | 40,389,000 | 40,389,000 | AGREES | Consolidated Statements of Income — *Interest expense* |
| `cash` | 1,394,244,000 | 1,394,244,000 | AGREES | Consolidated Balance Sheets — *Cash and equivalents* |
| `short_term_investments` | 551,561,000 | — | DIFFERS | Consolidated Balance Sheets — *Short-term investments* |
| `short_term_debt` | 402,965,000 | 402,965,000 | AGREES | Consolidated Balance Sheets — *Short-term debt* |
| `noncurrent_ltd` | 1,488,460,000 | 1,488,460,000 | AGREES | Consolidated Balance Sheets — *Long-Term Debt* |
| `current_assets` | 4,646,954,000 | 4,646,954,000 | AGREES | Consolidated Balance Sheets — *Total Current Assets* |
| `current_liabilities` | 1,777,093,000 | 1,777,093,000 | AGREES | Consolidated Balance Sheets — *Total Current Liabilities* |
| `equity` | 5,142,712,000 | 5,142,712,000 | AGREES | Consolidated Balance Sheets — *Total Shareholders' Equity* |
| `cfo` | 1,691,520,000 | — | DIFFERS | Consolidated Statements of Cash Flows — *Net Cash Provided by Continuing Operating Activities* |
| `capex` | 591,103,000 | 585,196,000 | DIFFERS | Consolidated Statements of Cash Flows — *Capital expenditures* |
| `inventory` | 1,156,762,000 | 1,156,762,000 | AGREES | Consolidated Balance Sheets — *Inventories* |

## Composites the engine derives

| Composite | Filing-derived | Engine | Verdict | How the filing figure is built |
|---|---|---|---|---|
| `total_debt` | 1,891,425,000 | ST_DEBT_SCOPE_UNCERTAIN | DIFFERS | 402,965 short-term debt + 1,488,460 long-term debt. Note 'Debt' shows the 402,965 ALREADY INCLUDES 200,085 of current portion of long-term debt |
| `net_debt` | -54,380,000 | MISSING_INPUT:total_debt | DIFFERS | 1,891,425 - 1,394,244 cash - 551,561 short-term investments: BDX was net cash |
| `ebitda` | 2,120,546,000 | 2,054,286,000 | DIFFERS | 1,650,353 operating income + 470,193 D&A |
| `fcf` | 1,100,417,000 | MISSING_INPUT:cfo | DIFFERS | 1,691,520 CFO - 591,103 capital expenditures |

## Disagreements, classified

### `revenue` — LEGITIMATE — restatement

The FY2009 10-K reports 7,160,874. BDX restated FY2009 in its FY2010 10-K after a divestment; the restated figure is 6,986,722. **The engine is correct** to prefer the most recent value (D14/D15 supersession).

### `ebit` — LEGITIMATE — restatement

As first reported 1,650,353; restated to 1,589,682 in the FY2010 10-K. 60,671 was reclassified to discontinued operations. **Engine correct.**

### `d_and_a` — LEGITIMATE — restatement

As first reported 470,193; restated to 464,604. **Engine correct.**

### `capex` — LEGITIMATE — restatement

As first reported 591,103; restated to 585,196. **Engine correct.**

### `ebitda` — CONSEQUENT

Follows the restated `ebit` and `d_and_a`. **Engine correct.**

### `short_term_investments` — ENGINE DEFECT

**Tag-map gap.** BDX tags short-term investments as `OtherShortTermInvestments` (551,561), which `tag_map.yaml` does not carry — it lists only `ShortTermInvestments` and `MarketableSecuritiesCurrent`. The figure is plainly on the balance sheet.

### `cfo` — ENGINE DEFECT

**Tag-map gap.** BDX tags operating cash flow as `NetCashProvidedByUsedInOperatingActivitiesContinuingOperations` (1,691,520), which the map does not carry — it lists only `NetCashProvidedByUsedInOperatingActivities`. The figure is plainly on the cash-flow statement.

### `fcf` — CONSEQUENT

Follows the `cfo` gap above.

### `total_debt` — ENGINE CORRECT — refusal vindicated

**This is the most valuable single result in the golden set.** The engine refuses with `ST_DEBT_SCOPE_UNCERTAIN` because `short_term_debt` resolved via the `DebtCurrent` tag (402,965) may already contain `current_ltd` (200,085), and XBRL cannot settle it. The Note 'Debt' table settles it for a human reader: *Loans Payable Domestic 200,000 + Foreign 2,880 + Current portion of long-term debt 200,085 = 402,965*. **It does contain it.** Had the engine added both it would have double-counted 200,085 — a 13% overstatement of BDX's total debt. D32's refusal prevented exactly that.

### `net_debt` — CONSEQUENT

Follows the `total_debt` refusal. The filing-derived figure shows BDX was **net cash** in FY2009.

