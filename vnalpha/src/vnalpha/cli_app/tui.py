from __future__ import annotations

from typing import Optional

import typer

from vnalpha.core.logging import (
    LogSurface,
    configure_logging,
    get_logger,
    set_correlation_id,
)
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

        try:
            logging_result = configure_logging(surface=LogSurface.TUI)
            get_logger("vnalpha.cli.tui").info(
                "LOGGING_SURFACE_CONFIGURED",
                surface=logging_result.surface.value,
                file_enabled=logging_result.file_enabled,
                console_enabled=logging_result.console_enabled,
            )
            try:
                tui_app = VnAlphaApp(date=date, logging_warning=logging_result.error_id)
            except ValueError as exc:
                from vnalpha.core.text_safety import sanitize_error_summary

                typer.echo(f"Error: {sanitize_error_summary(exc)}", err=True)
                raise typer.Exit(code=1) from exc
            tui_app.run()
        except typer.Exit:
            raise
        except Exception as exc:
            try:
                from vnalpha.observability.errors import capture_exception

                capture_exception(exc)
            except Exception:  # noqa: BLE001
                pass
            typer.echo("TUI failed to start. Check logs and retry.", err=True)
            raise typer.Exit(code=1) from exc


def register(app: typer.Typer) -> None:
    app.command("tui")(tui)
