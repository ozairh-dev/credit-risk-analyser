"""Generate benchmark/cases/a2_discrimination/failures.yaml from verified inputs.

Generated rather than hand-typed, because a count or a date restated by hand is
how D79's dropped defect and D71's arithmetic slip happened. The only values
entered by hand here are the ones that came from reading a document — the
petition date and its 8-K — and each carries the sentence it was read from.

**Petition dates come from the 8-K TEXT, never from the submissions index.**
Measured across these 19 cases, the index `reportDate` disagrees with the
document's stated petition date in **8 of 19 (42%)** — Hertz 2020-05-19 against
May 22, Windstream 2019-02-28 against February 25, Whiting 2020-03-26 against
April 1, GNC 2020-06-18 against June 23. Windstream's is the one that changes an
outcome: the correct date moves the cutoff to 2018-02-25, which excludes the
FY2017 10-K filed 2018-02-28 and drops the evaluated period to FY2016.

The index item tag is not a reliable oracle either: J.C. Penney's 2014-01-28
filing is tagged Item 1.03 and its text contains no bankruptcy language at all.
Every event below was confirmed by reading the filing.
"""

import json
import pathlib
import sys
from datetime import date, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from pit import as_of_for_event, filter_payload            # noqa: E402

from credit_risk import pipeline                            # noqa: E402

RAW = pathlib.Path("data/benchmark/raw")
OUT = pathlib.Path("benchmark/cases/a2_discrimination/failures.yaml")

# The minimum share of the five scoring categories that must score at the
# cutoff for a case to enter the DISCRIMINATION metrics. Below this the output
# is dominated by what is missing rather than by what is measured, so the
# metric would be reporting coverage, not discrimination. A failing case is
# retained and reported separately — hiding it would overstate coverage, and
# counting it would blame the discrimination model for a coverage defect.
MIN_CATEGORIES = 3

# Sector groups for the stratified hold-out split. Grouped from the SEC's own
# SIC, not invented.
SECTOR_GROUP = {
    "5311": "retail_consumer", "5700": "retail_consumer",
    "5912": "retail_consumer", "5400": "retail_consumer",
    "5600": "retail_consumer", "5900": "retail_consumer",
    "2844": "retail_consumer",
    "1311": "energy", "1381": "energy",
    "4813": "telecom",
    "7510": "transport_industrial", "4213": "transport_industrial",
    "3578": "transport_industrial", "3510": "transport_industrial",
}

# (ticker, cik, sic, entity name at the event, name now, petition date,
#  8-K accession, 8-K document, the sentence the date was read from)
CASES = [
 ("HTZ", 1657853, "7510", "Hertz Global Holdings, Inc.", "HERTZ GLOBAL HOLDINGS, INC",
  "2020-05-22", "0001104659-20-065674", "tm2020858d1_8k.htm",
  "On May 22, 2020, Hertz Global Holdings, Inc. ... and certain of their direct and indirect subsidiaries ... filed voluntary petitions"),
 ("JCP", 1166126, "5311", "J. C. Penney Company, Inc.", "Old COPPER Company, Inc.",
  "2020-05-15", "0001193125-20-144411", "d813078d8k.htm",
  "On May 15, 2020 (the Petition Date), J. C. Penney Company, Inc. ... commenced voluntary cases"),
 ("FTR", 20520, "4813", "Frontier Communications Corporation", "Frontier Communications Parent, Inc.",
  "2020-04-14", "0001140361-20-008876", "form8k.htm",
  "on April 14, 2020 (the Petition Date), the Company Parties filed the Chapter 11 Cases"),
 ("CHK", 895126, "1311", "Chesapeake Energy Corporation", "EXPAND ENERGY Corp",
  "2020-06-28", "0001104659-20-077745", "tm2023599-1_8k.htm",
  "On June 28, 2020, the Company filed voluntary petitions for reorganization under Chapter 11"),
 ("WIN", 1282266, "4813", "Windstream Holdings, Inc.", "WINDSTREAM HOLDINGS, INC.",
  "2019-02-25", "0001282266-19-000005", "a20190228form8-k.htm",
  "On February 25, 2019 (the Petition Date), Windstream Holdings and all of its subsidiaries ... filed voluntary petitions"),
 ("BBBY", 886158, "5700", "Bed Bath & Beyond Inc.", "20230930-DK-Butterfly-1, Inc.",
  "2023-04-23", "0001193125-23-111754", "d465247d8k.htm",
  "On April 23, 2023 (the Petition Date), Bed Bath and Beyond, Inc. ... filed a voluntary petition"),
 ("RAD", 84129, "5912", "Rite Aid Corporation", "New Rite Aid, LLC",
  "2023-10-15", "0001104659-23-109236", "tm2328505d1_8k.htm",
  "On October 15, 2023 (the Petition Date), Rite Aid Corporation ... and certain of its direct and indirect subsidiaries"),
 ("GNC", 1502034, "5400", "GNC Holdings, Inc.", "GNC HOLDINGS, INC.",
  "2020-06-23", "0001193125-20-177083", None,
  "On June 23, 2020, GNC Holdings, Inc. ... commenced voluntary Chapter 11 proceedings"),
 ("ASNA", 1498301, "5600", "Ascena Retail Group, Inc.", "Mahwah Bergen Retail Group, Inc.",
  "2020-07-23", "0001104659-20-085810", None,
  "On July 23, 2020 (the Petition Date), Ascena Retail Group, Inc. ... commenced voluntary cases"),
 ("TLRD", 884217, "5600", "Tailored Brands, Inc.", "TAILORED BRANDS INC",
  "2020-08-02", "0001104659-20-089351", None,
  "On August 2, 2020 (the Petition Date), Tailored Brands, Inc. ... commenced voluntary cases"),
 ("WLL", 1255474, "1311", "Whiting Petroleum Corporation", "Whiting Holdings LLC",
  "2020-04-01", "0001193125-20-093737", None,
  "On April 1, 2020, Whiting Petroleum Corporation ... commenced voluntary cases"),
 ("PRTY", 1592058, "5900", "Party City Holdco Inc.", "Party City Holdco Inc.",
  "2023-01-17", "0001193125-23-009847", None,
  "On January 17, 2023 (the Petition Date), the Borrowers, Holdings and each of the Subsidiary Guarantors ... filed voluntary petitions"),
 ("YELL", 716006, "4213", "Yellow Corporation", "Yellow Corp",
  "2023-08-06", "0001193125-23-204370", None,
  "On August 6, 2023 (the Petition Date), Yellow Corporation ... filed a voluntary petition"),
 ("DBD", 28823, "3578", "Diebold Nixdorf, Incorporated", "DIEBOLD NIXDORF, Inc",
  "2023-06-01", "0001193125-23-158463", None,
  "On June 1, 2023, the Debtors commenced the Chapter 11 Cases in the U.S. Bankruptcy Court"),
 ("REV", 887921, "2844", "Revlon, Inc.", "REVLON INC /DE/",
  "2022-06-15", "0001140361-22-023182", None,
  "On June 15, 2022 (the Petition Date), the Company and certain of its subsidiaries ... including Revlon Consumer Products Corporation"),
 ("BGG", 14195, "3510", "Briggs & Stratton Corporation", "BRIGGS & STRATTON CORP",
  "2020-07-20", "0000014195-20-000046", None,
  "On July 20, 2020, Briggs & Stratton Corporation ... filed voluntary petitions"),
 ("VAL", 314808, "1381", "Valaris plc", "Valaris Limited",
  "2020-08-19", "0001104659-20-096796", None,
  "On August 19, 2020 (the Petition Date), the Company and 89 of its subsidiaries ... filed voluntary petitions"),
 ("DNR", 945764, "1311", "Denbury Resources Inc.", "DENBURY INC.",
  "2020-07-30", "0000945764-20-000066", None,
  "On July 30, 2020, Denbury Resources Inc. ... filed petitions for voluntary relief"),
 ("XOG", 1655020, "1311", "Extraction Oil & Gas, Inc.", "Extraction Oil & Gas, Inc.",
  "2020-06-14", "0001104659-20-073184", None,
  "On June 14, 2020 (the Petition Date), Extraction Oil & Gas, Inc. ... filed voluntary petitions"),
]

# Candidates verified and REJECTED. Recorded because a rejection is evidence.
REJECTED = [
 ("WE", 1813756, "WeWork Inc.",
  "SIC 6512 (Operators of Nonresidential Buildings) falls inside the "
  "6000-6799 range docs/data-sources.md excludes from the universe. Admitting "
  "it would contradict the project's own scope rule. It is also exactly the "
  "balance-sheet shape that rule excludes: an office lessor whose liabilities "
  "are overwhelmingly operating leases."),
 ("HTZ-old", 1364479, "Hertz Global Holdings Inc (pre-2016 CIK)",
  "IDENTITY TRAP. This CIK is now HERC HOLDINGS INC — the equipment-rental "
  "business spun off in 2016, which KEPT the old CIK and did not fail. The "
  "car-rental business that filed Chapter 11 is on CIK 1657853. Using this CIK "
  "would place a surviving spinco in the failure cohort."),
 ("JCP-old", 77182, "J C Penney Corp Inc",
  "Wrong entity: the pre-2002 operating subsidiary. Two 10-Ks (1994, 1995), no "
  "Item 1.03 8-K, no XBRL. The public parent that filed in 2020 is CIK 1166126."),
 ("BBBY-wrong", 1130713, "Bed Bath & Beyond, Inc. (the NAME, not the filer)",
  "IDENTITY TRAP. CIK 1130713 is Overstock.com, which bought the Bed Bath & "
  "Beyond brand out of the 2023 bankruptcy auction and renamed ITSELF. It did "
  "not fail. The filer that failed is CIK 886158, now named "
  "20230930-DK-Butterfly-1, Inc."),
 ("WE-companies", 1533523, "WeWork Companies Inc/LLC",
  "No 10-K and no annual XBRL — nothing for the engine to read."),
]


def split_for(cases: list[dict]) -> None:
    """Stratified, deterministic, outcome-independent hold-out assignment.

    Stratify by SEC sector group, sort by CIK within each stratum, then
    alternate dev/holdout. **The rule uses no result of any kind**, so the
    split cannot have been chosen to flatter either version.

    Stated plainly: the V1 baseline grades were observed before this split was
    written, because admitting a case required running the engine to check it
    had usable data at all. What the hold-out protects against is **iterating
    on it during Phase C**, not ignorance of the baseline — and the brief
    requires the baseline to be recorded in Phase A regardless.
    """
    by_group: dict[str, list[dict]] = {}
    for c in cases:
        by_group.setdefault(c["sector_group"], []).append(c)
    for group in sorted(by_group):
        for i, c in enumerate(sorted(by_group[group], key=lambda c: c["cik"])):
            c["split"] = "dev" if i % 2 == 0 else "holdout"


def main() -> None:
    cases = []
    for (tick, cik, sic, name_then, name_now, event, accn, doc,
         sentence) in CASES:
        raw = json.loads((RAW / f"CIK{cik:010d}.json").read_text())["content"]
        cutoff = as_of_for_event(event)
        pit = filter_payload(raw, cutoff)
        (_s, _m, _c, _i, metrics, _t, scores, _st) = pipeline.analyse(pit)
        values = sum(1 for m in metrics.metrics
                     if m.data_status == "CALCULATED")
        last = max(scores, key=lambda s: s.period_end) if scores else None
        bare = accn.replace("-", "")
        url = (f"https://www.sec.gov/Archives/edgar/data/{cik}/{bare}/"
               f"{doc if doc else accn + '.txt'}")
        row = {
            "ticker": tick, "cik": cik, "sic": sic,
            "sector_group": SECTOR_GROUP[sic],
            "name_at_event": name_then, "name_now": name_now,
            "event": "Chapter 11 voluntary petition",
            "event_date": event,
            "source_form": "8-K Item 1.03 Bankruptcy or Receivership",
            "source_accession": accn,
            "source_url": url,
            "source_sentence": sentence,
            "pit_cutoff": cutoff,
            "pit_period_end": last.period_end if last else None,
            "pit_lead_days": ((date.fromisoformat(event)
                               - date.fromisoformat(last.period_end)).days
                              if last else None),
            "pit_categories_scored": last.categories_available if last else 0,
            "pit_metric_values": values,
            "admitted": bool(last
                             and last.categories_available >= MIN_CATEGORIES),
        }
        if not row["admitted"]:
            row["admission_note"] = (
                f"scores {row['pit_categories_scored']} of 5 categories at the "
                f"cutoff ({values} metric values in the whole point-in-time "
                f"history) — below the {MIN_CATEGORIES}-category bar. Retained "
                f"and reported as a COVERAGE failure, excluded from the "
                f"discrimination metrics.")
        cases.append(row)

    split_for(cases)

    lines = [
        "# A2 — external discrimination backtest: the failure cohort.",
        "#",
        "# GENERATED by benchmark/harness/build_a2_cases.py. Do not hand-edit:",
        "# every derived field is recomputed from the cached payload, and a",
        "# figure restated by hand is how this project has already lost a count",
        "# twice (D79, D71).",
        "#",
        "# Every event is a Chapter 11 voluntary petition reported by the filer",
        "# itself on an 8-K under Item 1.03. The petition date is read from the",
        "# DOCUMENT TEXT, never from the submissions index, which disagrees in",
        "# 8 of these 19 cases. `source_sentence` is the sentence it came from.",
        "#",
        f"# Admission bar: at least {MIN_CATEGORIES} of 5 scoring categories must",
        "# score at the point-in-time cutoff.",
        "",
        "min_categories: %d" % MIN_CATEGORIES,
        "lead_days: 365",
        "",
        "failures:",
    ]
    for c in cases:
        lines.append(f"  - ticker: {c['ticker']}")
        for k in ("cik", "sic", "sector_group", "name_at_event", "name_now",
                  "event", "event_date", "source_form", "source_accession",
                  "source_url", "pit_cutoff", "pit_period_end",
                  "pit_lead_days", "pit_categories_scored",
                  "pit_metric_values", "admitted", "split"):
            v = c[k]
            # Dates are quoted so YAML yields strings, not date objects: every
            # consumer compares them against ISO strings from the payload, and
            # a silently-typed date is a bug waiting for the first consumer
            # that does.
            if k in ("event_date", "pit_cutoff", "pit_period_end") and v:
                v = f'"{v}"'
            elif isinstance(v, str) and (":" in v or "," in v or "&" in v):
                v = f'"{v}"'
            lines.append(f"    {k}: {v}")
        lines.append(f"    source_sentence: >-")
        lines.append(f"      {c['source_sentence']}")
        if "admission_note" in c:
            lines.append("    admission_note: >-")
            lines.append(f"      {c['admission_note']}")
        lines.append("")
    lines.append("# Verified and REJECTED candidates. A rejection is evidence.")
    lines.append("rejected:")
    for tick, cik, name, why in REJECTED:
        lines.append(f"  - candidate: {tick}")
        lines.append(f"    cik: {cik}")
        lines.append(f'    name: "{name}"')
        lines.append("    why: >-")
        lines.append(f"      {why}")
        lines.append("")
    OUT.write_text("\n".join(lines))
    admitted = [c for c in cases if c["admitted"]]
    print(f"wrote {OUT}")
    print(f"  {len(cases)} verified cases, {len(admitted)} admitted, "
          f"{len(cases) - len(admitted)} coverage failures, "
          f"{len(REJECTED)} rejected candidates")
    from collections import Counter
    print(f"  split: {dict(Counter(c['split'] for c in admitted))}")
    print(f"  lead days: min {min(c['pit_lead_days'] for c in admitted)}, "
          f"max {max(c['pit_lead_days'] for c in admitted)}")


if __name__ == "__main__":
    main()
