"""Compatibility-preserving TUI input routing facade."""
# allow: SIZE_OK — TuiInputRouter is the compatibility facade for split route paths.

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from vnalpha.tui.operational_bridge import OperationalCommandBridge
from vnalpha.tui.routing import events
from vnalpha.tui.routing.chat_path import ChatPath
from vnalpha.tui.routing.command_path import CommandPath
from vnalpha.tui.routing.lifecycle_hooks import LifecycleHooks
from vnalpha.tui.routing.status_adapter import StatusAdapter, TraceEvent

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection

    from vnalpha.chat.controller import ChatController
    from vnalpha.commands.executor import CommandExecutor
    from vnalpha.commands.models import CommandResult, CommandStatus
    from vnalpha.tui.clipboard import ClipboardPort
    from vnalpha.tui.widgets.output_stream import OutputStream
    from vnalpha.tui.widgets.status_bar import StatusBar
    from vnalpha.workspace_context.models import WorkspaceState


class TuiInputRouter:
    """Route composer input while retaining the legacy public and private API."""

    def __init__(
        self,
        output_stream: OutputStream,
        target_date: str | None = None,
        on_busy_change: Callable[[bool], None] | None = None,
        status_bar: StatusBar | None = None,
        workspace: WorkspaceState | None = None,
        on_workspace_change: Callable[[WorkspaceState], None] | None = None,
        ui_dispatcher: Callable[[Callable[[], None]], None] | None = None,
        clipboard: ClipboardPort | None = None,
        log_text_provider: Callable[[], str] | None = None,
    ) -> None:
        self._output = output_stream
        self._target_date = target_date
        self._on_busy_change = on_busy_change
        self._status_bar = status_bar
        self._workspace = workspace or self._load_active_workspace()
        self._on_workspace_change = on_workspace_change
        self._ui_dispatcher = ui_dispatcher
        self._clipboard = clipboard
        self._log_text_provider = log_text_provider
        self._busy = False
        self._chat_controller: ChatController | None = None
        self._command_conn: DuckDBPyConnection | None = None
        self._command_executor: CommandExecutor | None = None
        self._operational_bridge = OperationalCommandBridge()
        self._status_adapter = StatusAdapter(status_bar)
        self._lifecycle_hooks = LifecycleHooks(
            output_stream,
            target_date,
            self._status_adapter,
            ui_dispatcher,
        )
        self._command_path = CommandPath()
        self._chat_path = ChatPath()
        self._setup_controller()
        self._setup_executor()

    def _load_active_workspace(self) -> WorkspaceState:
        from vnalpha.workspace_context.recovery import recover_workspace

        return recover_workspace().workspace

    def _bootstrap_session(self) -> str | None:
        return self._lifecycle_hooks.bootstrap_session()

    def _setup_controller(self) -> None:
        self._chat_controller = self._lifecycle_hooks.setup_controller(
            self._bootstrap_session()
        )

    def _setup_executor(self) -> None:
        resources = self._lifecycle_hooks.setup_executor()
        self._command_conn = resources.connection
        self._command_executor = resources.executor

    async def route(self, text: str) -> None:
        raw = text.strip()
        if not raw:
            return
        if raw.split(maxsplit=1)[0] == "/copy":
            self._handle_copy(raw)
            return
        if not raw.startswith("/"):
            self._output.show_user_input(raw)
        if raw == "/clear":
            self._output.clear_transcript()
            return
        if raw in ("/approve", "approve"):
            self._handle_approve()
            return
        if raw in ("/cancel", "cancel"):
            self._handle_cancel()
            return
        if raw == "a" and self._has_pending_plan():
            self._handle_approve()
            return
        if raw in ("n", "no") and self._has_pending_plan():
            self._handle_cancel()
            return
        if self._busy:
            events.emit_rejected(raw, "busy")
            self._output.show_warning("Still processing, please wait…", source="router")
            return
        self._record_workspace_input(raw)
        self._set_busy(True)
        self._set_status_routing()
        try:
            if raw.startswith("/"):
                if self._is_operational_command(raw):
                    await self._route_operational_command(raw)
                else:
                    await self._route_command(raw)
            else:
                await self._route_chat(raw)
        except Exception as exc:
            public_message = (
                "Unexpected routing failure. Inspect the debug logs for details."
            )
            self._set_status_error(public_message)
            self._output.show_error(public_message, source="router")
            self._capture_render_error(exc)
        finally:
            self._set_busy(False)

    async def _route_command(self, raw: str) -> None:
        await self._command_path.route(self, raw)

    async def _route_operational_command(self, raw: str) -> None:
        await self._command_path.route_operational(self, raw)

    async def _route_chat(self, raw: str) -> None:
        await self._chat_path.route(self, raw)

    def _result_to_markup(self, result: CommandResult | None) -> str:
        return self._command_path.result_to_markup(result)

    def _record_workspace_input(self, raw: str) -> None:
        try:
            from vnalpha.tui.workspace_context import record_workspace_input

            record_workspace_input(self._workspace, raw)
        except Exception as exc:
            self._output.show_warning(
                "Workspace input history is unavailable; continuing.",
                source="workspace",
            )
            events.capture_render_error(exc)

    def close(self) -> None:
        """Close the router-owned command connection exactly once."""
        if self._chat_controller is not None:
            self._chat_controller.close()
            self._chat_controller = None
        connection = self._command_conn
        self._command_conn = None
        self._lifecycle_hooks.close_connection(connection)

    def _is_operational_command(self, raw: str) -> bool:
        return raw.split(maxsplit=1)[0] in {"/logs", "/repair", "/deploy"}

    def _dispatch_ui(self, callback: Callable[[], None]) -> None:
        self._lifecycle_hooks.dispatch_ui(callback)

    def _render_trace(self, event: TraceEvent) -> None:
        self._lifecycle_hooks.render_trace(event)

    def _record_command_artifacts(self, result: CommandResult) -> None:
        try:
            from vnalpha.tui.workspace_context import record_command_artifacts

            record_command_artifacts(self._workspace, result)
        except Exception as exc:
            self._output.show_warning(
                "Workspace artifact history is unavailable; continuing.",
                source="workspace",
            )
            events.capture_render_error(exc)

    def _refresh_workspace_after_context_command(
        self, raw: str, status: CommandStatus
    ) -> bool:
        from vnalpha.tui.workspace_context import (
            refreshed_workspace_for_context_command,
        )

        workspace = refreshed_workspace_for_context_command(raw, status)
        if workspace is None:
            return False
        self._workspace = workspace
        return True

    def _notify_workspace_change(self) -> None:
        try:
            from vnalpha.tui.workspace_context import notify_workspace_change

            notify_workspace_change(
                self._on_workspace_change,
                self._load_active_workspace(),
            )
        except Exception as exc:
            self._output.show_warning(
                "Workspace refresh is unavailable; continuing.", source="workspace"
            )
            events.capture_render_error(exc)

    def _has_pending_plan(self) -> bool:
        return (
            self._chat_controller is not None
            and getattr(self._chat_controller, "_pending_plan", None) is not None
        )

    def _handle_copy(self, raw: str) -> None:
        parts = raw.split()
        if len(parts) != 2:
            self._status_adapter.warning("Usage: /copy result|output|logs|artifact-id")
            return
        self.copy_target(parts[1].lower())

    def copy_target(self, target: str) -> bool:
        providers: dict[str, Callable[[], str]] = {
            "result": self._output.latest_result_text,
            "output": self._output.transcript_text,
            "logs": self._log_text_provider or (lambda: ""),
            "artifact-id": lambda: self._output.current_artifact_id() or "",
        }
        provider = providers.get(target)
        if provider is None:
            self._status_adapter.warning(f"Unsupported copy target: {target}")
            return False
        text = provider()
        if not text:
            self._status_adapter.warning(f"Nothing to copy for {target}.")
            return False
        if self._clipboard is None:
            self._status_adapter.warning("Copy failed: clipboard access is unavailable")
            return False

        from vnalpha.tui.clipboard import prepare_clipboard_text

        prepared, truncated = prepare_clipboard_text(text)
        try:
            receipt = self._clipboard.copy(prepared)
        except Exception as exc:
            self._status_adapter.warning("Copy failed: clipboard backend error")
            events.capture_render_error(exc)
            return False
        confirmed = getattr(receipt, "confirmed", False)
        if truncated:
            self._status_adapter.update(
                "READY",
                label=(
                    f"Copied {target} (truncated)"
                    if confirmed
                    else f"Clipboard request sent for {target} (truncated)"
                ),
                detail=(
                    f"{len(prepared)} of {len(text)} characters; "
                    f"{getattr(receipt, 'detail', 'confirmation unavailable')}"
                ),
            )
        else:
            self._status_adapter.update(
                "READY",
                label=(
                    f"Copied {target}"
                    if confirmed
                    else f"Clipboard request sent for {target}"
                ),
                detail=(
                    f"{len(prepared)} characters"
                    if confirmed
                    else (
                        f"{len(prepared)} characters; "
                        f"{getattr(receipt, 'detail', 'confirmation unavailable')}"
                    )
                ),
            )
        return True

    def _handle_approve(self) -> None:
        self._emit_routed("approve", "/approve")
        if self._chat_controller is not None:
            try:
                self._chat_controller.approve_pending_plan()
            except Exception as exc:
                self._output.show_error(
                    "Plan approval failed. Inspect the debug logs for details.",
                    source="approve",
                )
                events.capture_render_error(exc)

    def _handle_cancel(self) -> None:
        self._emit_routed("cancel", "/cancel")
        if self._chat_controller is not None:
            try:
                self._chat_controller.cancel_pending_plan()
            except Exception as exc:
                self._output.show_error(
                    "Plan cancellation failed. Inspect the debug logs for details.",
                    source="cancel",
                )
                events.capture_render_error(exc)

    def _set_status_routing(self) -> None:
        self._status_adapter.routing()

    def _set_status_command(self, raw: str) -> None:
        self._status_adapter.command(raw)

    def _set_status_chat(self) -> None:
        self._status_adapter.chat()

    def _set_status_ready(self) -> None:
        self._status_adapter.ready()

    def _set_status_error(self, detail: str) -> None:
        self._status_adapter.error(detail)

    def _set_status_warning(self, detail: str) -> None:
        self._status_adapter.warning(detail)

    def _update_trace_status(self, event: TraceEvent) -> None:
        self._status_adapter.trace(event)

    def _update_status(
        self, state_name: str, label: str = "", detail: str = ""
    ) -> None:
        self._status_adapter.update(state_name, label, detail)

    def _emit_routed(self, route_type: str, raw: str) -> None:
        events.emit_routed(route_type, raw)

    def _capture_render_error(self, exc: Exception) -> None:
        events.capture_render_error(exc)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        if self._on_busy_change is not None:
            try:
                self._on_busy_change(busy)
            except Exception:
                pass
