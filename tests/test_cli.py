"""CLI wiring tests.

The `fetch` command's own logic (caching, rate limiting, error handling) is
tested in tests/test_ingest_companyfacts.py and tests/test_ingest_tickers.py;
here we only check the command wires ticker_to_cik -> fetch_companyfacts
correctly and forwards --force.
"""

from typer.testing import CliRunner

from credit_risk import __version__, cli, config

runner = CliRunner()


def test_version_command_prints_version_and_proves_config_loads():
    """`credit-risk version` had no test at all (audit finding 14).

    The command is the project's smoke test — it fails if either config file is
    missing or malformed — so its own output is worth asserting. The concept
    count is compared against config rather than a literal on purpose: the
    literal lives in test_project_setup (finding 13), and what this test checks
    is that the CLI reports what config holds, not what that number is.
    """
    result = runner.invoke(cli.app, ["version"])

    assert result.exit_code == 0
    assert f"credit-risk {__version__}" in result.output
    for category in config.thresholds()["weights"]:
        assert category in result.output
    assert f"tag map concepts loaded: {len(config.tag_map())}" in result.output


def test_fetch_resolves_ticker_then_fetches_companyfacts(monkeypatch):
    received = {}

    def fake_ticker_to_cik(ticker, **kwargs):
        received["ticker"] = ticker
        return 320193

    def fake_fetch_companyfacts(cik, force=False, **kwargs):
        received["cik"] = cik
        received["force"] = force
        return {}

    monkeypatch.setattr(cli.ingest, "ticker_to_cik", fake_ticker_to_cik)
    monkeypatch.setattr(cli.ingest, "fetch_companyfacts", fake_fetch_companyfacts)

    result = runner.invoke(cli.app, ["fetch", "AAPL"])

    assert result.exit_code == 0
    assert received == {"ticker": "AAPL", "cik": 320193, "force": False}
    assert "320193" in result.stdout


def test_fetch_force_flag_is_forwarded(monkeypatch):
    received = {}
    monkeypatch.setattr(cli.ingest, "ticker_to_cik", lambda ticker, **kw: 320193)
    monkeypatch.setattr(
        cli.ingest,
        "fetch_companyfacts",
        lambda cik, force=False, **kw: received.update(force=force) or {},
    )

    result = runner.invoke(cli.app, ["fetch", "AAPL", "--force"])

    assert result.exit_code == 0
    assert received["force"] is True


def test_fetch_unknown_ticker_fails_clearly(monkeypatch):
    def fake_ticker_to_cik(ticker, **kwargs):
        raise ValueError(f"Unknown ticker: {ticker}")

    monkeypatch.setattr(cli.ingest, "ticker_to_cik", fake_ticker_to_cik)

    result = runner.invoke(cli.app, ["fetch", "NOPE"])

    assert result.exit_code != 0
