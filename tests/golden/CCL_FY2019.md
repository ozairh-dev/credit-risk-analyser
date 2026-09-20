# Golden set — CCL FY2019

**Carnival Corporation & plc** · fiscal period ended **2019-11-30**

## Independence statement

**Every figure in the "Filing" column below was read from the human-readable
financial statements and footnotes of the filing document itself** — the income
statement, balance sheet, cash-flow statement and notes, as a person reads them.
**No value here was taken from the SEC `companyfacts` API, the cached JSON payload,
or any output of this pipeline.** The engine column is looked up only to compute the
verdict; it never sources an expected value.

**Source filing:** 10-K `0000815097-20-000003`, filed 2020-01-28  
<https://www.sec.gov/Archives/edgar/data/815097/000081509720000003/a2019ex-13.htm>

*Financial statements are in EX-13 to the 10-K, not the main document.*

All figures below are in **dollars** (the filing presents millions; converted here).

## Filing metadata

| Field | Filing | Engine | Verdict |
|---|---|---|---|
| Accession | `0000815097-20-000003` | `0000815097-20-000003` | AGREES |
| Form | 10-K | 10-K | AGREES |
| Filed | 2020-01-28 | 2020-01-28 | AGREES |
| Period end | 2019-11-30 | 2019-11-30 | AGREES |

## Reported line items

| Concept | Filing | Engine | Verdict | Source |
|---|---|---|---|---|
| `revenue` | 20,825,000,000 | 20,825,000,000 | AGREES | Consolidated Statements of Income — *Revenues total (14,104 passenger + 6,331 onboard + 390 tour)* |
| `ebit` | 3,276,000,000 | 3,276,000,000 | AGREES | Consolidated Statements of Income — *Operating Income* |
| `d_and_a` | 2,160,000,000 | 2,160,000,000 | AGREES | Consolidated Statements of Cash Flows — *Depreciation and amortization* |
| `interest_expense` | 206,000,000 | 206,000,000 | AGREES | Consolidated Statements of Income — *Interest expense, net of capitalized interest* |
| `cash` | 518,000,000 | 518,000,000 | AGREES | Consolidated Balance Sheets — *Cash and cash equivalents* |
| `short_term_debt` | 231,000,000 | 231,000,000 | AGREES | Consolidated Balance Sheets — *Short-term borrowings* |
| `current_ltd` | 1,596,000,000 | 1,596,000,000 | AGREES | Consolidated Balance Sheets — *Current portion of long-term debt* |
| `noncurrent_ltd` | 9,675,000,000 | 9,675,000,000 | AGREES | Consolidated Balance Sheets — *Long-Term Debt* |
| `current_assets` | 2,059,000,000 | 2,059,000,000 | AGREES | Consolidated Balance Sheets — *Total current assets* |
| `current_liabilities` | 9,127,000,000 | 9,127,000,000 | AGREES | Consolidated Balance Sheets — *Total current liabilities* |
| `equity` | 25,365,000,000 | 25,365,000,000 | AGREES | Consolidated Balance Sheets — *Total shareholders' equity* |
| `cfo` | 5,475,000,000 | 5,475,000,000 | AGREES | Consolidated Statements of Cash Flows — *Net cash provided by operating activities* |
| `capex` | 5,429,000,000 | 5,429,000,000 | AGREES | Consolidated Statements of Cash Flows — *Purchases of property and equipment* |
| `inventory` | 427,000,000 | 427,000,000 | AGREES | Consolidated Balance Sheets — *Inventories* |

## Composites the engine derives

| Composite | Filing-derived | Engine | Verdict | How the filing figure is built |
|---|---|---|---|---|
| `total_debt` | 11,502,000,000 | 11,502,000,000 | AGREES | 231 + 1,596 + 9,675 — the three debt lines on the balance sheet |
| `net_debt` | 10,984,000,000 | 10,984,000,000 | AGREES | 11,502 - 518 cash; no short-term investments line is presented |
| `ebitda` | 5,436,000,000 | 5,436,000,000 | AGREES | 3,276 operating income + 2,160 D&A |
| `fcf` | 46,000,000 | 46,000,000 | AGREES | 5,475 CFO - 5,429 capex |

## Disagreements, classified

**None.** Every reported line item, every composite and every item of filing
metadata matches the engine exactly.
