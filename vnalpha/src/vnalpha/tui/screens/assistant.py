"""AssistantScreen: natural-language research assistant surface for the TUI."""

from __future__ import annotations

try:
    from rich.text import Text
    from textual.app import ComposeResult
    from textual.screen import Screen
    from textual.widgets import Footer, Header, Input, Label, Static

    _TEXTUAL_AVAILABLE = True
except ImportError:
    _TEXTUAL_AVAILABLE = False

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
                from vnalpha.assistant.app import AssistantApp
                from vnalpha.assistant.gateway import LLMGatewayClient, LLMGatewayConfig
                from vnalpha.assistant.models import RefusalMessage
                from vnalpha.warehouse.connection import get_connection
                from vnalpha.warehouse.migrations import run_migrations

                conn = get_connection()
                run_migrations(conn=conn)
                llm_client = LLMGatewayClient(LLMGatewayConfig.from_env())
                app = AssistantApp(conn, surface="tui", llm_client=llm_client)
                result, plan = app.ask(
                    question,
                    date=self.target_date,
                    date_is_implicit=self.target_date_is_implicit,
                )
                if isinstance(result, RefusalMessage):
                    refusal_text = Text("Refused: ", style="red")
                    refusal_text.append(result.reason)
                    answer_panel.update(refusal_text)
                    return
                answer_text = Text(result.summary, style="bold")
                answer_text.append("\n\nBasis: ", style="dim")
                answer_text.append(result.basis)
                answer_text.append("\nRisks: ", style="dim yellow")
                answer_text.append(result.risks_caveats)
                answer_panel.update(answer_text)
                from vnalpha.assistant.planner import PlanBuilder

                plan_panel.update(Text(PlanBuilder().preview(plan), style="dim"))
            except Exception as exc:
                answer_panel.update(Text(f"Error: {exc}", style="red"))
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
