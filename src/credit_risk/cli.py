"""Command-line interface.

Commands are added phase by phase — see TODO.md.
"""

import typer

from credit_risk import __version__, config, ingest, pipeline
from credit_risk.metrics.ratios import METRICS, reason_kind
from credit_risk.scoring.engine import explain
from credit_risk.store import queries

app = typer.Typer(help="Credit risk analyser", no_args_is_help=True)


@app.callback()
def main() -> None:
    """Credit risk analyser. Run a subcommand — see --help."""


@app.command()
def version() -> None:
    """Print the version and confirm config files load."""
    typer.echo(f"credit-risk {__version__}")
    weights = config.thresholds()["weights"]
    typer.echo(f"scoring categories loaded: {', '.join(weights)}")
    typer.echo(f"tag map concepts loaded: {len(config.tag_map())}")


@app.command()
def fetch(
    ticker: str,
    force: bool = typer.Option(False, "--force", help="Bypass the cache and re-fetch."),
) -> None:
    """Fetch SEC companyfacts for TICKER and cache the raw JSON to data/raw/."""
    cik = ingest.ticker_to_cik(ticker)
    ingest.fetch_companyfacts(cik, force=force)
    typer.echo(f"{ticker.upper()} (CIK {cik}): cached to {ingest.default_cache_path(cik)}")


def _fmt(value, unit="USD"):
    if value is None:
        return "—"
    if unit == "ratio":
        return f"{value:,.2f}"
    return f"{value:,.0f}"


def _print_concept_chain(conn, cik, concept, end, indent, seen=None):
    """One concept and everything beneath it, down to tags and filings.

    Recursive because composites nest: net_debt is built from total_debt,
    which is itself built from reported concepts. Stopping at one level would
    show a CALCULATED number with no visible origin, which is the opposite of
    what this command exists for. `seen` guards against a cycle the schema
    should prevent but nothing enforces.
    """
    seen = seen or set()
    if (concept, end) in seen:
        return
    seen.add((concept, end))

    rows = queries.concept_chain(conn, cik, concept, end)
    if not rows:
        return
    head = rows[0]
    pad = " " * indent
    if head["data_status"] == "UNAVAILABLE":
        typer.echo(f"{pad}{concept:<24} {'UNAVAILABLE':>18}  {head['reason_code']}")
        return

    origin = head["source_tag"] or head["method"] or ""
    typer.echo(f"{pad}{concept:<24} {_fmt(head['value']):>18}  "
               f"{head['data_status']:<10} {origin}")
    if head["source_tag"] and head["accession"]:
        typer.echo(f"{pad}{'':24} {'':18}  {head['form']} {head['accession']} "
                   f"filed {head['filed']}")
    if head["detail"]:
        typer.echo(f"{pad}{'':24} {'':18}  ({head['detail']})")

    for input_concept in sorted({r["input_concept"] for r in rows
                                 if r["input_concept"]}):
        _print_concept_chain(conn, cik, input_concept, end, indent + 2, seen)


@app.command()
def metrics(
    ticker: str,
    period: str = typer.Option(None, "--period", help="One period end, YYYY-MM-DD."),
    all_periods: bool = typer.Option(False, "--all-periods",
                                     help="Every period, not just the latest."),
) -> None:
    """Compute the Task 11 ratios for TICKER and print each with its provenance.

    Runs the whole pipeline over the cached companyfacts into an in-memory
    database, then prints from that database — so what you see is the stored
    provenance chain, not in-memory values.
    """
    cik = ingest.ticker_to_cik(ticker)
    raw = pipeline.load_cached(cik)
    conn, _ = pipeline.analyse_and_store(raw)

    rows = queries.metrics_with_provenance(conn, cik)
    ends = sorted({r["period_end"] for r in rows})
    if period:
        if period not in ends:
            raise typer.BadParameter(
                f"{period} is not a period for {ticker.upper()}. "
                f"Available: {', '.join(ends)}"
            )
        ends = [period]
    elif not all_periods:
        ends = ends[-1:]

    verdicts = {r["period_end"]: r
                for r in queries.integrity_verdict_by_period(conn, cik)}

    typer.echo(f"\n{raw['entityName']} (CIK {cik}) — {len(ends)} period(s)")
    typer.echo("Deterministic engine output. Not a rating, not credit advice.\n")

    for end in ends:
        typer.echo(f"{'=' * 72}\nPeriod end {end}\n")
        for row in [r for r in rows if r["period_end"] == end]:
            if row["data_status"] == "UNAVAILABLE":
                kind = reason_kind(row["reason_code"])
                typer.echo(f"  {row['metric']:<22} UNAVAILABLE  "
                           f"{row['reason_code']} ({kind.lower()})")
                typer.echo("")
                continue
            typer.echo(f"  {row['metric']:<22} {_fmt(row['value'], 'ratio'):>10}  "
                       f"{row['data_status']}  {row['method']}")
            inputs = {r["input_concept"] for r in
                      queries.metric_provenance(conn, cik, end)
                      if r["metric"] == row["metric"]}
            for concept in sorted(inputs):
                _print_concept_chain(conn, cik, concept, end, indent=4)
            typer.echo("")
        v = verdicts.get(end)
        if v:
            typer.echo(f"  integrity: {v['verdict']} "
                       f"({v['checks_run']} checks run, {v['skipped']} skipped)")
        typer.echo("")


@app.command()
def score(
    ticker: str,
    period: str = typer.Option(None, "--period", help="One period end, YYYY-MM-DD."),
    all_periods: bool = typer.Option(False, "--all-periods",
                                     help="Every period, not just the latest."),
) -> None:
    """Score TICKER and print the explain output for each period.

    The cap line leads every period deliberately: capped grades are systematic
    rather than exceptional in the current company set, and a capped grade must
    never read as a judged one.
    """
    cik = ingest.ticker_to_cik(ticker)
    raw = pipeline.load_cached(cik)
    _, _, _, integrity, _, scores = pipeline.analyse(raw)

    by_period = {s.period_end: s for s in scores}
    ends = sorted(by_period)
    failed = sorted({r.period_end for r in integrity.results
                     if r.outcome == "FAIL"})
    if period:
        if period not in by_period:
            why = ("excluded: integrity FAIL" if period in failed
                   else "no score for that period")
            raise typer.BadParameter(
                f"{period}: {why}. Scored periods: {', '.join(ends) or 'none'}")
        ends = [period]
    elif not all_periods:
        ends = ends[-1:]

    typer.echo(f"\n{raw['entityName']} (CIK {cik})")
    if failed:
        typer.echo(f"Excluded by integrity FAIL: {', '.join(failed)}")
    typer.echo("")

    for end in ends:
        report = explain(by_period[end])
        typer.echo("=" * 72)
        typer.echo(f"Period end {end}")
        typer.echo(f"  {report['headline']}")
        typer.echo(f"  Total score {report['total_score']}/100\n")
        for cat in report["categories"]:
            if cat["points"] is None:
                typer.echo(f"  {cat['category']:22} ABSENT  "
                           f"({cat['absent_cause']}), weight {cat['weight']:g}")
            else:
                typer.echo(f"  {cat['category']:22} {cat['points']:5.2f}/10  "
                           f"weight {cat['weight']:<3g} contribution "
                           f"{cat['contribution']:5.2f}")
            for comp in cat["components"]:
                value = "—" if comp["value"] is None else f"{comp['value']:,.4g}"
                if comp["treatment"] == "scored":
                    detail = f"{comp['points']:>4.0f} pts  {comp['band']}"
                else:
                    detail = f"{comp['treatment']}  {comp['reason_code'] or ''}"
                typer.echo(f"      {comp['metric']:28} {value:>12}  {detail}")
        typer.echo("")
        typer.echo(f"  strongest: {', '.join(report['strongest']) or '—'}")
        typer.echo(f"  weakest:   {', '.join(report['weakest']) or '—'}")
        if report["positive_mitigants"]:
            typer.echo(f"  mitigants: {', '.join(report['positive_mitigants'])}")
        typer.echo("  top drivers (points lost vs a perfect score):")
        for d in report["top_drivers"]:
            typer.echo(f"      {d['metric']:28} {d['points_lost']:5.2f} "
                       f"({d['category']})")
        typer.echo(f"  {report['trend_note']}")
        typer.echo(f"\n  {report['disclaimer']}\n")


if __name__ == "__main__":
    app()
