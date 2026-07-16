from __future__ import annotations

from typing import Optional

import typer

from vnalpha.core.dates import resolve_date
from vnalpha.core.logging import set_correlation_id
from vnalpha.observability.commands import command_lifecycle


def register(app: typer.Typer) -> None:
    @app.command("ask")
    def ask_runner(
        question: str = typer.Argument(..., help="Natural-language research question."),
        date: Optional[str] = typer.Option(
            None, "--date", help="Target date (YYYY-MM-DD or 'today')."
        ),
        show_plan: bool = typer.Option(
            False, "--show-plan", help="Print the tool plan before answering."
        ),
        trace: bool = typer.Option(
            False, "--trace", help="Print tool trace summary after answering."
        ),
        no_execute: bool = typer.Option(
            False, "--no-execute", help="Show plan only; do not execute tools."
        ),
    ) -> None:
        """Ask a natural-language research question. Phase 5.9 research assistant.

        Examples:
            vnalpha ask "Show strongest VN30 candidates today"
            vnalpha ask "Why is FPT in the watchlist?"
            vnalpha ask "Compare FPT, VNM, and MWG"
            vnalpha ask "Which candidates have weak data quality?"
        """
        set_correlation_id()
        with command_lifecycle("ask"):
            from rich.console import Console
            from rich.panel import Panel
            from rich.text import Text

            from vnalpha.assistant.app import AssistantApp
            from vnalpha.assistant.errors import AssistantError, LLMConfigError
            from vnalpha.assistant.gateway import LLMGatewayClient, LLMGatewayConfig
            from vnalpha.assistant.models import AssistantAnswer, RefusalMessage
            from vnalpha.warehouse.connection import get_connection
            from vnalpha.warehouse.migrations import run_migrations

            console = Console()
            error_console = Console(stderr=True)

            conn = get_connection()
            run_migrations(conn=conn)

            resolved_date = resolve_date(date, conn=conn)

            try:
                llm_config = LLMGatewayConfig.from_env()
                llm_client = LLMGatewayClient(llm_config)
                assistant = AssistantApp(conn, surface="cli", llm_client=llm_client)
                result, plan = assistant.ask(
                    question, date=resolved_date, no_execute=no_execute
                )
            except LLMConfigError as exc:
                # Natural-language chat is unavailable; deterministic slash and
                # data commands remain usable (issue #165 degraded mode).
                error_console.print(
                    f"[yellow]Natural-language chat is unavailable: {exc}[/yellow]\n"
                    "[dim]Deterministic slash and data commands remain usable. "
                    "Run 'vnalpha preflight' to diagnose the LLM route.[/dim]"
                )
                raise typer.Exit(code=1) from exc
            except AssistantError as exc:
                error_console.print(f"[red]Assistant error: {exc}[/red]")
                raise typer.Exit(code=1) from exc
            except Exception as exc:
                error_console.print(f"[red]Unexpected error: {exc}[/red]")
                raise typer.Exit(code=1) from exc

            if show_plan or no_execute:
                from vnalpha.assistant.planner import PlanBuilder

                pb = PlanBuilder()
                console.print(
                    Panel(pb.preview(plan), title="Research Plan", border_style="blue")
                )

            if isinstance(result, RefusalMessage):
                console.print(
                    Panel(
                        f"[yellow]{result.reason}[/yellow]"
                        + (
                            f"\n\n[dim]Suggestion: {result.suggestion}[/dim]"
                            if result.suggestion
                            else ""
                        ),
                        title="[red]Request Refused[/red]",
                        border_style="red",
                    )
                )
                raise typer.Exit(code=1)

            assert isinstance(result, AssistantAnswer)
            answer_text = Text()
            answer_text.append(result.summary + "\n\n", style="bold")
            answer_text.append("Basis: ", style="dim")
            answer_text.append(result.basis + "\n")
            if result.risks_caveats:
                answer_text.append("Risks/caveats: ", style="dim yellow")
                answer_text.append(result.risks_caveats + "\n")
            if result.missing_data:
                answer_text.append("\nMissing data:\n", style="dim red")
                for item in result.missing_data:
                    answer_text.append(f"  • {item}\n", style="red")
            console.print(
                Panel(answer_text, title="Research Answer", border_style="green")
            )

            if trace:
                console.print(
                    Panel(
                        result.tool_trace_summary or "(no trace)",
                        title="Tool Trace",
                        border_style="dim",
                    )
                )
