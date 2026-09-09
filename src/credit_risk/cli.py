"""Command-line interface.

Commands are added phase by phase — see TODO.md. Nothing here does real
work yet beyond confirming the project and its configuration load.
"""

import typer

from credit_risk import __version__, config

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


if __name__ == "__main__":
    app()
