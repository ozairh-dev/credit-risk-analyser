"""Source a bankruptcy/default event from EDGAR itself, not from a news article.

A Chapter 11 petition is reported to the SEC on an 8-K under **Item 1.03,
"Bankruptcy or Receivership"**. The submissions endpoint lists every filing a
registrant has made with its form type, filing date, accession and — for 8-Ks —
the item numbers. So the event, its date and a citable public source all come
from the same primary record.

Why this rather than a news source: it is the filer's own report to the
regulator, it is free, it is in the public domain like the rest of the data
(D3), and the accession makes it checkable by anyone. A headline is neither
primary nor stable.

This is benchmark tooling. It touches no engine module and adds nothing to
`src/`.
"""

import json
import time
import urllib.request

from credit_risk import env

SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik:010d}.json"

# 8-K item numbers that report a credit event.
BANKRUPTCY_ITEM = "1.03"      # Bankruptcy or Receivership
DEFAULT_ITEM = "2.04"         # Triggering events that accelerate an obligation
DELISTING_ITEM = "3.01"       # Notice of delisting / failure to satisfy a rule


def fetch_submissions(cik: int, pause: float = 0.15) -> dict:
    """The registrant's filing index. Same UA and rate-limit discipline as
    `ingest/companyfacts.py`, which this deliberately mirrors rather than
    imports — that module is scoped to companyfacts."""
    request = urllib.request.Request(
        SUBMISSIONS.format(cik=cik),
        headers={"User-Agent": env.sec_user_agent()},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read())
    time.sleep(pause)
    return payload


def recent_filings(subs: dict) -> list[dict]:
    """Flatten the submissions' column-oriented `recent` block into rows."""
    recent = subs["filings"]["recent"]
    keys = ("form", "filingDate", "accessionNumber", "items",
            "primaryDocument", "reportDate")
    n = len(recent["form"])
    return [{k: recent.get(k, [None] * n)[i] for k in keys} for i in range(n)]


def older_filings(subs: dict) -> list[dict]:
    """The paged-out older filings, which is where a 2020 8-K will sit for a
    registrant that has filed since. Without this the search silently sees only
    the last ~1,000 filings — an absence that would look like 'no event'."""
    rows = []
    for extra in subs["filings"].get("files", []):
        request = urllib.request.Request(
            f"https://data.sec.gov/submissions/{extra['name']}",
            headers={"User-Agent": env.sec_user_agent()},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            block = json.loads(response.read())
        time.sleep(0.15)
        n = len(block["form"])
        keys = ("form", "filingDate", "accessionNumber", "items",
                "primaryDocument", "reportDate")
        rows += [{k: block.get(k, [None] * n)[i] for k in keys}
                 for i in range(n)]
    return rows


def all_filings(cik: int) -> tuple[dict, list[dict]]:
    subs = fetch_submissions(cik)
    return subs, recent_filings(subs) + older_filings(subs)


def credit_events(filings: list[dict], item: str = BANKRUPTCY_ITEM) -> list[dict]:
    """Every 8-K reporting `item`, oldest first."""
    hits = [f for f in filings
            if f["form"] and f["form"].startswith("8-K")
            and f["items"] and item in f["items"]]
    return sorted(hits, key=lambda f: f["filingDate"])


def annual_reports(filings: list[dict]) -> list[dict]:
    """10-K and 10-K/A filings, oldest first — the point-in-time universe."""
    hits = [f for f in filings
            if f["form"] in ("10-K", "10-K/A", "10-KT")]
    return sorted(hits, key=lambda f: f["filingDate"])


def filing_url(cik: int, accession: str, document: str | None = None) -> str:
    bare = accession.replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{bare}"
    return f"{base}/{document}" if document else f"{base}/"
