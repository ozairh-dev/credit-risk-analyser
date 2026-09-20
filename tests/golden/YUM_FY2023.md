# Golden set — YUM FY2023

**Yum! Brands, Inc.** · fiscal period ended **2023-12-31**

## Independence statement

**Every figure in the "Filing" column below was read from the human-readable
financial statements and footnotes of the filing document itself** — the income
statement, balance sheet, cash-flow statement and notes, as a person reads them.
**No value here was taken from the SEC `companyfacts` API, the cached JSON payload,
or any output of this pipeline.** The engine column is looked up only to compute the
verdict; it never sources an expected value.

**Source filing:** 10-K `0001041061-24-000011`, filed 2024-02-20  
<https://www.sec.gov/Archives/edgar/data/1041061/000104106124000011/yum-20231231.htm>

*A second accession (0001041061-25-000013, the FY2024 10-K) also carries FY2023 comparatives; every figure below was read from the FY2023 filing.*

All figures below are in **dollars** (the filing presents millions; converted here).

## Filing metadata

| Field | Filing | Engine | Verdict |
|---|---|---|---|
| Accession | `0001041061-24-000011` | `0001041061-24-000011` | AGREES |
| Form | 10-K | 10-K | AGREES |
| Filed | 2024-02-20 | 2024-02-20 | AGREES |
| Period end | 2023-12-31 | 2023-12-31 | AGREES |

## Reported line items

| Concept | Filing | Engine | Verdict | Source |
|---|---|---|---|---|
| `revenue` | 7,076,000,000 | 7,076,000,000 | AGREES | Consolidated Statements of Income — *Total revenues* |
| `ebit` | 2,318,000,000 | 2,318,000,000 | AGREES | Consolidated Statements of Income — *Operating Profit* |
| `d_and_a` | 153,000,000 | 153,000,000 | AGREES | Consolidated Statements of Cash Flows — *Depreciation and amortization* |
| `interest_expense` | 602,000,000 | 602,000,000 | AGREES | Note 11, Short-term Borrowings and Long-term Debt — *"Interest expense on Short-term borrowings, Long-term debt and gross interest on cash pooling arrangements was $602 million"* |
| `cash` | 512,000,000 | 512,000,000 | AGREES | Consolidated Balance Sheets — *Cash and cash equivalents* |
| `short_term_debt` | 53,000,000 | 53,000,000 | AGREES | Consolidated Balance Sheets — *Short-term borrowings* |
| `ltd_incl_leases_current` | 56,000,000 | 56,000,000 | AGREES | Note 11 debt table — *Current maturities of long-term debt (before 3 of issuance costs)* |
| `ltd_incl_leases_noncurrent` | 11,142,000,000 | 11,142,000,000 | AGREES | Consolidated Balance Sheets — *Long-term debt* |
| `current_assets` | 1,609,000,000 | 1,609,000,000 | AGREES | Consolidated Balance Sheets — *Total Current Assets* |
| `current_liabilities` | 1,277,000,000 | 1,277,000,000 | AGREES | Consolidated Balance Sheets — *Total Current Liabilities* |
| `equity` | -7,858,000,000 | -7,858,000,000 | AGREES | Consolidated Balance Sheets — *Total Shareholders' Deficit* |
| `cfo` | 1,603,000,000 | 1,603,000,000 | AGREES | Consolidated Statements of Cash Flows — *Net Cash Provided by Operating Activities* |
| `capex` | 285,000,000 | 285,000,000 | AGREES | Consolidated Statements of Cash Flows — *Capital spending* |

## Composites the engine derives

| Composite | Filing-derived | Engine | Verdict | How the filing figure is built |
|---|---|---|---|---|
| `total_debt` | 11,195,000,000 | 11,251,000,000 | DIFFERS | 53 short-term borrowings + 11,142 long-term debt. The Note 11 table shows the 53 IS the 56 of current maturities net of 3 of issuance costs, so 56 must NOT be added again |
| `net_debt` | 10,683,000,000 | 10,739,000,000 | DIFFERS | 11,195 - 512 cash |
| `ebitda` | 2,471,000,000 | 2,471,000,000 | AGREES | 2,318 operating profit + 153 D&A |
| `fcf` | 1,318,000,000 | 1,318,000,000 | AGREES | 1,603 CFO - 285 capital spending |

## Disagreements, classified

### `total_debt` — KNOWN LIMITATION — not fixed

**The one engine defect the D78 fix does not reach.** The `debt_from_lease_inclusive_ltd` branch adds `short_term_debt` (53) to `ltd_incl_leases_current` (56); Note 11 shows the 53 IS the 56 net of 3 of issuance costs, so the same debt is counted twice and total debt is overstated by 56 (0.5%).

D78 refuses this pattern when the two agree within the component/aggregate tolerance, or when a lease-inclusive aggregate reconciles them. YUM FY2023 satisfies neither: the deviation is **5.36%**, 0.36pp outside the 5% tolerance, and YUM's only aggregate (`...IncludingCurrentMaturities` = 11,269) is the **gross** figure before issuance costs, so it sits closer to pair+std than to pair and would give the wrong answer.

**The tolerance was not widened to capture this case.** There is no measured basis for a different number — the deviation between the two tags runs continuously from 0% to 100% across 95 periods with no bimodal gap, so unlike D69 no threshold can be derived from the data. Tuning a constant until one known case passes is fitting to the test. YUM FY2022, FY2019, FY2020 and FY2025 are caught; FY2023 is not.

**What would actually settle it is footnote prose that XBRL does not carry** — which is a real limit on a deterministic XBRL engine, recorded rather than papered over.

### `net_debt` — CONSEQUENT

Follows `total_debt` above.

