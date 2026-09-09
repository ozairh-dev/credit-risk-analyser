"""Task 3: fetch_company_tickers caching and ticker_to_cik lookup."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from credit_risk import env
from credit_risk.ingest import tickers

SAMPLE = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"},
}


@pytest.fixture(autouse=True)
def sec_user_agent(monkeypatch):
    monkeypatch.setenv("SEC_USER_AGENT", "credit-risk-tests test@example.com")


def write_cache(path, content, fetched_at=None):
    fetched_at = fetched_at or datetime.now(timezone.utc)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"fetched_at": fetched_at.isoformat(), "content": content}))


def test_fetch_sends_user_agent_and_writes_cache(requests_mock, tmp_path):
    cache_path = tmp_path / "company_tickers.json"
    requests_mock.get(tickers.TICKERS_URL, json=SAMPLE)

    result = tickers.fetch_company_tickers(cache_path=cache_path)

    assert result == SAMPLE
    assert requests_mock.call_count == 1
    assert requests_mock.last_request.headers["User-Agent"] == "credit-risk-tests test@example.com"
    cached = json.loads(cache_path.read_text())
    assert cached["content"] == SAMPLE
    assert "fetched_at" in cached


def test_fetch_uses_cache_within_24h(requests_mock, tmp_path):
    cache_path = tmp_path / "company_tickers.json"
    write_cache(cache_path, SAMPLE, fetched_at=datetime.now(timezone.utc) - timedelta(hours=1))

    result = tickers.fetch_company_tickers(cache_path=cache_path)

    assert result == SAMPLE
    assert requests_mock.call_count == 0


def test_fetch_refetches_stale_cache(requests_mock, tmp_path):
    cache_path = tmp_path / "company_tickers.json"
    stale = {"0": {"cik_str": 1, "ticker": "OLD", "title": "Old Corp"}}
    write_cache(cache_path, stale, fetched_at=datetime.now(timezone.utc) - timedelta(hours=25))
    requests_mock.get(tickers.TICKERS_URL, json=SAMPLE)

    result = tickers.fetch_company_tickers(cache_path=cache_path)

    assert result == SAMPLE
    assert requests_mock.call_count == 1


def test_force_refetches_even_if_fresh(requests_mock, tmp_path):
    cache_path = tmp_path / "company_tickers.json"
    write_cache(cache_path, {"0": {"cik_str": 1, "ticker": "OLD", "title": "Old Corp"}})
    requests_mock.get(tickers.TICKERS_URL, json=SAMPLE)

    result = tickers.fetch_company_tickers(force=True, cache_path=cache_path)

    assert result == SAMPLE
    assert requests_mock.call_count == 1


def test_ticker_to_cik_is_case_insensitive(tmp_path):
    cache_path = tmp_path / "company_tickers.json"
    write_cache(cache_path, SAMPLE)

    assert tickers.ticker_to_cik("aapl", cache_path=cache_path) == 320193
    assert tickers.ticker_to_cik("MSFT", cache_path=cache_path) == 789019


def test_ticker_to_cik_unknown_raises(tmp_path):
    cache_path = tmp_path / "company_tickers.json"
    write_cache(cache_path, SAMPLE)

    with pytest.raises(ValueError, match="NOPE"):
        tickers.ticker_to_cik("NOPE", cache_path=cache_path)
