"""Does negative/near-zero book equity predict a survivor being flagged?

**Re-measured 2026-09-28 with symmetric sampling, after a first version's
asymmetric design was caught by review.** The first version sampled flagged
companies only at the cutoff(s) where they were flagged, and never-flagged
companies at every cutoff -- which conditions one group's sampling on the
very outcome being explained, and made the two groups' rates incomparable.
This version fixes that and two other issues found at the same time.

**Unit of analysis: the company-cutoff observation, not the company.** Every
survivor is evaluated at every cutoff, for both groups, identically. A
company that appears at 19 cutoffs contributes up to 19 independent rows, not
one company-level verdict -- deliberately, because "was this company negative
at the moment it was scored, and was it flagged at that same moment" is a
per-observation question. This mirrors how score_a2.py's own pooled
false-positive rate is computed (per company-cutoff, not per company), and
inherits the same pseudo-replication caveat: repeated observations of one
company are not independent draws, so read the distinct-company breakdown
alongside the pooled one, not instead of it.

**All 19 cutoffs, not 18.** The original version used A2's `admitted_cutoffs`
-- 18 cutoffs linked to *admitted* failure cases -- which silently dropped
2019-05-23 because its linked failure case (Hertz) wasn't A2-admitted. All 43
survivors are fully scored at that cutoff; Hertz's own admission status has
no bearing on a survivor-only question. The frozen case file already assigns
every one of the 19 cutoffs a dev/holdout split (`failures.yaml`'s `split`
field covers all 19 cases, not just the 18 admitted ones -- verified before
relying on it), so dev/holdout reporting below uses that existing label
rather than inventing a new rule for the 19th cutoff.

**The strict classification is read from the engine's own stored warning,
not reimplemented.** `trends/engine.py`'s LEVEL_WARNINGS fires
`negative_equity` at exactly `equity <= 0`; `a2_raw.json`'s
`warning_indicators` already carries that verdict for every scored
company-cutoff. Re-deriving `equity <= 0` here as well would be the same
invariant in two places (rule 13) -- if the engine's threshold or equity-tag
resolution ever changes, a second independent implementation would silently
drift from what the engine actually flags. The raw equity/total_assets
values are still fetched via the pipeline, because they're needed for the
near-zero band and for detecting when equity itself never resolved -- but the
negative/not-negative verdict itself is read, not recomputed.

**Equity-unavailable is its own bucket, excluded from both rate denominators
and reported on its own.** The prior version let it silently count as
"normal" in the denominator, diluting the rate with no signal that data was
missing. Zero such rows existed in the first run; kept explicit regardless,
since it wasn't caused by anything specific to that run's data.

Reads `data/raw/` via the existing normalise pipeline and `benchmark/results/
a2_raw.json` (no engine/config touched). `CONCERN_GRADE` is imported from
`score_a2`, not duplicated as a local constant.
"""

import json
import pathlib
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from pit import filter_payload                                 # noqa: E402
from score_a2 import CONCERN_GRADE                              # noqa: E402

from credit_risk.normalise import select_annual_facts, map_concepts  # noqa: E402

RAW = pathlib.Path("data/raw")
NEAR_ZERO_FRACTION = 0.05  # equity below this share of total_assets, but positive


def load_inputs():
    raw_data = json.loads(
        pathlib.Path("benchmark/results/a2_raw.json").read_text())
    survivors = yaml.safe_load(
        pathlib.Path("benchmark/cases/a2_discrimination/survivors.yaml")
        .read_text())["survivors"]
    failures = yaml.safe_load(
        pathlib.Path("benchmark/cases/a2_discrimination/failures.yaml")
        .read_text())["failures"]
    return raw_data, survivors, failures


def build_split_map(failures: list[dict]) -> dict[str, str]:
    """cutoff -> 'dev' | 'holdout', from the frozen case file.

    Covers all 19 cases, admitted or not -- verified, not assumed: every
    entry in failures.yaml carries a `split`, including Hertz's, which is
    not part of the discrimination set but still anchors a real cutoff.
    """
    split_by_cutoff = {c["pit_cutoff"]: c["split"] for c in failures}
    assert len(split_by_cutoff) == len(failures), \
        "cutoff collision across cases -- the split map assumes one case per cutoff"
    return split_by_cutoff


def equity_and_assets_at(payload_cache, cik_by_ticker, ticker, cutoff, period_end):
    if ticker not in payload_cache:
        cik = cik_by_ticker[ticker]
        payload_cache[ticker] = json.loads(
            (RAW / f"CIK{cik:010d}.json").read_text())["content"]
    pit = filter_payload(payload_cache[ticker], cutoff)
    mapping = map_concepts(select_annual_facts(pit))
    got = {c.concept: c.value for c in mapping.concepts if c.end == period_end}
    return got.get("equity"), got.get("total_assets")


def loose_class(equity, total_assets) -> str:
    """negative / near_zero / normal / unavailable.

    Not the strict verdict -- that comes from the engine's own stored
    warning. This is the secondary, finer-grained band the engine does not
    compute natively, so there is no stored value to defer to here.
    """
    if equity is None:
        return "unavailable"
    if equity <= 0:
        return "negative"
    if total_assets and equity / total_assets < NEAR_ZERO_FRACTION:
        return "near_zero"
    return "normal"


def build_rows(raw_data, survivors, split_by_cutoff) -> list[dict]:
    cik_by_ticker = {s["ticker"]: s["cik"] for s in survivors}
    all_cutoffs = sorted(raw_data["panels"].keys())
    assert len(all_cutoffs) == 19, f"expected 19 cutoffs, found {len(all_cutoffs)}"
    assert set(split_by_cutoff) == set(all_cutoffs), \
        "the frozen case file's cutoffs don't match a2_raw.json's panels"

    payload_cache: dict = {}
    rows = []
    for ticker in sorted(cik_by_ticker):
        for cutoff in all_cutoffs:
            panel = raw_data["panels"][cutoff][ticker]
            if not panel["scored"]:
                continue
            eq, ta = equity_and_assets_at(payload_cache, cik_by_ticker, ticker,
                                          cutoff, panel["period_end"])
            strict_negative = (
                "negative_equity" in panel["warning_indicators"]
                if eq is not None else None)
            rows.append({
                "ticker": ticker, "cutoff": cutoff, "split": split_by_cutoff[cutoff],
                "flagged": panel["grade"] is not None
                          and panel["grade"] >= CONCERN_GRADE,
                "equity": eq, "total_assets": ta,
                "strict_negative": strict_negative,
                "loose_class": loose_class(eq, ta),
            })
    return rows


def _rate(group: list[dict], predicate) -> tuple[float | None, int, int]:
    n = len(group)
    if n == 0:
        return None, 0, 0
    hits = sum(1 for r in group if predicate(r))
    return hits / n, hits, n


def summarize(rows_subset: list[dict], label: str) -> dict:
    n_total = len(rows_subset)
    n_unavailable = sum(1 for r in rows_subset if r["equity"] is None)
    available = [r for r in rows_subset if r["equity"] is not None]
    flagged = [r for r in available if r["flagged"]]
    not_flagged = [r for r in available if not r["flagged"]]

    strict_f = _rate(flagged, lambda r: r["strict_negative"])
    strict_n = _rate(not_flagged, lambda r: r["strict_negative"])
    loose_f = _rate(flagged, lambda r: r["loose_class"] in ("negative", "near_zero"))
    loose_n = _rate(not_flagged, lambda r: r["loose_class"] in ("negative", "near_zero"))

    def fmt(rate_tuple):
        rate, hits, n = rate_tuple
        return "n/a (0 obs)" if rate is None else f"{hits}/{n} = {rate:.1%}"

    def diff(a, b):
        return None if a[0] is None or b[0] is None else (a[0] - b[0]) * 100

    print(f"\n=== {label} ===")
    print(f"  {n_total} observations total, {n_unavailable} equity-unavailable "
          f"(excluded below), {len(available)} usable")
    print(f"  flagged: {len(flagged)} obs   not-flagged: {len(not_flagged)} obs")
    print(f"  STRICT (engine's stored negative_equity warning):")
    print(f"    flagged:     {fmt(strict_f)}")
    print(f"    not-flagged: {fmt(strict_n)}")
    d = diff(strict_f, strict_n)
    print(f"    difference:  {d:+.1f}pp" if d is not None else "    difference:  n/a")
    print(f"  LOOSE (negative or <{NEAR_ZERO_FRACTION:.0%} of total assets):")
    print(f"    flagged:     {fmt(loose_f)}")
    print(f"    not-flagged: {fmt(loose_n)}")
    d2 = diff(loose_f, loose_n)
    print(f"    difference:  {d2:+.1f}pp" if d2 is not None else "    difference:  n/a")

    # distinct-company view, for the pseudo-replication cross-check the
    # docstring promises -- "ever negative at a flagged obs" vs "ever
    # negative at a not-flagged obs", one row per company
    companies_flagged = {r["ticker"] for r in flagged}
    companies_not_flagged = {r["ticker"] for r in not_flagged}
    strict_co_f = sum(1 for t in companies_flagged
                      if any(r["ticker"] == t and r["strict_negative"]
                            for r in flagged))
    strict_co_n = sum(1 for t in companies_not_flagged
                      if any(r["ticker"] == t and r["strict_negative"]
                            for r in not_flagged))
    print(f"  distinct companies: {len(companies_flagged)} ever flagged "
          f"({strict_co_f} with a strict-negative flagged obs), "
          f"{len(companies_not_flagged)} ever not-flagged "
          f"({strict_co_n} with a strict-negative not-flagged obs)")

    return {
        "n_total": n_total, "n_unavailable": n_unavailable,
        "n_flagged_obs": len(flagged), "n_not_flagged_obs": len(not_flagged),
        "strict": {"flagged_hits": strict_f[1], "flagged_n": strict_f[2],
                  "flagged_rate": strict_f[0],
                  "not_flagged_hits": strict_n[1], "not_flagged_n": strict_n[2],
                  "not_flagged_rate": strict_n[0], "diff_pp": diff(strict_f, strict_n)},
        "loose": {"flagged_hits": loose_f[1], "flagged_n": loose_f[2],
                 "flagged_rate": loose_f[0],
                 "not_flagged_hits": loose_n[1], "not_flagged_n": loose_n[2],
                 "not_flagged_rate": loose_n[0], "diff_pp": diff(loose_f, loose_n)},
        "distinct_companies": {
            "flagged_total": len(companies_flagged),
            "flagged_with_strict_negative": strict_co_f,
            "not_flagged_total": len(companies_not_flagged),
            "not_flagged_with_strict_negative": strict_co_n,
        },
    }


def main() -> int:
    raw_data, survivors, failures = load_inputs()
    split_by_cutoff = build_split_map(failures)
    rows = build_rows(raw_data, survivors, split_by_cutoff)

    print(f"unit of analysis: company-cutoff observation")
    print(f"{len(rows)} scored observations across "
          f"{len({r['ticker'] for r in rows})} survivors and "
          f"{len({r['cutoff'] for r in rows})} cutoffs "
          f"(19 available, all used)")

    results = {
        "all": summarize(rows, "ALL (pooled, 19 cutoffs, both splits)"),
        "dev": summarize([r for r in rows if r["split"] == "dev"], "DEV"),
        "holdout": summarize([r for r in rows if r["split"] == "holdout"], "HOLDOUT"),
    }

    out = pathlib.Path("benchmark/results/negative_equity_measurement.json")
    out.write_text(json.dumps({
        "unit_of_analysis": "company-cutoff observation",
        "near_zero_fraction_threshold": NEAR_ZERO_FRACTION,
        "n_cutoffs": 19,
        "concern_grade": CONCERN_GRADE,
        "results": results,
        "rows": rows,
    }, indent=1, default=str))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
