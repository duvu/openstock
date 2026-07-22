from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from vnalpha.assistant.app import AssistantApp
from vnalpha.assistant.degraded_answer import (
    AssistantFailureStage,
    degradation_warning,
    lifecycle_warning,
)
from vnalpha.assistant.errors import (
    AssistantError,
    AssistantInputValidationError,
    AssistantLifecycleError,
    LLMConfigError,
)
from vnalpha.assistant.gateway import LLMGatewayClient, LLMGatewayConfig
from vnalpha.assistant.models import AssistantAnswer, RefusalMessage
from vnalpha.assistant.planner import PlanBuilder
from vnalpha.core.dates import resolve_date
from vnalpha.core.logging import set_correlation_id
from vnalpha.core.text_safety import sanitize_error_summary, sanitize_text
from vnalpha.observability.commands import command_lifecycle
from vnalpha.observability.errors import capture_exception
from vnalpha.warehouse.connection import get_connection


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
            console = Console()
            error_console = Console(stderr=True)

            if date is not None and date.strip().lower() != "today":
                try:
                    resolve_date(date)
                except ValueError as exc:
                    public_error = sanitize_error_summary(exc)
                    error_console.print(
                        Text(f"Assistant error: {public_error}", style="red")
                    )
                    raise typer.Exit(code=1) from exc

            try:
                with get_connection() as connection:
                    resolved_date = resolve_date(date, conn=connection)
            except ValueError as exc:
                public_error = sanitize_error_summary(exc)
                error_console.print(
                    Text(f"Assistant error: {public_error}", style="red")
                )
                raise typer.Exit(code=1) from exc
            except Exception as exc:
                capture_exception(exc)
                error_console.print(
                    Text(
                        lifecycle_warning(
                            AssistantFailureStage.CLASSIFY, "CONNECTION_FAILURE", None
                        ),
                        style="red",
                    )
                )
                raise typer.Exit(code=1) from exc

            try:
                llm_config = LLMGatewayConfig.from_env()
                llm_client = LLMGatewayClient(llm_config)
                assistant = AssistantApp.managed(surface="cli", llm_client=llm_client)
                result, plan = assistant.ask(
                    question,
                    date=resolved_date,
                    date_is_implicit=(date is None or date.strip().lower() == "today"),
                    no_execute=no_execute,
                )
            except LLMConfigError as exc:
                capture_exception(exc)
                config_error = Text(
                    "Natural-language chat is unavailable because the LLM route "
                    "is not configured correctly.\n",
                    style="yellow",
                )
                config_error.append(
                    "Deterministic slash and data commands remain usable. "
                    "Run 'vnalpha preflight' to diagnose the LLM route.",
                    style="dim",
                )
                error_console.print(config_error)
                raise typer.Exit(code=1) from exc
            except AssistantInputValidationError as exc:
                public_error = sanitize_error_summary(exc)
                error_console.print(
                    Text(f"Assistant error: {public_error}", style="red")
                )
                raise typer.Exit(code=1) from exc
            except AssistantLifecycleError as exc:
                error_console.print(
                    Text(
                        lifecycle_warning(
                            exc.stage,
                            exc.category,
                            exc.correlation_id,
                            trace_id=exc.trace_id,
                            model_route=exc.model_route,
                        ),
                        style="red",
                    )
                )
                raise typer.Exit(code=1) from exc
            except AssistantError as exc:
                capture_exception(exc)
                error_console.print(
                    Text(
                        lifecycle_warning(
                            AssistantFailureStage.ANSWER_VALIDATION,
                            "ASSISTANT_FAILURE",
                            None,
                        ),
                        style="red",
                    )
                )
                raise typer.Exit(code=1) from exc
            except Exception as exc:
                capture_exception(exc)
                error_console.print(
                    Text(
                        lifecycle_warning(
                            AssistantFailureStage.ANSWER_VALIDATION,
                            "UNEXPECTED_FAILURE",
                            None,
                        ),
                        style="red",
                    )
                )
                raise typer.Exit(code=1) from exc

            if show_plan or no_execute:
                pb = PlanBuilder()
                console.print(
                    Panel(
                        Text(sanitize_text(pb.preview(plan))),
                        title="Research Plan",
                        border_style="blue",
                    )
                )

            if isinstance(result, RefusalMessage):
                refusal_text = Text(sanitize_text(result.reason), style="yellow")
                if result.suggestion:
                    refusal_text.append("\n\nSuggestion: ", style="dim")
                    refusal_text.append(sanitize_text(result.suggestion), style="dim")
                console.print(
                    Panel(
                        refusal_text,
                        title="[red]Request Refused[/red]",
                        border_style="red",
                    )
                )
                raise typer.Exit(code=1)

            assert isinstance(result, AssistantAnswer)
            answer_text = Text()
            answer_text.append(sanitize_text(result.summary) + "\n\n", style="bold")
            answer_text.append("Basis: ", style="dim")
            answer_text.append(sanitize_text(result.basis) + "\n")
            if result.risks_caveats:
                answer_text.append("Risks/caveats: ", style="dim yellow")
                answer_text.append(sanitize_text(result.risks_caveats) + "\n")
            warning = degradation_warning(result)
            if warning is not None:
                answer_text.append("Warning: ", style="bold yellow")
                answer_text.append(sanitize_text(warning) + "\n", style="yellow")
            if result.missing_data:
                answer_text.append("\nMissing data:\n", style="dim red")
                for item in result.missing_data:
                    answer_text.append(f"  • {sanitize_text(item)}\n", style="red")
            console.print(
                Panel(answer_text, title="Research Answer", border_style="green")
            )

            if trace:
                console.print(
                    Panel(
                        Text(sanitize_text(result.tool_trace_summary or "(no trace)")),
                        title="Tool Trace",
                        border_style="dim",
                    )
                )
