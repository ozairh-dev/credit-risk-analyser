"""A2 — external discrimination backtest.

Scores the failure cohort and a matched survivor panel at the SAME point-in-time
cutoff, through the same `assess()` call, and writes the raw record. It computes
no verdict: `score.py` does that, so the measurement and the grading of the
measurement stay separable.

**What this can and cannot show.** It asks whether the engine's pre-event view
of companies that later filed Chapter 11 was worse than its view of companies
that did not. That is *discrimination* on a small sample. It is not calibration:
nothing here maps a grade to a default probability, and 18 events cannot.
"""

import json
import pathlib
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from assess import assess, load_payload                       # noqa: E402

FAILURES = pathlib.Path("benchmark/cases/a2_discrimination/failures.yaml")
SURVIVORS = pathlib.Path("benchmark/cases/a2_discrimination/survivors.yaml")
BENCH_RAW = pathlib.Path("data/benchmark/raw")
MAIN_RAW = pathlib.Path("data/raw")
OUT = pathlib.Path("benchmark/results/a2_raw.json")


def run(out_path=OUT) -> dict:
    failures = yaml.safe_load(FAILURES.read_text())
    survivors = yaml.safe_load(SURVIVORS.read_text())

    # Cache payloads once: the survivor panel is re-assessed at every cutoff,
    # so re-reading 43 multi-megabyte files per cutoff would dominate runtime.
    payloads = {}

    def payload(cik, directory):
        if cik not in payloads:
            payloads[cik] = load_payload(directory / f"CIK{cik:010d}.json")
        return payloads[cik]

    cases = []
    for f in failures["failures"]:
        record = {k: f[k] for k in (
            "ticker", "cik", "sic", "sector_group", "event", "event_date",
            "source_accession", "pit_cutoff", "admitted", "split")}
        record["assessment"] = assess(payload(f["cik"], BENCH_RAW),
                                      f["pit_cutoff"])
        cases.append(record)

    # One survivor panel per DISTINCT cutoff, so a cutoff shared by two cases is
    # not assessed twice and cannot come out differently.
    panels = {}
    for cutoff in sorted({f["pit_cutoff"] for f in failures["failures"]}):
        panel = {}
        for s in survivors["survivors"]:
            excl = s.get("excluded_before")
            if excl and cutoff < excl:
                # not a valid survivor at this cutoff — see survivors.yaml
                continue
            panel[s["ticker"]] = assess(payload(s["cik"], MAIN_RAW), cutoff)
        panels[cutoff] = panel

    result = {
        "min_categories": failures["min_categories"],
        "lead_days": failures["lead_days"],
        "cases": cases,
        "panels": panels,
        "survivor_count": len(survivors["survivors"]),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=1))
    return result


if __name__ == "__main__":
    r = run()
    print(f"wrote {OUT}")
    adm = [c for c in r["cases"] if c["admitted"]]
    print(f"  {len(r['cases'])} cases ({len(adm)} admitted), "
          f"{len(r['panels'])} survivor panels, "
          f"{r['survivor_count']} survivors")
