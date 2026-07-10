from __future__ import annotations

from typing import Optional

import typer

from vnalpha.core.logging import set_correlation_id
from vnalpha.observability.commands import command_lifecycle


def tui(
    date: Optional[str] = typer.Option(
        None, "--date", help="Reference date (YYYY-MM-DD). Default: today."
    ),
) -> None:
    """Launch the interactive research TUI."""
    set_correlation_id()
    with command_lifecycle("tui"):
        try:
            from vnalpha.tui.app import VnAlphaApp
        except ImportError as err:
            typer.echo(
                "Error: 'textual' is required for the TUI. Install it with: pip install textual",
                err=True,
            )
            raise typer.Exit(code=1) from err

        VnAlphaApp(date=date).run()


def register(app: typer.Typer) -> None:
    app.command("tui")(tui)
