"""AssistantScreen: natural-language research assistant surface for the TUI."""
from __future__ import annotations

try:
    from textual.app import ComposeResult
    from textual.screen import Screen
    from textual.widgets import Footer, Header, Input, Label, Static
    _TEXTUAL_AVAILABLE = True
except ImportError:
    _TEXTUAL_AVAILABLE = False

if _TEXTUAL_AVAILABLE:
    class AssistantScreen(Screen):
        """Natural-language research assistant screen."""

        BINDINGS = [("escape", "app.pop_screen", "Back")]

        def __init__(self, target_date: str | None = None):
            super().__init__()
            self.target_date = target_date

        def compose(self) -> ComposeResult:
            yield Header()
            yield Label("Research Assistant — ask a question in plain language")
            yield Input(placeholder='e.g. "Show strongest VN30 candidates today"', id="assistant-input")
            yield Static("", id="assistant-answer")
            yield Static("", id="assistant-plan")
            yield Footer()

        def on_input_submitted(self, event: Input.Submitted) -> None:
            question = event.value.strip()
            if not question:
                return
            self._process_question(question)

        def _process_question(self, question: str) -> None:
            answer_panel = self.query_one("#assistant-answer", Static)
            plan_panel = self.query_one("#assistant-plan", Static)
            answer_panel.update("[dim]Processing...[/dim]")
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
                result, plan = app.ask(question, date=self.target_date)
                if isinstance(result, RefusalMessage):
                    answer_panel.update(f"[red]Refused:[/red] {result.reason}")
                    return
                answer_panel.update(
                    f"[bold]{result.summary}[/bold]\n\n"
                    f"[dim]Basis:[/dim] {result.basis}\n"
                    f"[dim yellow]Risks:[/dim yellow] {result.risks_caveats}"
                )
                from vnalpha.assistant.planner import PlanBuilder
                plan_panel.update(f"[dim]{PlanBuilder().preview(plan)}[/dim]")
            except Exception as exc:
                answer_panel.update(f"[red]Error: {exc}[/red]")
else:
    class AssistantScreen:  # type: ignore[no-redef]
        """Stub when textual is not installed."""

        def __init__(self, target_date: str | None = None):
            self.target_date = target_date
