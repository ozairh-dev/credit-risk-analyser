"""companyfacts fetcher (docs/data-sources.md, TODO Task 4).

Fetches every XBRL fact SEC has ever received for one company. Cached to
data/raw/CIK{cik:010d}.json, reusing the same cache module and staleness
rule (config/ingestion.yaml) as ingest/tickers.py.
"""

import time

import requests

from credit_risk import config, env
from credit_risk.ingest import cache

COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
REQUEST_INTERVAL = 0.12  # seconds between live requests — keeps us under 10 req/s


def default_cache_path(cik: int):
    return config.RAW_DIR / f"CIK{cik:010d}.json"


def fetch_companyfacts(cik: int, force: bool = False, cache_path=None) -> dict:
    """Return the raw companyfacts JSON for `cik`, from cache if fresh.

    Raises RuntimeError if SEC_USER_AGENT isn't set — no request is ever sent
    without one — and a clear RuntimeError, wrapping the original HTTP error,
    if SEC returns a non-200 (e.g. an unknown or malformed CIK).
    """
    cache_path = cache_path or default_cache_path(cik)

    if not force:
        cached = cache.read_cache(cache_path)
        if cached is not None:
            return cached

    response = requests.get(
        COMPANYFACTS_URL.format(cik=cik),
        headers={"User-Agent": env.sec_user_agent()},
        timeout=30,
    )
    time.sleep(REQUEST_INTERVAL)

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise RuntimeError(
            f"SEC companyfacts request for CIK {cik:010d} failed: "
            f"{response.status_code} {response.reason}. Check the CIK is correct."
        ) from exc

    content = response.json()
    cache.write_cache(cache_path, content)
    return content
