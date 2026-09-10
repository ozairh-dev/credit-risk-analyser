"""Task 4: fetch_companyfacts caching, rate limiting and error wrapping."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from credit_risk import env
from credit_risk.ingest import companyfacts

CIK = 320193
URL = companyfacts.COMPANYFACTS_URL.format(cik=CIK)
SAMPLE = {"cik": CIK, "entityName": "Apple Inc.", "facts": {"us-gaap": {}}}


@pytest.fixture(autouse=True)
def sec_user_agent(monkeypatch):
    monkeypatch.setenv("SEC_USER_AGENT", "credit-risk-tests test@example.com")


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Record sleep calls instead of actually waiting during tests."""
    calls = []
    monkeypatch.setattr(companyfacts.time, "sleep", lambda seconds: calls.append(seconds))
    return calls


def write_cache(path, content, fetched_at=None):
    fetched_at = fetched_at or datetime.now(timezone.utc)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"fetched_at": fetched_at.isoformat(), "content": content}))


def test_fetch_sends_user_agent_and_writes_cache(requests_mock, tmp_path):
    cache_path = tmp_path / "CIK0000320193.json"
    requests_mock.get(URL, json=SAMPLE)

    result = companyfacts.fetch_companyfacts(CIK, cache_path=cache_path)

    assert result == SAMPLE
    assert requests_mock.call_count == 1
    assert requests_mock.last_request.headers["User-Agent"] == "credit-risk-tests test@example.com"
    cached = json.loads(cache_path.read_text())
    assert cached["content"] == SAMPLE
    assert "fetched_at" in cached


def test_fetch_uses_cache_within_max_age(requests_mock, tmp_path):
    cache_path = tmp_path / "CIK0000320193.json"
    write_cache(cache_path, SAMPLE, fetched_at=datetime.now(timezone.utc) - timedelta(hours=1))

    result = companyfacts.fetch_companyfacts(CIK, cache_path=cache_path)

    assert result == SAMPLE
    assert requests_mock.call_count == 0


def test_fetch_refetches_stale_cache(requests_mock, tmp_path):
    cache_path = tmp_path / "CIK0000320193.json"
    stale = {"cik": CIK, "entityName": "Old Apple Inc."}
    write_cache(cache_path, stale, fetched_at=datetime.now(timezone.utc) - timedelta(hours=25))
    requests_mock.get(URL, json=SAMPLE)

    result = companyfacts.fetch_companyfacts(CIK, cache_path=cache_path)

    assert result == SAMPLE
    assert requests_mock.call_count == 1


def test_force_refetches_even_if_fresh(requests_mock, tmp_path):
    cache_path = tmp_path / "CIK0000320193.json"
    write_cache(cache_path, {"cik": CIK, "entityName": "Old Apple Inc."})
    requests_mock.get(URL, json=SAMPLE)

    result = companyfacts.fetch_companyfacts(CIK, force=True, cache_path=cache_path)

    assert result == SAMPLE
    assert requests_mock.call_count == 1


def test_sleeps_after_a_live_fetch(requests_mock, tmp_path, no_sleep):
    cache_path = tmp_path / "CIK0000320193.json"
    requests_mock.get(URL, json=SAMPLE)

    companyfacts.fetch_companyfacts(CIK, cache_path=cache_path)

    assert no_sleep == [companyfacts.REQUEST_INTERVAL]


def test_does_not_sleep_on_cache_hit(requests_mock, tmp_path, no_sleep):
    cache_path = tmp_path / "CIK0000320193.json"
    write_cache(cache_path, SAMPLE)

    companyfacts.fetch_companyfacts(CIK, cache_path=cache_path)

    assert no_sleep == []
    assert requests_mock.call_count == 0


def test_non_200_response_raises_clear_error_and_does_not_cache(requests_mock, tmp_path):
    cache_path = tmp_path / "CIK0000320193.json"
    requests_mock.get(URL, status_code=404, reason="Not Found")

    with pytest.raises(RuntimeError, match="320193"):
        companyfacts.fetch_companyfacts(CIK, cache_path=cache_path)

    assert not cache_path.exists()


def test_missing_user_agent_raises_before_any_request(requests_mock, monkeypatch, tmp_path):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    monkeypatch.setattr(env, "ENV_FILE", tmp_path / "does-not-exist.env")
    cache_path = tmp_path / "CIK0000320193.json"

    with pytest.raises(RuntimeError, match="SEC_USER_AGENT"):
        companyfacts.fetch_companyfacts(CIK, cache_path=cache_path)

    assert requests_mock.call_count == 0


def test_default_cache_path_is_zero_padded():
    assert companyfacts.default_cache_path(320193).name == "CIK0000320193.json"
