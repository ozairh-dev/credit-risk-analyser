"""Item 4 — does negative/near-zero book equity explain the false positives?

Measurement only. Reads data/raw/ via the existing normalise pipeline (no
engine/config touched), applies pit.py the same way assess() does, and reports
equity at the specific periods each survivor was actually scored on.
"""
import json, pathlib, sys
sys.path.insert(0, "benchmark/harness")
from pit import filter_payload
from credit_risk.normalise import select_annual_facts, map_concepts
import yaml

RAW = pathlib.Path("data/raw")
raw_data = json.load(open("benchmark/results/a2_raw.json"))
scored = json.load(open("benchmark/results/a2_scored.json"))
survivors = yaml.safe_load(open("benchmark/cases/a2_discrimination/survivors.yaml"))["survivors"]
cik_by_ticker = {s["ticker"]: s["cik"] for s in survivors}

flagged_tickers = set(scored["splits"]["all"]["flagged_survivor_companies"])
all_tickers = set(cik_by_ticker)
never_flagged_tickers = all_tickers - flagged_tickers
print(f"flagged: {len(flagged_tickers)}   never-flagged: {len(never_flagged_tickers)}"
      f"   total: {len(all_tickers)}")
assert len(flagged_tickers) == 21 and len(never_flagged_tickers) == 22

# cutoffs used in the "all" split (18 admitted failure cutoffs)
cutoffs = sorted(raw_data["panels"].keys())
admitted_cutoffs = sorted({c["pit_cutoff"] for c in raw_data["cases"] if c["admitted"]})
assert len(admitted_cutoffs) == 18

FLAG_GRADE = 5  # matches CONCERN_GRADE in score_a2.py

_payload_cache = {}
def payload(ticker):
    if ticker not in _payload_cache:
        cik = cik_by_ticker[ticker]
        _payload_cache[ticker] = json.load(open(RAW / f"CIK{cik:010d}.json"))["content"]
    return _payload_cache[ticker]

def equity_at(ticker, cutoff, period_end):
    """(equity, total_assets) at `period_end`, point-in-time filtered to `cutoff`."""
    pit = filter_payload(payload(ticker), cutoff)
    mapping = map_concepts(select_annual_facts(pit))
    got = {c.concept: c.value for c in mapping.concepts if c.end == period_end}
    return got.get("equity"), got.get("total_assets")

def classify(equity, total_assets):
    if equity is None:
        return "unavailable"
    if equity <= 0:
        return "negative"
    if total_assets and equity / total_assets < 0.05:
        return "near_zero"
    return "normal"

def per_company_flags(tickers, cutoffs_for):
    """For each ticker, per-cutoff (grade, equity classification) at that ticker's
    relevant cutoffs — flagging cutoffs for flagged companies, all 18 for the rest."""
    rows = {}
    for t in sorted(tickers):
        rows[t] = []
        for cutoff in cutoffs_for(t):
            panel = raw_data["panels"][cutoff][t]
            if not panel["scored"]:
                continue
            eq, ta = equity_at(t, cutoff, panel["period_end"])
            rows[t].append({
                "cutoff": cutoff, "period_end": panel["period_end"],
                "grade": panel["grade"], "equity": eq, "total_assets": ta,
                "class": classify(eq, ta),
            })
    return rows

def flagging_cutoffs(ticker):
    return [c for c in admitted_cutoffs
            if raw_data["panels"][c][ticker]["scored"]
            and raw_data["panels"][c][ticker]["grade"] >= FLAG_GRADE]

def all_cutoffs(ticker):
    return admitted_cutoffs

flagged_rows = per_company_flags(flagged_tickers, flagging_cutoffs)
never_rows = per_company_flags(never_flagged_tickers, all_cutoffs)

def company_verdict(rows):
    """True if ANY observation for this company hits negative or near-zero."""
    classes = {r["class"] for r in rows}
    return {
        "any_negative": "negative" in classes,
        "any_near_zero_or_negative": bool(classes & {"negative", "near_zero"}),
        "n_obs": len(rows),
    }

print("\n=== FLAGGED (21) — equity at the cutoff(s) where each was flagged ===")
flagged_summary = {}
for t, rows in flagged_rows.items():
    v = company_verdict(rows)
    flagged_summary[t] = v
    detail = ", ".join(f"{r['cutoff']}:eq={r['equity']:,.0f}" if r['equity'] is not None
                       else f"{r['cutoff']}:eq=?" for r in rows)
    print(f"  {t:5} neg={v['any_negative']!s:5} nearzero_or_neg="
          f"{v['any_near_zero_or_negative']!s:5} n={v['n_obs']}  [{detail}]")

print("\n=== NEVER-FLAGGED (22) — equity across all 18 cutoffs ===")
never_summary = {}
for t, rows in never_rows.items():
    v = company_verdict(rows)
    never_summary[t] = v
    n_neg = sum(1 for r in rows if r["class"] == "negative")
    print(f"  {t:5} neg={v['any_negative']!s:5} nearzero_or_neg="
          f"{v['any_near_zero_or_negative']!s:5} n={v['n_obs']}"
          f"  (negative at {n_neg}/{v['n_obs']} cutoffs)")

def rate(summary, key):
    n = len(summary)
    hits = sum(1 for v in summary.values() if v[key])
    return hits, n, hits / n

print("\n=== RESULT ===")
for key, label in (("any_negative", "STRICT: negative equity"),
                   ("any_near_zero_or_negative", "LOOSE: negative or <5% of assets")):
    fh, fn, fr = rate(flagged_summary, key)
    nh, nn, nr = rate(never_summary, key)
    print(f"{label}")
    print(f"  flagged (21):      {fh}/{fn} = {fr:.1%}")
    print(f"  never-flagged (22): {nh}/{nn} = {nr:.1%}")
    print(f"  difference: {(fr-nr)*100:+.1f}pp")

out = {"flagged": flagged_summary, "never_flagged": never_summary,
      "flagged_detail": flagged_rows, "never_flagged_detail": never_rows}
pathlib.Path("benchmark/results/negative_equity_measurement.json").write_text(
    json.dumps(out, indent=1, default=str))
print("\nwrote benchmark/results/negative_equity_measurement.json")
