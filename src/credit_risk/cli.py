"""Command-line interface.

Commands are added phase by phase — see TODO.md.
"""

import typer

from credit_risk import __version__, config, ingest

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


if __name__ == "__main__":
    app()
