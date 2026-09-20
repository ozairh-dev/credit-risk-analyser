# The golden set — what it does and does not establish

Four company-years, each hand-verified against the human-readable financial statements and
footnotes of the filing document: **CCL FY2019, YUM FY2023, MCK FY2023, BDX FY2009.**

## Why it exists

Every other test in this suite compares the engine to hand-built fixtures or to its own
prior output. They all share one failure mode: **if the engine misreads a filing
consistently, nothing notices.** A test whose expected values came from the same XBRL
payload the engine reads would inherit that blind spot exactly.

So the figures here were read from the income statement, balance sheet, cash-flow statement
and notes as a person reads them. Not from `companyfacts`, not from the cached JSON, not
from any pipeline output. The markdown files are the evidence; `tests/test_golden.py` is
the enforcement, and it **parses** those files rather than restating their numbers so the
two cannot drift apart.

## What it established

Immediately, on first contact with real filings: **four engine defects that no other test
could have found**, and one confirmation that matters as much.

| Finding | Reach across the adopted 43 |
|---|---|
| `cfo` missing where a filer tags the continuing-operations variant | **74 periods, 19 companies** |
| `total_debt` double-count in `debt_from_lease_inclusive_ltd` | up to **65 periods, 8 companies** (1 confirmed by hand) |
| `total_debt` double-count in `debt_from_aggregate` (finance leases already inside the aggregate) | MCK confirmed; not yet swept |
| `d_and_a` rank order picks a narrower tag than rank 1 | **16 periods, 2 companies** — MCD understated **80–86%** |
| **`ST_DEBT_SCOPE_UNCERTAIN` (D32) vindicated** | the refusal prevented a **13%** overstatement of BDX's debt |

The D32 result is the one worth dwelling on. The engine refuses BDX's `total_debt` because
`DebtCurrent` (402,965) may already contain `current_ltd` (200,085) and XBRL cannot settle
it. The filing's debt note settles it for a human: *Loans Payable Domestic 200,000 + Foreign
2,880 + Current portion of long-term debt 200,085 = 402,965.* **It does contain it.** A rule
written on suspicion turns out to have been right about a specific company, and the golden
set is what proved it.

The three double-count findings are one shape: **`short_term_debt` overlapping a
current-maturities figure.** D32 guards it on the components branch. The lease-inclusive and
aggregate branches have no equivalent guard. That is the same "fixed the instance, not the
mechanism" pattern the project has now hit four times.

## What it does not establish

**Four companies is four companies.** This set verifies that the engine reads *these four
filings* correctly. It does not verify that it reads all filings correctly, and nothing here
should be quoted as if it did.

More precisely, it does not establish:

- **Coverage of the other 39 adopted companies.** Every defect above was found in a
  hand-checked case and then *measured* across the universe — but the measurement is a
  count of exposure, not a verification. The 64 unverified lease-inclusive periods are
  flagged as at-risk, not confirmed wrong; KO's figures differ in magnitude and KO has
  genuine commercial paper, so some of that exposure is certainly correct.
- **Coverage of the branches these four do not exercise.** No golden case exercises the
  operating-leverage stress mode, the FYE-derivation edge cases, or five of the six
  fail-severity integrity checks.
- **That the metrics mean anything.** This is an arithmetic check against a source
  document. It says nothing about whether the bands, weights or grades are calibrated —
  they are not, and `docs/risk-scoring.md` says so.
- **That agreement proves correctness of the tag choice.** CCL agrees on all 22 rows, but
  that shows the engine and the filing coincide for CCL's tagging conventions — not that
  the tag map is right in general. MCK agreed on revenue and EBIT while being wrong on D&A.

## A limit on the method itself, found by using it

**Some figures are only obtainable from the XBRL, and the golden set cannot verify those.**
Two of the four cases needed a footnote rather than the face of a statement:

- YUM's gross interest expense (602) appears only in Note 11 prose; the income statement
  presents interest **net** (513). Both are real; the engine uses the gross figure, which is
  the more conservative choice for a coverage ratio.
- MCK's finance-lease split (29 / 173) appears only in the lease note; the balance sheet
  folds it into other lines.

Footnotes are still the filing, so those remain independently verified. But where a figure
exists **only** as an XBRL fact with no human-readable presentation, this method has nothing
to check it against — and that is a limit on the golden set, recorded rather than
worked around.

## The restatement finding, which shapes what any golden test can assert

BDX restated FY2009 in its FY2010 10-K after a divestment. Revenue 7,160,874 → 6,986,722;
operating income 1,650,353 → 1,589,682; CFO 1,691,520 → 1,658,486.

**The engine reports the restated figures and is right to** (D14/D15 supersession). The
original filing reports the first-reported ones. So five of BDX's ten disagreements are
neither engine defects nor tagging artefacts — they are the correct behaviour of a system
that prefers the most recent statement of a fact.

The consequence is general: **"verify the engine against the filing" is ambiguous whenever a
period has been restated**, and a golden test must say which filing it means. These files
say so explicitly, and BDX was kept in the set precisely because it forces the question.
