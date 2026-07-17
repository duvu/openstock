"""Slash-command execution and rendering for the TUI router."""

from __future__ import annotations

import inspect
from functools import partial
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
        if _is_research_workflow(raw):
            router._output.append_activity(
                raw,
                detail="research workflow running",
                kind="running",
            )
        try:
            if router._command_executor is None:
                router._output.show_error(
                    "CommandExecutor unavailable.", source="router"
                )
                router._set_status_error("CommandExecutor unavailable")
                return
            with command_lifecycle("tui research command", raw) as lifecycle:
                executor = router._command_executor
                execute = executor.execute
                session_id = getattr(router._chat_controller, "_chat_session_id", None)
                if (
                    session_id
                    and "session_scope_id" in inspect.signature(execute).parameters
                ):
                    execute = partial(execute, session_scope_id=session_id)
                result = await anyio.to_thread.run_sync(execute, raw)
                result_status = getattr(result.status, "value", result.status)
                if result_status in {"FAILED", "VALIDATION_ERROR"}:
                    lifecycle.mark_failed(result.summary)
            from vnalpha.tui.result_presentation import command_result_presentation

            router._output.show_command_result(
                raw,
                command_result_presentation(raw, result),
            )
            router._output.register_command_result(raw, result)
            workspace_changed = router._refresh_workspace_after_context_command(
                raw, result.status
            )
            router._record_command_artifacts(result)
            if workspace_changed:
                router._notify_workspace_change()
            router._status_adapter.command_result(
                result.status,
                result.summary,
                result.warnings,
                result.metadata,
            )
            if _is_research_workflow(raw):
                router._output.append_activity(
                    raw,
                    detail=_workflow_detail(result),
                    kind=_workflow_activity_kind(result.status),
                )
        except Exception as exc:
            public_message = (
                "Command failed unexpectedly. Inspect the debug logs for details."
            )
            router._output.show_error(public_message, source="command")
            router._set_status_error(public_message)
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
            output_text = await anyio.to_thread.run_sync(
                router._operational_bridge.execute, raw
            )
        from vnalpha.tui.result_presentation import operational_result_presentation

        router._output.show_command_result(
            raw,
            operational_result_presentation(raw, output_text),
        )
        router._set_status_ready()

    def result_to_markup(self, result: CommandResult | None) -> str:
        try:
            from vnalpha.commands.renderers.textual_renderer import result_to_markup

            return result_to_markup(result)
        except Exception:
            return str(result) if result is not None else ""


def _is_research_workflow(raw: str) -> bool:
    command_name = raw.split(maxsplit=1)[0].lstrip("/")
    return command_name in {
        "analyze",
        "market-regime",
        "sector-strength",
        "watchlist-summary",
        "shortlist",
        "research-plan",
        "setup-evidence",
    }


def _workflow_detail(result: CommandResult) -> str:
    metadata = result.metadata if isinstance(result.metadata, dict) else {}
    artifact_id = metadata.get("artifact_id")
    if isinstance(artifact_id, str) and artifact_id:
        return artifact_id
    return result.summary or result.title


def _workflow_activity_kind(status: object) -> str:
    value = getattr(status, "value", status)
    if value == "SUCCESS":
        return "done"
    if value in {"FAILED", "VALIDATION_ERROR"}:
        return "error"
    return "warning"
