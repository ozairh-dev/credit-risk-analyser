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


# ============ the metrics command (pre-Phase-6 audit finding 5) ============

import json                                                    # noqa: E402

import pytest                                                  # noqa: E402

from credit_risk import pipeline                               # noqa: E402

CCL = 815097
CACHED_CCL = config.RAW_DIR / f"CIK{CCL:010d}.json"


@pytest.mark.skipif(not CACHED_CCL.exists(),
                    reason="no cached companyfacts in data/raw/ (gitignored)")
def test_metrics_command_prints_a_ratio_with_its_provenance(monkeypatch):
    """The Task 11 deliverable, asserted rather than eyeballed.

    The recursion bug found during Task 11 — the chain stopping one level
    short, so a CALCULATED number appeared with no visible origin — was caught
    by eye. This is the test that would have caught it: the output must reach
    a source tag and a filing accession, not merely name the composite.
    """
    monkeypatch.setattr(cli.ingest, "ticker_to_cik", lambda ticker, **kw: CCL)
    result = runner.invoke(cli.app, ["metrics", "CCL", "--period", "2019-11-30"])

    assert result.exit_code == 0, result.output
    assert "Carnival" in result.output
    assert "2019-11-30" in result.output
    # the value, hand-recomputed in Task 11: ebit 3,276 / interest 206
    assert "ebit_interest_cover" in result.output
    assert "15.90" in result.output
    # the chain must reach a reported tag and the filing behind it
    assert "OperatingIncomeLoss" in result.output
    assert "10-K" in result.output
    assert "0000815097-20-000003" in result.output
    # and the disclaimer the methodology requires on user-facing output
    assert "Not a rating" in result.output


@pytest.mark.skipif(not CACHED_CCL.exists(), reason="no cached companyfacts")
def test_metrics_command_labels_an_unavailable_ratio_with_its_kind(monkeypatch):
    """A refusal must show the reason AND the kind — the kind is what Phase 6
    acts on, and a reader cannot infer it from the code alone (D41a)."""
    monkeypatch.setattr(cli.ingest, "ticker_to_cik", lambda ticker, **kw: CCL)
    result = runner.invoke(cli.app, ["metrics", "CCL", "--period", "2020-11-30"])

    assert result.exit_code == 0, result.output
    assert "UNAVAILABLE" in result.output
    assert "NEGATIVE_EBITDA" in result.output
    assert "(evidence)" in result.output          # not a data gap


@pytest.mark.skipif(not CACHED_CCL.exists(), reason="no cached companyfacts")
def test_metrics_command_rejects_an_unknown_period(monkeypatch):
    monkeypatch.setattr(cli.ingest, "ticker_to_cik", lambda ticker, **kw: CCL)
    result = runner.invoke(cli.app, ["metrics", "CCL", "--period", "1999-01-01"])
    assert result.exit_code != 0
    assert "not a period" in result.output


def test_load_cached_names_the_fetch_command_when_nothing_is_cached(tmp_path, monkeypatch):
    """The error a first-time user hits must say what to run next."""
    monkeypatch.setattr(config, "RAW_DIR", tmp_path)
    with pytest.raises(FileNotFoundError, match="credit-risk fetch"):
        pipeline.load_cached(999999)


# ==== score, stress, export-evidence, validate-memo (D81) ====
#
# These four commands shipped with no test at all, which is how `score` reached
# v1 raising ValueError on its first line. A command that is only ever run by
# hand is a command whose wiring nothing checks: the suite was green throughout.
# Every expected value below was read off the real CCL run before it was pinned
# (CLAUDE.md rule 14), not copied from what the code happened to emit.


@pytest.mark.skipif(not CACHED_CCL.exists(), reason="no cached companyfacts")
def test_score_command_prints_the_explain_block(monkeypatch):
    """The D81 regression test, covering both wiring faults.

    `score` unpacked six names from pipeline.analyse()'s eight-tuple, and then
    read a `trend_note` key explain() has never returned. Each raised before any
    output reached the user, so this test fails on either fault returning.
    """
    monkeypatch.setattr(cli.ingest, "ticker_to_cik", lambda ticker, **kw: CCL)
    result = runner.invoke(cli.app, ["score", "CCL", "--period", "2019-11-30"])

    assert result.exit_code == 0, result.output
    assert "Carnival" in result.output
    assert "Grade 4" in result.output
    assert "Total score 45.0/100" in result.output

    # The five contributions must be present AND sum to the printed total:
    # 17.50 + 16.00 + 0.00 + 4.00 + 7.50 = 45.0, hand-checked against the
    # weights in config/thresholds.yaml.
    for contribution in ("contribution 17.50", "contribution 16.00",
                         "contribution  0.00", "contribution  4.00",
                         "contribution  7.50"):
        assert contribution in result.output

    # Same ebit_interest_cover the metrics command reports for this period
    # (ebit 3,276 / interest 206), so the two commands cannot silently diverge.
    assert "15.9" in result.output

    # The line that raised KeyError: 'trend_note'. It now renders explain()'s
    # deteriorating_metrics, which is the only trend data explain() returns.
    assert "deteriorating: ebit_interest_cover, ebitda_margin_trend" in result.output
    assert "Not a credit rating" in result.output


@pytest.mark.skipif(not CACHED_CCL.exists(), reason="no cached companyfacts")
def test_score_command_rejects_an_unknown_period(monkeypatch):
    """A bad --period must name the periods that do score, not just refuse."""
    monkeypatch.setattr(cli.ingest, "ticker_to_cik", lambda ticker, **kw: CCL)
    result = runner.invoke(cli.app, ["score", "CCL", "--period", "1999-01-01"])

    assert result.exit_code != 0
    assert "no score for that period" in " ".join(result.output.split())
    assert "2019-11-30" in result.output


@pytest.mark.skipif(not CACHED_CCL.exists(), reason="no cached companyfacts")
def test_stress_command_prints_base_stressed_and_drivers(monkeypatch):
    """The stressed run must carry the same base score the score command gives.

    Both read the same eight-tuple; pinning the base here is what would catch
    `stress` drifting onto a different period's score the way `score` drifted
    onto the wrong tuple positions.
    """
    monkeypatch.setattr(cli.ingest, "ticker_to_cik", lambda ticker, **kw: CCL)
    result = runner.invoke(cli.app, ["stress", "CCL", "--period", "2019-11-30",
                                     "--scenario", "severe"])

    assert result.exit_code == 0, result.output
    assert "grade 4 (base, 45.0) -> 5 (stressed, 34.5)" in result.output
    assert "driver attribution" in result.output
    # D54's assumption must stay visible in the output, not just in the code.
    assert "floating_share = 1.0 (ASSUMED, D54)" in result.output


@pytest.mark.skipif(not CACHED_CCL.exists(), reason="no cached companyfacts")
def test_export_evidence_writes_a_pack_with_all_nine_sections(tmp_path, monkeypatch):
    """A pack missing a section is a pack a memo can cite around."""
    monkeypatch.setattr(cli.ingest, "ticker_to_cik", lambda ticker, **kw: CCL)
    result = runner.invoke(cli.app, ["export-evidence", "CCL", "--period",
                                     "2019-11-30", "--out", str(tmp_path)])

    assert result.exit_code == 0, result.output
    path = tmp_path / "CCL_2019-11-30.md"
    assert path.exists()
    pack = path.read_text(encoding="utf-8")
    for heading in ("## 1. Company and filing",
                    "## 2. Grade",
                    "## 3. Reported concepts",
                    "## 4. Calculated values",
                    "## 5. Trends and early warnings",
                    "## 6. Stress scenarios",
                    "## 7. Data quality and integrity",
                    "## 8. Assumption register",
                    "## 9. What this pack does not contain"):
        assert heading in pack, heading
    assert "EXCLUSIVE basis" in result.output


@pytest.mark.skipif(not CACHED_CCL.exists(), reason="no cached companyfacts")
def test_validate_memo_fails_a_reviewed_memo_holding_an_unverified_figure(
        tmp_path, monkeypatch):
    """REVIEWED is the claim the exit code defends; 99999 is not in the pack."""
    monkeypatch.setattr(cli.ingest, "ticker_to_cik", lambda ticker, **kw: CCL)
    runner.invoke(cli.app, ["export-evidence", "CCL", "--period", "2019-11-30",
                            "--out", str(tmp_path)])
    memo = tmp_path / "memo.md"
    memo.write_text(
        "# Credit memo — Carnival Corporation Ltd. — 2019-11-30\n\n"
        "Status: REVIEWED\n\n"
        "Net debt to EBITDA is 2.0206x and interest cover is 15.9029x.\n"
        "Revenue reached 99999 million in the period.\n",
        encoding="utf-8")

    result = runner.invoke(cli.app, ["validate-memo", str(memo),
                                     str(tmp_path / "CCL_2019-11-30.md")])

    assert result.exit_code == 1, result.output
    assert "99999" in result.output
    assert "A CLEAN VALIDATION IS NOT A CLEAN MEMO" in result.output


@pytest.mark.skipif(not CACHED_CCL.exists(), reason="no cached companyfacts")
def test_validate_memo_passes_the_same_memo_when_it_does_not_claim_reviewed(
        tmp_path, monkeypatch):
    """The gate is on the REVIEWED claim, not on the figure.

    An unverified figure in a draft is a finding to report; the same figure
    under Status: REVIEWED is a claim the tool must refuse. Identical memo body
    to the test above, so the exit code can only be turning on that one line.
    """
    monkeypatch.setattr(cli.ingest, "ticker_to_cik", lambda ticker, **kw: CCL)
    runner.invoke(cli.app, ["export-evidence", "CCL", "--period", "2019-11-30",
                            "--out", str(tmp_path)])
    memo = tmp_path / "memo.md"
    memo.write_text(
        "# Credit memo — Carnival Corporation Ltd. — 2019-11-30\n\n"
        "Status: DRAFT\n\n"
        "Net debt to EBITDA is 2.0206x and interest cover is 15.9029x.\n"
        "Revenue reached 99999 million in the period.\n",
        encoding="utf-8")

    result = runner.invoke(cli.app, ["validate-memo", str(memo),
                                     str(tmp_path / "CCL_2019-11-30.md")])

    assert result.exit_code == 0, result.output
    assert "99999" in result.output
