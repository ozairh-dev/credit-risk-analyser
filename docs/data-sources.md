# Data sources

## v1 source: SEC XBRL companyfacts (only)

**Endpoints**

- Ticker → CIK map: `https://www.sec.gov/files/company_tickers.json`
- All facts for a company: `https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json`
  (CIK zero-padded to 10 digits)

**Access rules**

- Every request must send a `User-Agent` header of the form `"Project name contact@email"`.
  The SEC blocks requests without one.
- Stay under 10 requests/second. Add a small sleep between calls.
- Cache the raw JSON to `data/raw/CIK{cik:010d}.json` with a `fetched_at` timestamp. Do not
  re-fetch within 24 hours unless `--force` is passed. The window is **exclusive** — at
  exactly the configured age the cache is stale and is re-fetched (D31) — and the value
  itself lives in `config/ingestion.yaml`, never in code. Raw files are never edited.

**Licensing:** SEC data is US public domain. No restrictions on this use.

## Fact selection rules

companyfacts returns every fact ever filed, across many filings and periods. Selection
has to be explicit or you get duplicates and wrong periods.

1. **Annual data only in v1.** Keep facts where `fp == "FY"` and `form` is `10-K` or
   `10-K/A`. Quarterly alignment is a v2 problem.
2. **Duration facts** (income statement, cash flow): keep only where `end − start` is
   between 350 and 380 days. This drops cumulative and partial-year values.
3. **Instant facts** (balance sheet): keep where `end` equals the fiscal year end.
   The fiscal year end is **derived** — companyfacts has no per-company FYE field: it is
   the `end` date of the duration facts accepted by rules 1–2 for that fiscal year. If
   accepted duration facts disagree on `end`, use the most common date and flag the
   period. If a year has no accepted duration facts, its instant facts are
   `UNAVAILABLE`, reason `NO_FYE_ANCHOR` — never accepted unvalidated. (DECISIONS D13)
4. **Restatements:** for the same `(concept, period type, period end)` there will often be
   several values from different filings. **Period type is part of the identity** — a
   duration fact (a flow) and an instant fact (a stock) sharing an end date are different
   facts and never supersede each other (DECISIONS D29).
   When the values **differ**, the most recently filed is
   current; earlier values are kept and marked `superseded_by = <accession>`. Never
   delete. When a later filing repeats an **identical** value (routine comparative
   reporting), the earliest filing remains the source and no supersession is recorded —
   supersession marks changed values only. (DECISIONS D15)
   Rules apply in order: 1–3 filter, then this rule dedups the survivors. (DECISIONS D14)
5. **Units:** USD for monetary items. A unit is classified into exactly one of three
   kinds (DECISIONS D24):
   - **Monetary, USD** → the fact is selected normally.
   - **Monetary, non-USD** — a genuine ISO-4217 currency code other than USD (`EUR`,
     `GBP`, `JPY`) → `UNAVAILABLE`, reason `FOREIGN_UNIT`. Never converted.
   - **Not a monetary item** → ignored entirely: no fact, no marker, no event. This
     covers `shares` and `pure`, compound per-unit denominations of the form
     `USD/<something>` (`USD/shares`, `USD/Warrant` — these are rates per unit, not
     amounts), and count units naming a thing being counted (`segment`, `patent`,
     `lawsuit`, `Employee`, `reporting_unit`, …).

   `FOREIGN_UNIT` is reserved for the second kind only. A per-share amount is not
   foreign currency, and neither is a count of patents.
6. Store on every fact: `fy`, `fp`, `form`, `filed`, `accn`, `frame`, `start`, `end`.

## Normalisation

Companies do not use the same tags. The mapping lives in `config/tag_map.yaml`: each
internal concept has an **ordered list of candidate tags**; the first one present for the
period wins. Always record `source_tag` (which tag was used) and keep the original label.
The mapping table is configuration and must be validated per company — expect to extend it.

Starting candidate lists (us-gaap taxonomy; validate, don't trust):

| Internal concept        | Candidate tags, in priority order |
|-------------------------|-----------------------------------|
| revenue                 | `Revenues`, `RevenueFromContractWithCustomerExcludingAssessedTax`, `SalesRevenueNet` |
| cost_of_revenue         | `CostOfRevenue`, `CostOfGoodsAndServicesSold` |
| gross_profit            | `GrossProfit` (else revenue − cost_of_revenue, CALCULATED) |
| ebit                    | `OperatingIncomeLoss` |
| d_and_a                 | `DepreciationDepletionAndAmortization`, `DepreciationAndAmortization`, `DepreciationAmortizationAndAccretionNet` — these usually come from the **cash-flow statement**, not the income statement |
| interest_expense        | `InterestExpense`, `InterestExpenseNonoperating`, `InterestExpenseDebt` |
| pretax_income           | `IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest` |
| tax_expense             | `IncomeTaxExpenseBenefit` |
| net_income              | `NetIncomeLoss` |
| cash                    | `CashAndCashEquivalentsAtCarryingValue` |
| short_term_investments  | `ShortTermInvestments`, `MarketableSecuritiesCurrent` |
| receivables             | `AccountsReceivableNetCurrent` |
| inventory               | `InventoryNet` |
| current_assets          | `AssetsCurrent` |
| total_assets            | `Assets` |
| current_liabilities     | `LiabilitiesCurrent` |
| total_liabilities       | `Liabilities` |
| short_term_debt         | `ShortTermBorrowings`, `CommercialPaper`, `DebtCurrent` |
| current_ltd             | `LongTermDebtCurrent` |
| noncurrent_ltd          | `LongTermDebtNoncurrent` |
| total_ltd_aggregate     | `LongTermDebt` (only used if components are absent — see methodology) |
| finance_lease_liab_current    | `FinanceLeaseLiabilityCurrent` |
| finance_lease_liab_noncurrent | `FinanceLeaseLiabilityNoncurrent` |
| operating_lease_liab_current    | `OperatingLeaseLiabilityCurrent` |
| operating_lease_liab_noncurrent | `OperatingLeaseLiabilityNoncurrent` |
| equity                  | `StockholdersEquity`, `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest` |
| cfo                     | `NetCashProvidedByUsedInOperatingActivities` |
| capex                   | `PaymentsToAcquirePropertyPlantAndEquipment` |
| dividends               | `PaymentsOfDividends`, `PaymentsOfDividendsCommonStock` |
| debt_issued             | `ProceedsFromIssuanceOfLongTermDebt` |
| debt_repaid             | `RepaymentsOfLongTermDebt` |

Composite concepts (total debt, net debt, EBITDA, FCF) are defined in
`docs/credit-methodology.md`, not here.

## Provenance record

Every stored number, reported or calculated, carries:

```
concept            internal name, e.g. net_debt_to_ebitda
value
unit               e.g. USD, ratio, percent — for monetary items this carries the
                   currency; there is no separate currency column (D30a)
period_start
period_end
fiscal_year
fiscal_period      FY
filing_form        10-K
filing_date
accession          SEC accession number
source_tag         the XBRL tag actually used (REPORTED only)
data_status        REPORTED | CALCULATED | ESTIMATED | ASSUMED | AI_INTERPRETED | UNAVAILABLE
method             for CALCULATED: which formula/version
inputs             for CALCULATED: list of input concept ids
reason_code        for UNAVAILABLE: why
fetched_at
superseded_by      accession of a later restatement, if any
```

Two fields that earlier drafts of this list named are deliberately **not** columns
(DECISIONS D30). `currency` is collapsed into `unit`: v1 is USD-only, so a second column
could only repeat `unit` or contradict it. `source_url` is **derived from
`(cik, accession)` when a filing link is needed**, not stored — the link is still
available, it is computed rather than persisted, because a stored copy can only drift
from EDGAR's actual URL shape.

## Codes

Two separate vocabularies, both load-bearing (D9). They are not interchangeable: a
**reason code** explains why one value is `UNAVAILABLE`, and rides on that row. A
**data-quality event** records that the pipeline made a judgement worth surfacing, and is
a row in `data_quality_events`, counted per code and read by Phase 4's data-quality panel.
A value can be present and still generate an event.

### Data-quality event codes

Defined in `normalise/quality.py`. Phase 4 adds `INTEGRITY_*` codes alongside these.

| Code | Emitted when | Decision |
|------|--------------|----------|
| `FYE_DISAGREEMENT` | Accepted duration facts for a fiscal year disagree on `end`; the most common date wins and the period is flagged | D13 |
| `FYE_TIE` | That disagreement has no single most-common date, so no anchor is chosen and nearby instants become `AMBIGUOUS_FYE` | D16(2) |
| `SAME_DAY_REFILING_TIEBREAK` | Two filings share a `filed` date for the same fact, so accession order sequences them | D16(4) |
| `CANDIDATE_TAG_DISAGREEMENT` | Two candidate tags for one concept both resolve for a period and disagree on value; the higher-priority tag is used | D17(1) |

### Reason codes on `UNAVAILABLE` rows

| Code | Applies to | Meaning | Decision |
|------|-----------|---------|----------|
| `FOREIGN_UNIT` | fact | Monetary fact in a currency other than USD. Never converted | D24 |
| `AMBIGUOUS_FYE` | fact | Instant fact near a fiscal year end that `FYE_TIE` left unanchored | D16(2) |
| `NO_FYE_ANCHOR` | fact | Instant fact whose fiscal year has no accepted duration fact to anchor it | D13 |
| `NO_CANDIDATE_TAG` | concept | No candidate tag in `tag_map.yaml` resolved for the period | D17 |
| `LEASES_NOT_SEPARABLE` | concept | Filer bundles debt and leases into one figure, so `total_debt_ex_leases` cannot be computed. Task 9 | D27 |
| `COMPONENT_AGGREGATE_MISMATCH` | concept | Debt components and the reported aggregate disagree beyond tolerance; refuses rather than picking one. Task 9 | D26 |

A refused value is never approximated from a neighbouring period, a related tag, or
subtraction from another figure (CLAUDE.md rule 11).

**What real data actually produces** (measured across all five cached companies,
2026-09-11): `CANDIDATE_TAG_DISAGREEMENT` 82 events — LUMN 15, F 32, JNJ 16, KHC 19, CCL
0 — and 2 `FOREIGN_UNIT` facts (JNJ and KHC, one each). Every other code above is
exercised only by synthetic fixtures: no cached company has produced an FYE
disagreement, tie or unanchored instant. Phase 4 should not assume the rarer codes are
unreachable, but it should expect `CANDIDATE_TAG_DISAGREEMENT` to dominate the panel.

## Data-quality summary (per company, per period)

- Completeness: % of required concepts present
- List of missing concepts
- Integrity check results (see methodology): pass / warn / fail with the numbers
- Latest filing date and form
- Which tag_map entries needed a fallback tag

## Explicitly out of scope for v1

- **Companies House (UK).** Filings are iXBRL with weak tag standardisation; many companies
  file abbreviated accounts with no P&L. It's document parsing, not an API. Post-MVP.
- **Market data / share prices.** Not needed for credit metrics. If added later, the
  source's licence must be documented first.
- **Private companies.** No accessible financials.
- **Banks, insurers, REITs, other financials.** Exclude SIC codes 6000–6799. Their balance
  sheets don't fit this methodology.
- **Quarterly data.** v2.
