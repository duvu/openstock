"""Slash-command execution and rendering for the TUI router."""

from __future__ import annotations

from typing import TYPE_CHECKING

import anyio

from vnalpha.observability.commands import command_lifecycle
from vnalpha.tui.operational_bridge import UnsupportedOperationalCommand
from vnalpha.tui.routing import events

if TYPE_CHECKING:
    from vnalpha.commands.models import CommandResult
    from vnalpha.tui.routing.router import TuiInputRouter


class CommandPath:
    """Run research and operational commands without owning route selection."""

    async def route(self, router: TuiInputRouter, raw: str) -> None:
        router._emit_routed("command", raw)
        router._set_status_command(raw)
        try:
            if router._command_executor is None:
                router._output.show_error(
                    "CommandExecutor unavailable.", source="router"
                )
                router._set_status_error("CommandExecutor unavailable")
                return
            with command_lifecycle("tui research command", raw):
                result = await anyio.to_thread.run_sync(
                    router._command_executor.execute, raw
                )
            router._output.show_command_result(raw, self.result_to_markup(result))
            workspace_changed = router._refresh_workspace_after_context_command(
                raw, result.status
            )
            router._record_command_artifacts(result)
            if workspace_changed:
                router._notify_workspace_change()
            if result.warnings:
                router._set_status_warning("; ".join(result.warnings[:2]))
            else:
                router._set_status_ready()
        except Exception as exc:
            router._output.show_error(str(exc), source="command")
            router._set_status_error(str(exc))
            events.capture_render_error(exc)

    async def route_operational(self, router: TuiInputRouter, raw: str) -> None:
        router._emit_routed("command", raw)
        router._set_status_command(raw)
        if not router._operational_bridge.is_supported(raw):
            error = UnsupportedOperationalCommand(
                "Unsupported operational command. Use /logs, /repair, or /deploy help."
            )
            try:
                with command_lifecycle("tui operational command", raw, mode="redacted"):
                    raise error
            except UnsupportedOperationalCommand:
                router._output.show_error(str(error), source="operational")
            router._set_status_warning("Unsupported operational command")
            return
        with command_lifecycle("tui operational command", raw):
            markup = await anyio.to_thread.run_sync(
                router._operational_bridge.execute, raw
            )
        router._output.show_command_result(raw, markup)
        router._set_status_ready()

    def result_to_markup(self, result: CommandResult | None) -> str:
        try:
            from vnalpha.commands.renderers.textual_renderer import result_to_markup

            return result_to_markup(result)
        except Exception:
            return str(result) if result is not None else ""
