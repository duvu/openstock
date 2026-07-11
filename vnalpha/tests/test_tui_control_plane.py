from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vnalpha.commands.models import CommandError, CommandResult
from vnalpha.workspace_context.lifecycle import create_workspace


@pytest.mark.parametrize(
    ("status", "expected_state"),
    [
        ("EMPTY_RESULT", "READY"),
        ("PARTIAL", "WARNING"),
    ],
)
def test_status_adapter_projects_command_outcomes(
    status: str, expected_state: str
) -> None:
    from vnalpha.tui.routing.status_adapter import StatusAdapter

    status_bar = MagicMock()

    StatusAdapter(status_bar).command_result(
        CommandResult(status=status, title="Research", summary="No complete result")
    )

    runtime_status = status_bar.update_status.call_args.args[0]
    assert runtime_status.state.value == expected_state


@pytest.mark.parametrize(
    ("result", "expected_state"),
    [
        (
            CommandResult(
                status="SUCCESS",
                title="Research",
                summary="Completed",
                warnings=["Stale quote"],
            ),
            "WARNING",
        ),
        (
            CommandResult(
                status="FAILED",
                title="Research",
                error=CommandError(
                    error_type="RuntimeError", message="Provider unavailable"
                ),
            ),
            "ERROR",
        ),
        (
            CommandResult(
                status="VALIDATION_ERROR",
                title="Research",
                error=CommandError(
                    error_type="CommandValidationError", message="Symbol required"
                ),
            ),
            "ERROR",
        ),
    ],
)
def test_status_adapter_projects_warning_and_error_command_outcomes(
    result: CommandResult, expected_state: str
) -> None:
    from vnalpha.tui.routing.status_adapter import StatusAdapter

    status_bar = MagicMock()

    StatusAdapter(status_bar).command_result(result)

    runtime_status = status_bar.update_status.call_args.args[0]
    assert runtime_status.state.value == expected_state


def test_executor_setup_reports_and_captures_failure() -> None:
    from vnalpha.tui.routing.lifecycle_hooks import LifecycleHooks
    from vnalpha.tui.routing.status_adapter import StatusAdapter

    output = MagicMock()
    hooks = LifecycleHooks(output, "2026-07-10", StatusAdapter(None), None)

    with patch(
        "vnalpha.warehouse.connection.get_connection",
        side_effect=RuntimeError("warehouse unavailable"),
    ):
        with patch("vnalpha.observability.errors.capture_exception") as capture:
            resources = hooks.setup_executor()

    assert resources.connection is None
    assert resources.executor is None
    output.show_error.assert_called_once_with(
        "Command setup failed: warehouse unavailable", source="router"
    )
    capture.assert_called_once()


def test_input_submission_sets_correlation_before_audit() -> None:
    from vnalpha.tui.app import VnAlphaApp

    app = MagicMock()
    with patch(
        "vnalpha.observability.context.get_correlation_id", return_value="unset"
    ):
        with patch("vnalpha.observability.context.set_correlation_id") as set_id:
            with patch("vnalpha.tui.app._emit_audit_event") as emit:
                VnAlphaApp._emit_input_submitted(app, "/help")

    set_id.assert_called_once_with()
    emit.assert_called_once_with("TUI_INPUT_SUBMITTED", "len=5")


@pytest.mark.asyncio
async def test_help_routes_through_executor_and_renders_inline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from vnalpha.tui.input_router import TuiInputRouter
    from vnalpha.tui.widgets.output_stream import OutputStream

    output = MagicMock(spec=OutputStream)
    monkeypatch.setenv("VNALPHA_WORKSPACE_ROOT", str(tmp_path))
    with patch.object(TuiInputRouter, "_setup_controller"):
        with patch.object(TuiInputRouter, "_setup_executor"):
            router = TuiInputRouter(
                output_stream=output,
                workspace=create_workspace(root=tmp_path),
            )
    executor = MagicMock()
    executor.execute.return_value = CommandResult(
        status="SUCCESS", title="/help", summary="Available commands"
    )
    router._command_executor = executor

    await router.route("/help")

    executor.execute.assert_called_once_with("/help")
    output.show_command_result.assert_called_once()
