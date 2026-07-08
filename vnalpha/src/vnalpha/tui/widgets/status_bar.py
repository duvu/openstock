"""StatusBar widget — compact one-line operational status for the TUI."""

from __future__ import annotations

from vnalpha.tui.runtime_status import RuntimeState, RuntimeStatus

try:
    from textual.app import ComposeResult
    from textual.reactive import reactive
    from textual.widget import Widget
    from textual.widgets import Static

    _TEXTUAL_AVAILABLE = True
except ImportError:
    _TEXTUAL_AVAILABLE = False


if _TEXTUAL_AVAILABLE:

    class StatusBar(Widget):
        """
        Compact one-line status bar showing the current runtime state.

        This is a supporting widget — not a primary pane.
        """

        DEFAULT_CSS = """
        StatusBar {
            height: 1;
            max-height: 1;
            width: 100%;
            background: $surface-darken-1;
            color: $text-muted;
            padding: 0 1;
        }
        """

        status_text: reactive[str] = reactive("READY", layout=False)

        def __init__(self, **kwargs) -> None:
            super().__init__(**kwargs)
            self._status = RuntimeStatus(state=RuntimeState.READY)

        def compose(self) -> ComposeResult:
            yield Static(self._render_status(), id="status-text")

        def update_status(self, status: RuntimeStatus) -> None:
            """Update the displayed status."""
            old = self._status
            self._status = status
            self._refresh_display()
            self._emit_status_changed(old.state, status.state)

        def _refresh_display(self) -> None:
            try:
                static = self.query_one("#status-text", Static)
                static.update(self._render_status())
            except Exception:
                pass

        def _render_status(self) -> str:
            """Render the status as a Rich markup string."""
            s = self._status
            state = s.state
            badge = _RICH_BADGES.get(state, f"[dim]{state.value}[/dim]")
            parts = [badge]
            if s.label:
                parts.append(s.label)
            if s.detail:
                d = s.detail[:50] + "…" if len(s.detail) > 50 else s.detail
                parts.append(f"[dim]{d}[/dim]")
            return " │ ".join(parts)

        def _emit_status_changed(
            self, from_state: RuntimeState, to_state: RuntimeState
        ) -> None:
            if from_state == to_state:
                return
            try:
                from vnalpha.observability.audit import log_audit

                log_audit(
                    "TUI_STATUS_CHANGED",
                    f"from={from_state.value} to={to_state.value}",
                    module="vnalpha.tui.widgets.status_bar",
                )
            except Exception:
                pass

else:

    class StatusBar:  # type: ignore[no-redef]
        """Importable fallback used when textual is unavailable."""

        DEFAULT_CSS = ""

        def __init__(self, **kwargs) -> None:
            self._status = RuntimeStatus(state=RuntimeState.READY)

        def update_status(self, status: RuntimeStatus) -> None:
            self._status = status


_RICH_BADGES: dict[RuntimeState, str] = {
    RuntimeState.IDLE: "[dim]IDLE[/dim]",
    RuntimeState.ROUTING_INPUT: "[bold]ROUTING[/bold]",
    RuntimeState.COMMAND_RUNNING: "[bold cyan]RUNNING[/bold cyan]",
    RuntimeState.CHAT_THINKING: "[bold magenta]THINKING[/bold magenta]",
    RuntimeState.TOOL_RUNNING: "[bold blue]TOOL[/bold blue]",
    RuntimeState.DATA_ENSURE_RUNNING: "[bold yellow]DATA[/bold yellow]",
    RuntimeState.DATA_SYNCING: "[bold yellow]SYNCING[/bold yellow]",
    RuntimeState.BUILDING_FEATURES: "[bold yellow]FEATURES[/bold yellow]",
    RuntimeState.SCORING: "[bold yellow]SCORING[/bold yellow]",
    RuntimeState.READY: "[bold green]READY[/bold green]",
    RuntimeState.WARNING: "[bold yellow]⚠ WARN[/bold yellow]",
    RuntimeState.ERROR: "[bold red]✗ ERROR[/bold red]",
    RuntimeState.SERVICE_UNAVAILABLE: "[bold red]✗ UNAVAIL[/bold red]",
}
