"""Command-line interface.

Commands are added phase by phase — see TODO.md.
"""

import typer

from credit_risk import __version__, config, ingest, pipeline
from credit_risk.metrics.ratios import METRICS, reason_kind
from credit_risk.scoring.engine import explain
from credit_risk.stress import engine as stress_engine
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


@app.command()
def stress(
    ticker: str,
    period: str = typer.Option(None, "--period", help="One period end, YYYY-MM-DD."),
    scenario: str = typer.Option("severe", "--scenario",
                                 help="base | moderate | severe"),
    grid: bool = typer.Option(False, "--grid",
                              help="Also print the sensitivity grid."),
) -> None:
    """Stress TICKER and print base vs stressed with driver attribution.

    The assumptions block is not decoration: five of its lines are output
    duties recorded as decisions before this command existed.
    """
    cik = ingest.ticker_to_cik(ticker)
    raw = pipeline.load_cached(cik)
    _, mapping, composites, _, metrics, trends, _, runs = pipeline.analyse(raw)

    by = {(r.period_end, r.scenario): r for r in runs}
    periods = sorted({p for p, _ in by})
    if not periods:
        typer.echo(f"\n{raw['entityName']} cannot be stress tested: no period "
                   f"resolves both revenue and EBITDA.")
        raise typer.Exit(0)
    end = period or periods[-1]
    run = by.get((end, scenario))
    if run is None:
        raise typer.BadParameter(
            f"no {scenario} run for {end}. Stressable periods: "
            f"{', '.join(periods)}")

    typer.echo(f"\n{raw['entityName']} (CIK {cik}) — {end} — {scenario}")
    typer.echo(f"  grade {run.base_grade} (base, {run.base_score:.1f}) -> "
               f"{run.stressed_grade} (stressed, {run.stressed_score:.1f})\n")
    typer.echo(f"  {'metric':26} {'base':>12} {'stressed':>12} {'change':>12}")
    for metric, (b, s_, c, status, reason) in sorted(run.results.items()):
        if status == "UNAVAILABLE":
            typer.echo(f"  {metric:26} {b if b is None else f'{b:12.4f}'}"
                       f" {'UNAVAILABLE':>12}  {reason}")
        else:
            typer.echo(f"  {metric:26} "
                       f"{'—' if b is None else f'{b:12.4f}'} {s_:12.4f} "
                       f"{'—' if c is None else f'{c:+12.4f}'}")

    typer.echo("\n  driver attribution (each shock alone against base):")
    shocks = sorted({sh for sh, _ in run.drivers})
    for shock in shocks:
        typer.echo(f"    {shock}")
        for (sh, metric), change in sorted(run.drivers.items()):
            if sh == shock and metric in ("net_debt_to_ebitda",
                                          "ebit_interest_cover", "fcf_margin"):
                typer.echo(f"      {metric:24} {change:+.4f}")
    typer.echo("    (drivers do not sum to the combined run: the propagation "
               "is multiplicative and tax is floored)")

    typer.echo("\n  assumptions and simplifications:")
    for line in run.assumptions:
        typer.echo(f"    - {line}")

    if grid:
        series = {}
        for c in mapping.concepts:
            series.setdefault(c.end, {})[c.concept] = c.value
        for c in composites:
            if c.data_status == "CALCULATED":
                series.setdefault(c.end, {})[c.concept] = c.value
        base_metrics = {m.metric: m for m in metrics.metrics if m.end == end}
        tv = {t.metric: t.verdict for t in trends.trends if t.period_end == end}
        cells = stress_engine.sensitivity_grid(end, series[end], base_metrics, tv)
        typer.echo("\n  sensitivity grid (revenue x margin shock) — "
                   "net_debt_to_ebitda / grade:")
        margins = sorted({c["margin_shock"] for c in cells})
        typer.echo("      rev\\mar " + "".join(f"{m:>12.0%}" for m in margins))
        for rev in sorted({c["revenue_shock"] for c in cells}, reverse=True):
            row = [next(c for c in cells if c["revenue_shock"] == rev
                        and c["margin_shock"] == m) for m in margins]
            cells_txt = "".join(
                f"{'—/—':>12}" if c["net_debt_to_ebitda"] is None
                else f"{c['net_debt_to_ebitda']:8.2f}/{c['grade']}" .rjust(12)
                for c in row)
            typer.echo(f"      {rev:>7.0%} {cells_txt}")

    typer.echo("\n  Internal analytical grade for this project. Not a credit "
               "rating.\n")


@app.command("export-evidence")
def export_evidence(
    ticker: str,
    period: str = typer.Option(None, "--period", help="Period end, YYYY-MM-DD."),
    out: str = typer.Option("evidence", "--out", help="Output directory."),
) -> None:
    """Write the evidence pack for TICKER — the exclusive basis for a memo."""
    from pathlib import Path
    from credit_risk.export.evidence import build_pack

    cik = ingest.ticker_to_cik(ticker)
    raw = pipeline.load_cached(cik)
    analysis = pipeline.analyse(raw)
    ends = sorted({c.end for c in analysis[1].concepts})
    if period and period not in ends:
        raise typer.BadParameter(
            f"{period} is not a period for {ticker.upper()}. "
            f"Available: {', '.join(ends[-6:])}")
    end = period or ends[-1]
    pack = build_pack(raw, analysis, end, ticker.upper())
    directory = Path(out)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{ticker.upper()}_{end}.md"
    path.write_text(pack, encoding="utf-8")
    typer.echo(f"Evidence pack written to {path}")
    typer.echo(f"  {len(pack.splitlines())} lines. This is the COMPLETE and "
               f"EXCLUSIVE basis for any memo written from it.")
    typer.echo(f"  Next: paste it with prompts/credit_memo.md, then run "
               f"`credit-risk validate-memo <memo> {path}`")


@app.command("validate-memo")
def validate_memo(memo: str, pack: str) -> None:
    """Check a memo against the evidence pack it was written from."""
    from pathlib import Path
    from credit_risk.export.validator import render, validate

    memo_text = Path(memo).read_text(encoding="utf-8")
    pack_text = Path(pack).read_text(encoding="utf-8")
    report = validate(memo_text, pack_text)
    typer.echo(render(report))
    if report.reviewed_claimed and not report.may_be_reviewed:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
