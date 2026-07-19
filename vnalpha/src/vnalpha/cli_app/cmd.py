from __future__ import annotations

from typing import Optional, assert_never

import typer

from vnalpha.commands.models import CommandStatus
from vnalpha.core.logging import set_correlation_id
from vnalpha.observability.commands import command_lifecycle


def register(app: typer.Typer) -> None:
    @app.command("cmd")
    def cmd_runner(
        command: str = typer.Argument(
            ..., help="Slash command to run, e.g. '/scan VN30'"
        ),
        date: Optional[str] = typer.Option(
            None, "--date", help="Override date context (YYYY-MM-DD or 'today')."
        ),
    ) -> None:
        """Run a Phase 5.8 slash command in the research workspace.

        Examples:
            vnalpha cmd "/help"
            vnalpha cmd "/scan"
            vnalpha cmd "/explain FPT"
            vnalpha cmd "/filter score>=0.70"
            vnalpha cmd "/history --limit 20"
        """
        set_correlation_id()
        with command_lifecycle("cmd"):
            from vnalpha.commands.executor import CommandExecutor
            from vnalpha.commands.renderers.rich_renderer import render_result
            from vnalpha.core.text_safety import sanitize_text
            from vnalpha.warehouse.connection import get_connection
            from vnalpha.warehouse.migrations import run_migrations

            conn = None
            try:
                conn = get_connection()
                run_migrations(conn=conn)
                result = CommandExecutor(conn, surface="cli").execute(
                    command, date_override=date
                )

                try:
                    from rich.console import Console

                    render_result(result, console=Console())
                except ImportError:
                    typer.echo(sanitize_text(result.title))
                    if result.summary:
                        typer.echo(sanitize_text(result.summary))
            except Exception as exc:
                _capture_exception(exc)
                typer.echo("Command failed. Check logs and retry.", err=True)
                raise typer.Exit(code=1) from exc
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception as exc:
                        _capture_exception(exc)
                        typer.echo("Command failed. Check logs and retry.", err=True)
                        raise typer.Exit(code=1) from exc

            match result.status:
                case (
                    CommandStatus.SUCCESS
                    | CommandStatus.EMPTY_RESULT
                    | CommandStatus.PARTIAL
                ):
                    return
                case CommandStatus.FAILED | CommandStatus.VALIDATION_ERROR:
                    raise typer.Exit(code=1)
                case unreachable:
                    assert_never(unreachable)


def _capture_exception(exc: Exception) -> None:
    try:
        from vnalpha.observability.errors import capture_exception

        capture_exception(exc)
    except Exception:  # noqa: BLE001
        pass
