from __future__ import annotations

from typing import Optional

import typer

from vnalpha.core.logging import set_correlation_id
from vnalpha.observability.commands import command_lifecycle


def register(app: typer.Typer) -> None:
    @app.command("log")
    def log_cmd(
        level: str = typer.Option(
            "ALL", "--level", help="Filter: ALL/DEBUG/INFO/WARNING/ERROR"
        ),
        since: Optional[str] = typer.Option(
            None, "--since", help="Time filter: '30m', '1h', '2d', or ISO datetime"
        ),
        grep: Optional[str] = typer.Option(
            None, "--grep", help="Substring filter on event field"
        ),
        tail: int = typer.Option(50, "--tail", help="Show last N records (default 50)"),
    ) -> None:
        """View and filter the vnalpha structured log file.

        Examples:
            vnalpha log --tail 20
            vnalpha log --level ERROR
            vnalpha log --level INFO --since 1h
            vnalpha log --grep "sync" --tail 30
        """
        set_correlation_id()
        with command_lifecycle("log"):
            from rich.console import Console

            from vnalpha.log_viewer import (
                default_log_path,
                format_record_rich,
                read_log_records,
            )

            console = Console()
            log_path = default_log_path()

            if not log_path.exists():
                console.print(
                    f"[yellow]Log file not found: {log_path}[/yellow]\n"
                    "[dim]Run any vnalpha command first to create it.[/dim]"
                )
                return

            records = read_log_records(
                log_path,
                level=level,
                since=since,
                grep=grep,
                tail=tail,
            )

            if not records:
                console.print("[dim]No log records match the filters.[/dim]")
                return

            for rec in records:
                console.print(format_record_rich(rec))

            console.print(
                f"\n[dim]Showing {len(records)} record(s) from {log_path}[/dim]"
            )
