"""AssistantScreen: natural-language research assistant surface for the TUI."""

from __future__ import annotations

from rich.text import Text

from vnalpha.assistant.app import AssistantApp
from vnalpha.assistant.degraded_answer import degradation_warning, lifecycle_warning
from vnalpha.assistant.errors import (
    AssistantInputValidationError,
    AssistantLifecycleError,
)
from vnalpha.assistant.gateway import LLMGatewayClient, LLMGatewayConfig
from vnalpha.assistant.models import AssistantAnswer, RefusalMessage
from vnalpha.assistant.planner import PlanBuilder
from vnalpha.core.text_safety import sanitize_error_summary, sanitize_text
from vnalpha.observability.errors import capture_exception

try:
    from textual.app import ComposeResult
    from textual.screen import Screen
    from textual.widgets import Footer, Header, Input, Label, Static

    _TEXTUAL_AVAILABLE = True
except ImportError:
    _TEXTUAL_AVAILABLE = False


def render_assistant_answer(answer: AssistantAnswer) -> Text:
    answer_text = Text(sanitize_text(answer.summary), style="bold")
    answer_text.append("\n\nBasis: ", style="dim")
    answer_text.append(sanitize_text(answer.basis))
    answer_text.append("\nRisks: ", style="dim yellow")
    answer_text.append(sanitize_text(answer.risks_caveats))
    warning = degradation_warning(answer)
    if warning is not None:
        answer_text.append("\nWarning: ", style="bold yellow")
        answer_text.append(sanitize_text(warning), style="yellow")
    return answer_text


if _TEXTUAL_AVAILABLE:

    class AssistantScreen(Screen):
        """Natural-language research assistant screen."""

        TITLE = "Research Assistant"
        BINDINGS = [("escape", "app.pop_screen", "Back")]

        def __init__(
            self,
            target_date: str | None = None,
            *,
            target_date_is_implicit: bool = False,
            **kwargs,
        ):
            super().__init__(**kwargs)
            self.target_date = target_date
            self.target_date_is_implicit = target_date_is_implicit

        def compose(self) -> ComposeResult:
            yield Header()
            yield Label("Research Assistant — ask a question in plain language")
            yield Input(
                placeholder='e.g. "Show strongest VN30 candidates today"',
                id="assistant-input",
            )
            yield Static("", id="assistant-answer")
            yield Static("", id="assistant-plan")
            yield Footer()

        def on_mount(self) -> None:
            """Auto-focus the input when the screen is mounted."""
            try:
                self.query_one("#assistant-input", Input).focus()
            except Exception:
                pass

        def on_input_submitted(self, event: Input.Submitted) -> None:
            question = event.value.strip()
            if not question:
                return
            self._process_question(question)

        def _process_question(self, question: str) -> None:
            answer_panel = self.query_one("#assistant-answer", Static)
            plan_panel = self.query_one("#assistant-plan", Static)
            answer_panel.update(Text("Processing...", style="dim"))
            try:
                llm_client = LLMGatewayClient(LLMGatewayConfig.from_env())
                app = AssistantApp.managed(surface="tui", llm_client=llm_client)
                result, plan = app.ask(
                    question,
                    date=self.target_date,
                    date_is_implicit=self.target_date_is_implicit,
                )
                if isinstance(result, RefusalMessage):
                    refusal_text = Text("Refused: ", style="red")
                    refusal_text.append(sanitize_text(result.reason))
                    answer_panel.update(refusal_text)
                    return
                answer_panel.update(render_assistant_answer(result))
                plan_panel.update(
                    Text(sanitize_text(PlanBuilder().preview(plan)), style="dim")
                )
            except AssistantInputValidationError as exc:
                public_error = sanitize_error_summary(exc)
                answer_panel.update(Text(f"Error: {public_error}", style="red"))
            except AssistantLifecycleError as exc:
                answer_panel.update(
                    Text(
                        lifecycle_warning(exc.stage, exc.category, exc.correlation_id),
                        style="red",
                    )
                )
            except Exception as exc:
                capture_exception(exc)
                answer_panel.update(
                    Text(
                        lifecycle_warning("REQUEST_FAILED", "UNEXPECTED_FAILURE", None),
                        style="red",
                    )
                )

else:

    class AssistantScreen:  # type: ignore[no-redef]
        """Stub when textual is not installed."""

        def __init__(
            self,
            target_date: str | None = None,
            *,
            target_date_is_implicit: bool = False,
        ):
            self.target_date = target_date
            self.target_date_is_implicit = target_date_is_implicit
