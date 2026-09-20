# Golden set — MCK FY2023

**McKesson Corporation** · fiscal period ended **2023-03-31**

## Independence statement

**Every figure in the "Filing" column below was read from the human-readable
financial statements and footnotes of the filing document itself** — the income
statement, balance sheet, cash-flow statement and notes, as a person reads them.
**No value here was taken from the SEC `companyfacts` API, the cached JSON payload,
or any output of this pipeline.** The engine column is looked up only to compute the
verdict; it never sources an expected value.

**Source filing:** 10-K `0000927653-23-000038`, filed 2023-05-09  
<https://www.sec.gov/Archives/edgar/data/927653/000092765323000038/mck-20230331.htm>

*Fiscal year ends 31 March.*

All figures below are in **dollars** (the filing presents millions; converted here).

## Filing metadata

| Field | Filing | Engine | Verdict |
|---|---|---|---|
| Accession | `0000927653-23-000038` | `0000927653-23-000038` | AGREES |
| Form | 10-K | 10-K | AGREES |
| Filed | 2023-05-09 | 2023-05-09 | AGREES |
| Period end | 2023-03-31 | 2023-03-31 | AGREES |

## Reported line items

| Concept | Filing | Engine | Verdict | Source |
|---|---|---|---|---|
| `revenue` | 276,711,000,000 | 276,711,000,000 | AGREES | Consolidated Statements of Operations — *Revenues* |
| `ebit` | 4,381,000,000 | 4,381,000,000 | AGREES | Consolidated Statements of Operations — *Gross profit 12,358 less total operating expenses 7,977* |
| `d_and_a` | 608,000,000 | 272,000,000 | DIFFERS | Consolidated Statements of Cash Flows — *Depreciation 248 + Amortization 360* |
| `interest_expense` | 248,000,000 | 248,000,000 | AGREES | Consolidated Statements of Operations — *Interest expense* |
| `cash` | 4,678,000,000 | 4,678,000,000 | AGREES | Consolidated Balance Sheets — *Cash and cash equivalents* |
| `current_assets` | 44,292,000,000 | 44,292,000,000 | AGREES | Consolidated Balance Sheets — *Total current assets* |
| `current_liabilities` | 47,957,000,000 | 47,957,000,000 | AGREES | Consolidated Balance Sheets — *Total current liabilities* |
| `equity` | -1,857,000,000 | -1,857,000,000 | AGREES | Consolidated Balance Sheets — *Total McKesson Corporation stockholders' deficit* |
| `cfo` | 5,159,000,000 | 5,159,000,000 | AGREES | Consolidated Statements of Cash Flows — *Net cash provided by operating activities* |
| `capex` | 390,000,000 | 390,000,000 | AGREES | Consolidated Statements of Cash Flows — *Payments for property, plant, and equipment* |
| `inventory` | 19,691,000,000 | 19,691,000,000 | AGREES | Consolidated Balance Sheets — *Inventories, net* |
| `total_ltd_aggregate` | 5,594,000,000 | 5,594,000,000 | AGREES | Consolidated Balance Sheets — *Current portion of long-term debt 968 + Long-term debt 4,626* |
| `operating_lease_liab_current` | 299,000,000 | 299,000,000 | AGREES | Consolidated Balance Sheets — *Current portion of operating lease liabilities* |
| `operating_lease_liab_noncurrent` | 1,402,000,000 | 1,402,000,000 | AGREES | Consolidated Balance Sheets — *Long-term operating lease liabilities* |
| `finance_lease_liab_current` | 29,000,000 | 29,000,000 | AGREES | Note 11 Leases — *Finance leases - Current portion of long-term debt* |
| `finance_lease_liab_noncurrent` | 173,000,000 | 173,000,000 | AGREES | Note 11 Leases — *Finance leases - Long-term debt* |

## Composites the engine derives

| Composite | Filing-derived | Engine | Verdict | How the filing figure is built |
|---|---|---|---|---|
| `total_debt` | 7,295,000,000 | 7,497,000,000 | DIFFERS | 5,594 debt (which the lease note shows ALREADY contains the 202 of finance leases) + 1,701 operating lease liabilities |
| `net_debt` | 2,617,000,000 | 2,819,000,000 | DIFFERS | 7,295 - 4,678 cash |
| `ebitda` | 4,989,000,000 | 4,653,000,000 | DIFFERS | 4,381 operating income + 608 D&A |
| `fcf` | 4,769,000,000 | 4,769,000,000 | AGREES | 5,159 CFO - 390 capex |

## Disagreements, classified

### `d_and_a` — ENGINE DEFECT

**Tag rank order.** `tag_map.yaml` ranks `DepreciationDepletionAndAmortization` (272) above `DepreciationAndAmortization` (608). For McKesson the rank-0 tag is the NARROWER figure — depreciation 248 plus finance-lease ROU amortisation 24 — and excludes 360 of intangible amortisation. The rank-1 tag ties exactly to the cash-flow statement. Understates EBITDA by 336 (6.7%).

### `total_debt` — ENGINE DEFECT

**Double-count.** The `debt_from_aggregate` branch adds all four lease components to `total_ltd_aggregate` (5,594). The lease note shows finance lease liabilities are *presented within* "Current portion of long-term debt" (29) and "Long-term debt" (173) — so the 202 is already inside the 5,594. Overstates total debt by 202 (2.8%).

### `net_debt` — CONSEQUENT

Follows `total_debt` above.

### `ebitda` — CONSEQUENT

Follows `d_and_a` above.

