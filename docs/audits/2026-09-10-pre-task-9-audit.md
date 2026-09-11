Audit complete. Nothing was changed — all findings are from reading the code, branch-coverage data, and running the pipeline over the cached filings in throwaway scripts.

# Audit: Tasks 1–8 before Task 9

Branch coverage is 95% (508 statements, 164 branches), but coverage turned out to be the least interesting signal. The decisive finding came from doing something no test does: running the full pipeline over the five cached companies.

---

## BLOCKING — must be fixed before Task 9

### 1. Selection treats a duration fact and an instant fact as the same fact — KHC cannot be stored at all
**HIGH · correctness + crash**

**What:** `select_annual_facts` groups facts for rule 4 supersession by `(tag, period_end)` (`selection.py`, the `groups` dict). A *duration* fact (a flow over a period) and an *instant* fact (a stock at a date) that share an end date land in the same group and supersede each other. Real example, KHC `GoodwillImpairmentLoss` ending 2018-12-29:

| value | shape | accession | status assigned |
|---|---|---|---|
| 7,008M | duration | `…-19-000049` | SUPERSEDED by **`…-19-000049`** — its own accession |
| 6,900M | **instant** | `…-19-000049` | SUPERSEDED |
| 7,008M | duration | `…-20-000027` | CURRENT |
| 7,008M | duration | `…-21-000009` | DUPLICATE |

**How found:** ran `store_company_data` over each cached company. Four succeed; **KHC raises `ValueError: superseding fact not found for GoodwillImpairmentLoss 2018-12-29`** and stores nothing. KHC's second affected group (`ImpairmentOfIntangibleAssets…`) does *not* crash — there an **instant** fact (8,600M) became CURRENT and superseded a **duration** fact (8,925M). Whether it crashes or silently picks the wrong shape depends on insertion order, which makes it latent rather than reliably visible.

**Why it matters:** three distinct consequences. (a) A whole company fails to store — KHC is the D27 witness you deliberately retained. (b) A fact can be recorded as superseded by its own filing, which is meaningless provenance and contradicts D15's intent. (c) The wrong-shape value can win, which is the plausible-but-wrong class rule 9 exists to prevent. Measured scope: 2 groups in KHC, 0 in F/JNJ/LUMN/CCL, and **no currently-mapped tag is dual-shaped in any cached company** — so no concept value is wrong *today*. Task 9 reads concepts, so it inherits the hole rather than triggering it.

**Smallest fix:** a fact's identity is `(tag, period type, period end)`, not `(tag, period end)`. Add the discriminator in the three places that encode identity: the rule-4 group key in `selection.py`, `uq_facts_current` in `schema.py`, and the superseder lookup in `writer.py`. Nothing is persisted yet, so there's no migration. (Fail-safe alternative, if you'd rather not widen the identity: refuse mixed-shape groups with a new reason code. That's more conservative but loses both facts.)

### 2. Not one test reads any real filing — which is exactly how finding 1 survived
**HIGH · process**

**What:** `grep` for `data/raw` or `CIK00000` across `tests/` returns nothing. All 118 tests run against the hand-built fixture or small synthetic dicts. Every real-data behaviour established this session — Ford's repurposed tag, WBD's partial-components understatement, LUMN's lease bundling, JNJ's exact aggregate agreement, CCL's 7.9% deviation, the single EUR `FOREIGN_UNIT` fact — was verified in throwaway scratchpad scripts that are not part of the suite.

**How found:** grep, then confirmed by the coverage gaps all sitting on paths only real data reaches.

**Why it matters:** finding 1 is a crash on data that has been sitting in `data/raw/` for hours. Nothing would have caught it, and nothing will catch the next one. Every D13–D27 conclusion is currently unprotected against regression.

**Smallest fix:** one test module that, for each cached company, runs select → map → store and asserts the headline invariants (stores without raising; fact/concept/event counts; re-store is idempotent). That single test would have failed on KHC immediately. Keep it skipped-if-absent so a clean checkout without `data/raw/` still passes.

### 3. D6's config toggles exist only as Python constants — and Task 9 is what reads them
**HIGH · rule-6 violation, directly blocking**

**What:** `include_operating_leases` and `include_st_investments` are defined **only** in `store/fingerprint.py`'s `COMPOSITE_DEFAULTS`. `config/composites.yaml` mentions them in a comment and defines neither. CLAUDE.md rule 6: thresholds and stress defaults live in `config/*.yaml`, *never in code*. D6 describes the lease toggle as config-controlled.

**How found:** `grep -rn "include_operating_leases" config/ src/` → two hits in `fingerprint.py`, one in a YAML comment.

**Why it matters:** Task 9's `total_debt` and `net_debt` are the first code to read these. If it reads `COMPOSITE_DEFAULTS`, D6's toggle is hard-coded in Python and the fingerprint machinery (D18) is fingerprinting a value no config file can change.

**Smallest fix:** add both keys to `config/composites.yaml` with the methodology's documented defaults (`true`/`true`), before Task 9 writes a line.

### 4. The methodology contradicts itself on `total_debt_ex_leases`, 44 lines apart
**MEDIUM-HIGH · spec ambiguity in exactly what Task 9 builds**

**What:** `docs/credit-methodology.md` line 33 — "Always show `total_debt_ex_leases` alongside so the effect is visible." Line 77, inside D27's branch — "`total_debt_ex_leases` → `UNAVAILABLE`, `reason_code = LEASES_NOT_SEPARABLE`." Both are live text in one document. D6's consequences line ("ex-lease figure always shown alongside") was likewise never amended when D27 landed.

**How found:** grepped `ex_leases` across docs after noticing D27 introduced an exception to an absolute.

**Why it matters:** Task 9 implements both statements. An implementer following line 33 produces a number where D27 requires a refusal.

**Smallest fix:** qualify line 33 ("except on the lease-inclusive branch, where it is `UNAVAILABLE` — see below") and add one line to D6's consequences pointing at D27.

### 5. The superseder lookup is neither unique nor order-deterministic
**MEDIUM · the proximate cause of finding 1's crash**

**What:** `writer.py:108` looks up the superseding fact by `(cik, tag, period_end, accession)` — not a unique key, since one accession can carry several facts for the same `(tag, end)`. And same-`filed` SUPERSEDED rows are inserted in unspecified order (`sorted(..., key=filed, reverse=True)` with no tiebreak), so the lookup can run before its target exists.

**How found:** coverage showed line 113 (`raise ValueError`) uncovered; the KHC run then executed it.

**Why it matters:** even with finding 1 fixed, this remains a latent ordering bug rather than a defended invariant. Note D16(4) already decided that same-`filed` ties break by accession order — that tiebreak is applied in `selection.py` but **not** in the writer's insertion sort, so the two disagree.

**Smallest fix:** add `accn` to the writer's sort key so it matches D16(4), and make the lookup deterministic by also matching the value/shape.

---

## NON-BLOCKING

### 6. `data_quality_events` is only ever asserted to be empty
`writer.py:213–221` — the entire event-storage path — is uncovered. The only test touching the table asserts `count == 0`. Yet real data produces events readily: **F 32, JNJ 16, LUMN 15** `CANDIDATE_TAG_DISAGREEMENT` records. Task 8's design made these "first-class, queried, counted," and the `event_counts` query has only ever been run against an empty table. *Fix:* the finding-2 test covers this for free.

### 7. `UNAVAILABLE` fact storage and filings-from-unavailable are untested but do work
`writer.py:45–46` and `121–129` uncovered. I ran them manually: storing JNJ produces 1 `UNAVAILABLE` fact row (`SubsequentEventAmount`, EUR, `FOREIGN_UNIT`) and — notably — **a `10-Q` filing row**, because that EUR fact comes from a 10-Q and rule 5 fires before rule 1. That retroactively validates D21's removal of the `form` CHECK; without it, storing JNJ would fail. Worth having a test assert that, since it's a non-obvious dependency between two decisions.

### 8. `config/ingestion.yaml`'s `max_age_hours` is never proven load-bearing
No test mentions it. If someone re-hardcoded 24h into `cache.py`, all 118 tests would pass. Contrast `test_mapping_order_is_config_driven`, which proves the tag map's authority by reversing a list. *Fix:* one test that sets `max_age_hours` low and asserts a 2-hour-old cache is treated as stale. Also: the exact 24h boundary is untested (tests use 1h and 25h).

### 9. Provenance-record drift: docs promise two fields the schema doesn't have
`docs/data-sources.md`'s provenance record lists `currency` (separate from `unit`) and `source_url`. The schema has **neither** column. Both omissions were deliberate and I explained them in the Task 8 design conversation — `currency` collapsed into `unit` because v1 is USD-only, `source_url` derived from `(cik, accession)` at export — but **neither was ever written into DECISIONS.md**, so the only record is a chat message. The doc still reads as a requirement. *Fix:* one decision entry, or amend the doc's field list.

### 10–12. Superseded decisions never amended
- **D2** — "migration to Postgres later is mechanical **via SQLAlchemy**". D22 removed SQLAlchemy from the stack.
- **D6** — "ex-lease figure always shown alongside". Contradicted by D27 (see finding 4).
- **Event-code vocabulary undocumented** — `AMBIGUOUS_FYE`, `FYE_DISAGREEMENT`, `FYE_TIE`, `SAME_DAY_REFILING_TIEBREAK`, `CANDIDATE_TAG_DISAGREEMENT` are implemented and tested but appear in **no `docs/` file**. `docs/data-sources.md` documents only `NO_FYE_ANCHOR`. For a project where "reason codes are load-bearing" (D9), the vocabulary living only in code and DECISIONS is a gap Phase 4's data-quality panel will hit.

### 13. I weakened six assertions this session — disclosing it
When the tag map grew 31→34 concepts, I changed six tests from hard-coded counts (62/55/124) to `len(config.tag_map()) * 2`. That makes the count assertion **self-referential**: if a concept were accidentally deleted from `tag_map.yaml`, code and test would shift together and still pass. The exact assertions (7 resolve, and which 7) still hold, so this is a weakening rather than a hole — but it's the one place in the suite where an expected value is now derived from the same input the code reads. *Fix, if you want it:* assert the literal concept count alongside, so a deletion fails loudly.

### 14. Minor test gaps
`credit-risk version` (cli.py 21–24) has no test. `assert __version__` is tautological — any non-empty string passes. `config.py:22`'s missing-file error and `db.py:19`'s on-disk path are uncovered (all tests use `:memory:`). `fingerprint.py:43–44`'s `FileNotFoundError` fallback is now **dead code** — `composites.yaml` exists, so the fallback can't be reached, though the defaults still apply via `loaded.get(key, default)`.

### 15. Spec assumptions still unvalidated, ranked by what breaks
Measured across all five cached companies:

| Assumption | Status | If wrong |
|---|---|---|
| Rule 2's 350–380 day window | **Partly validated.** Observed durations span **362–372 days** only — ~12 days of headroom each side. A fiscal-year-change stub would be excluded (correctly, as Ford's 274-day case showed). | A legitimate annual period silently dropped |
| D13 FYE derivation / D16(1) 14-day clustering | **Never exercised by real data.** Zero companies have two accepted duration end-dates within 14 days; all five produce **0 selection warnings**. Disagreement, tie, `AMBIGUOUS_FYE` and `NO_FYE_ANCHOR` are synthetic-only. | Wrong fiscal-year anchor; instants attached to the wrong year |
| Rule 1's 10-K/A acceptance | **Validated** — LUMN contributes **312 facts from 10-K/A filings**. But no test uses LUMN, so it's validated by my probe, not by the suite. | Amended filings ignored |
| "Debt ⊆ liabilities" integrity check | **Cannot run for 3 of 5** cached companies: `total_debt_ex_leases` is UNAVAILABLE for LUMN and KHC under D27, and CCL reports no `Liabilities` tag. Only JNJ can exercise it. | Phase 4 ships a check with almost no live coverage |
| D15 equal-value duplicates | Validated on real data — F/JNJ/LUMN/CCL all produce large DUPLICATE populations (2,461–4,167 rows) and all re-store idempotently | — |

---

## Categories that came back clean

**Finding 3 — tests that would pass against broken code: substantially clean, and better than typical.** The Task 5–8 expected values were written into `companyfacts_minimal_expected.md` and the Task 8 design document *before* the code existed and were owner-reviewed, so they're independent oracles rather than code-derived. The exact-set assertions (9 facts with accessions and statuses, the 7 resolved concepts, the restatement self-join returning exactly one row) would all fail on subtly wrong logic. The only real offenders are #13 (my own change) and `assert __version__`.

**Finding 6 — cross-module interactions: the fixture chain is genuinely covered end-to-end.** `test_store_schema.py`'s `stored` fixture runs fixture JSON → `select_annual_facts` → `map_concepts` → `store_company_data`, and the D15 duplicate, D18b idempotency and provenance constraints are all asserted across that boundary. The gap is that it's only ever the fixture — which is finding 2, not a separate hole.

---

## What Task 9 inherits

**Solid:** selection and mapping produce correct values for every mapped concept in all five cached companies. The store's constraints genuinely enforce the six `data_status` values, supersession-as-relationship, and append-with-history. D13–D27 are all implemented where their task has run, and the four "not yet implemented" ones (D5, D23, D26, D27's branch logic) are Task 9/10's job by design, not drift.

**Not solid:** the fact-identity bug (#1) means the store rejects one real company and can prefer a wrong-shape value. `total_debt`'s two config toggles don't exist in config (#3) — Task 9 cannot implement D6 correctly without them. The methodology contradicts itself on the exact output Task 9 produces (#4). And there is no regression net under any of it (#2), which is why #1 went unnoticed for a day.

## Verdict

**Not fit for Task 9 as it stands** — but the gap is small and well-defined, not structural. Three things must be fixed first:

1. **Finding 3** (add the two toggles to `config/composites.yaml`) — minutes, and Task 9 literally cannot implement D6 without it.
2. **Finding 1 + 5** (widen fact identity to include period shape, in selection, schema and writer) — the only correctness bug found, and the only thing that breaks a real company.
3. **Finding 4** (resolve the `total_debt_ex_leases` contradiction) — otherwise Task 9 must guess which sentence governs.

**Finding 2** doesn't block Task 9 mechanically, but I'd do it in the same pass: one real-data end-to-end test is what turns this audit's conclusions into something the suite defends. Everything else — findings 6–15 — is safe to carry into Task 9 and clean up after.

One loose end from before this audit: the `CLAUDE.md` layout trim is still unresolved (you'd answered "Let me pick" and then redirected). Nothing was changed, so it's still pending whenever you want it.
