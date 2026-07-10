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
            from vnalpha.warehouse.connection import get_connection
            from vnalpha.warehouse.migrations import run_migrations

            conn = get_connection()
            run_migrations(conn=conn)
            result = CommandExecutor(conn, surface="cli").execute(
                command, date_override=date
            )

            try:
                from rich.console import Console

                render_result(result, console=Console())
            except ImportError:
                typer.echo(result.title)
                if result.summary:
                    typer.echo(result.summary)

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
