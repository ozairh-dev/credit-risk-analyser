"""Fetch the A2 failure cohort's companyfacts so the backtest can be re-run.

`data/benchmark/raw/` is gitignored, like `data/raw/` — the payloads are public
SEC data and do not belong in the repository. So a fresh clone has the harness
and the cases but not the data, and this is the one command that closes the gap:

    .venv/bin/python benchmark/harness/fetch_cohort.py

**The CIKs are read from `failures.yaml`, never listed here.** A second copy of
the cohort would be a second place for it to drift (CLAUDE.md rule 13), and the
case file is the frozen record.

Caches to `data/benchmark/raw/`, deliberately separate from `data/raw/` so the
benchmark cannot silently widen `tests/test_real_companies.py`, which globs that
directory — the accident D68 records. Re-running is cheap: `fetch_companyfacts`
honours the 24h staleness window, so an existing cache is not re-downloaded.
"""

import pathlib
import sys

import yaml

from credit_risk.ingest.companyfacts import fetch_companyfacts

CASES = pathlib.Path("benchmark/cases/a2_discrimination/failures.yaml")
OUT = pathlib.Path("data/benchmark/raw")


def main() -> int:
    cohort = yaml.safe_load(CASES.read_text())["failures"]
    OUT.mkdir(parents=True, exist_ok=True)
    failed = []
    for case in cohort:
        path = OUT / f"CIK{case['cik']:010d}.json"
        try:
            payload = fetch_companyfacts(case["cik"], cache_path=path)
        except Exception as exc:                                # noqa: BLE001
            failed.append((case["ticker"], f"{type(exc).__name__}: {exc}"))
            print(f"{case['ticker']:5} {case['cik']:>8}  FAILED  {exc}")
            continue
        print(f"{case['ticker']:5} {case['cik']:>8}  "
              f"{payload.get('entityName', '?')[:40]:42} "
              f"{len(payload.get('facts', {}).get('us-gaap', {})):>4} us-gaap tags")

    print(f"\n{len(cohort) - len(failed)} of {len(cohort)} cached in {OUT}")
    if failed:
        print("failed:", ", ".join(t for t, _e in failed))
        return 1
    print("Next: benchmark/harness/run_a2.py, then score_a2.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
