"""Ticker -> CIK lookup (docs/data-sources.md, TODO Task 3).

SEC publishes one JSON file mapping every ticker to a CIK. We cache it whole
and look tickers up in memory rather than hitting the network per company.
"""

import requests

from credit_risk import config, env
from credit_risk.ingest import cache

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
DEFAULT_CACHE_PATH = config.RAW_DIR / "company_tickers.json"


def fetch_company_tickers(force: bool = False, cache_path=None) -> dict:
    """Return the raw ticker->company map, from cache if <24h old.

    Keyed by an arbitrary string index, e.g. {"0": {"cik_str": 320193,
    "ticker": "AAPL", "title": "Apple Inc."}, ...} — this is SEC's format,
    unchanged.
    """
    cache_path = cache_path or DEFAULT_CACHE_PATH

    if not force:
        cached = cache.read_cache(cache_path)
        if cached is not None:
            return cached

    response = requests.get(
        TICKERS_URL,
        headers={"User-Agent": env.sec_user_agent()},
        timeout=30,
    )
    response.raise_for_status()
    content = response.json()
    cache.write_cache(cache_path, content)
    return content


def ticker_to_cik(ticker: str, force: bool = False, cache_path=None) -> int:
    """Look up a ticker's CIK (as an int; zero-pad to 10 digits at the URL-building step)."""
    tickers = fetch_company_tickers(force=force, cache_path=cache_path)
    ticker = ticker.upper()
    for row in tickers.values():
        if row["ticker"].upper() == ticker:
            return row["cik_str"]
    raise ValueError(f"Unknown ticker: {ticker}")
