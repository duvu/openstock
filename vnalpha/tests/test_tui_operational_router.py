from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vnalpha.commands.models import CommandResult
from vnalpha.observability.context import (
    RunContext,
    reset_run_context,
    set_correlation_id,
)
from vnalpha.workspace_context.lifecycle import create_workspace
from vnalpha.workspace_context.models import WorkspaceState


@pytest.fixture(autouse=True)
def reset_observability_context(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VNALPHA_WORKSPACE_ROOT", str(tmp_path))
    reset_run_context()
    yield
    reset_run_context()


def make_router(tmp_path: Path, workspace: WorkspaceState):
    from vnalpha.tui.input_router import TuiInputRouter
    from vnalpha.tui.widgets.output_stream import OutputStream

    output = MagicMock(spec=OutputStream)
    with patch.object(TuiInputRouter, "_setup_controller"):
        with patch.object(TuiInputRouter, "_setup_executor"):
            router = TuiInputRouter(
                output_stream=output,
                target_date="2026-07-10",
                workspace=workspace,
            )
    router._command_executor = MagicMock()
    router._command_executor.execute.return_value = CommandResult(
        status="SUCCESS", title="research", summary="completed"
    )
    return router, output


@pytest.mark.parametrize(
    ("command", "action_name"),
    [
        ("/logs errors --latest", "logs_errors"),
        ("/logs summarize --latest", "logs_summarize"),
        ("/repair prepare --latest", "repair_prepare"),
        ("/repair status repair-123", "repair_status"),
        ("/deploy verify candidate-1", "deploy_verify"),
        ("/deploy promote candidate-1 --deployment-id deploy-123", "deploy_promote"),
        ("/deploy rollback deploy-123", "deploy_rollback"),
    ],
)
def test_operational_bridge_parses_only_documented_forms(
    command: str, action_name: str
) -> None:
    from vnalpha.tui.operational_bridge import OperationalCommandBridge

    actions = MagicMock()
    getattr(actions, action_name).return_value = "operation completed"
    bridge = OperationalCommandBridge(actions=actions)

    assert bridge.execute(command) == "operation completed"
    getattr(actions, action_name).assert_called_once()


@pytest.mark.parametrize(
    "command",
    [
        "/logs errors --latest --verbose",
        "/logs summarize latest",
        "/repair status repair-123 --latest",
        '/repair status ""',
        '/deploy verify ""',
        "/deploy promote candidate-1 deploy-123 --deployment-id",
        '/deploy rollback ""',
        "/logsfoo errors --latest",
    ],
)
def test_operational_bridge_rejects_near_matches_and_extra_arguments(
    command: str,
) -> None:
    from vnalpha.tui.operational_bridge import OperationalCommandBridge

    bridge = OperationalCommandBridge(actions=MagicMock())

    assert bridge.is_supported(command) is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "command",
    [
        "/logs errors --latest",
        "/logs summarize --latest",
        "/repair prepare --latest",
        "/repair status repair-123",
        "/deploy verify candidate-1",
        "/deploy promote candidate-1 --deployment-id deploy-123",
        "/deploy rollback deploy-123",
    ],
)
async def test_operational_commands_bypass_research_executor(
    tmp_path: Path, command: str
) -> None:
    workspace = create_workspace(root=tmp_path)
    router, output = make_router(tmp_path, workspace)
    bridge = MagicMock()
    bridge.execute.return_value = "operation completed"
    router._operational_bridge = bridge

    await router.route(command)

    bridge.execute.assert_called_once_with(command)
    router._command_executor.execute.assert_not_called()
    output.show_command_result.assert_called_once_with(command, "operation completed")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "command",
    [
        "/logs show --latest",
        "/repair start repair-123",
        "/deploy status deploy-123",
    ],
)
async def test_unsupported_operational_commands_render_inline_message(
    tmp_path: Path, command: str
) -> None:
    workspace = create_workspace(root=tmp_path)
    router, output = make_router(tmp_path, workspace)
    bridge = MagicMock()
    bridge.is_supported.return_value = False
    router._operational_bridge = bridge

    await router.route(command)

    bridge.execute.assert_not_called()
    router._command_executor.execute.assert_not_called()
    output.show_error.assert_called_once()
    assert "Unsupported" in output.show_error.call_args.args[0]


@pytest.mark.asyncio
async def test_unsupported_operational_command_records_redacted_failure(
    tmp_path: Path,
) -> None:
    workspace = create_workspace(root=tmp_path)
    router, _ = make_router(tmp_path, workspace)
    run_context = RunContext(
        run_id="tui-operational-unsupported",
        surface="tui",
        actor="test",
        log_root=tmp_path,
    )
    from vnalpha.observability.context import init_run_context

    with patch(
        "vnalpha.observability.context.make_run_context", return_value=run_context
    ):
        init_run_context("tui", actor="test", log_root=tmp_path)
    set_correlation_id("unset")

    await router.route("/logs show api_key=super-secret")

    records = [
        json.loads(line)
        for line in run_context.commands_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [record["event_type"] for record in records] == [
        "COMMAND_STARTED",
        "COMMAND_FAILED",
    ]
    assert all(record["correlation_id"] not in {"", "unset"} for record in records)
    assert "super-secret" not in run_context.commands_path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_research_command_lifecycle_redacts_raw_arguments(tmp_path: Path) -> None:
    workspace = create_workspace(root=tmp_path)
    router, _ = make_router(tmp_path, workspace)
    run_context = RunContext(
        run_id="tui-research-redaction",
        surface="tui",
        actor="test",
        log_root=tmp_path,
    )
    from vnalpha.observability.context import init_run_context

    with patch(
        "vnalpha.observability.context.make_run_context", return_value=run_context
    ):
        init_run_context("tui", actor="test", log_root=tmp_path)
    set_correlation_id("unset")

    await router.route("/scan api_key=super-secret")

    records = [
        json.loads(line)
        for line in run_context.commands_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [record["event_type"] for record in records] == [
        "COMMAND_STARTED",
        "COMMAND_SUCCEEDED",
    ]
    assert all(record["correlation_id"] not in {"", "unset"} for record in records)
    assert "super-secret" not in run_context.commands_path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_research_command_result_failure_records_failed_lifecycle(
    tmp_path: Path,
) -> None:
    workspace = create_workspace(root=tmp_path)
    router, _ = make_router(tmp_path, workspace)
    router._command_executor.execute.return_value = CommandResult(
        status="FAILED",
        title="data",
        summary="No required OHLCV symbol completed.",
    )
    run_context = RunContext(
        run_id="tui-research-failure-result",
        surface="tui",
        actor="test",
        log_root=tmp_path,
    )
    from vnalpha.observability.context import init_run_context

    with patch(
        "vnalpha.observability.context.make_run_context", return_value=run_context
    ):
        init_run_context("tui", actor="test", log_root=tmp_path)
    set_correlation_id("unset")

    await router.route("/data download ohlcv FPT")

    records = [
        json.loads(line)
        for line in run_context.commands_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [record["event_type"] for record in records] == [
        "COMMAND_STARTED",
        "COMMAND_FAILED",
    ]
    assert records[-1]["status"] == "FAILED"
    assert records[-1]["exit_code"] == 1


@pytest.mark.asyncio
async def test_operational_command_lifecycle_captures_exception(tmp_path: Path) -> None:
    workspace = create_workspace(root=tmp_path)
    router, _ = make_router(tmp_path, workspace)
    bridge = MagicMock()
    bridge.execute.side_effect = RuntimeError("operation failed")
    router._operational_bridge = bridge
    run_context = RunContext(
        run_id="tui-operational-failure",
        surface="tui",
        actor="test",
        log_root=tmp_path,
    )
    from vnalpha.observability.context import init_run_context

    with patch(
        "vnalpha.observability.context.make_run_context", return_value=run_context
    ):
        init_run_context("tui", actor="test", log_root=tmp_path)

    await router.route("/logs errors --latest")

    records = [
        json.loads(line)
        for line in run_context.commands_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [record["event_type"] for record in records] == [
        "COMMAND_STARTED",
        "COMMAND_FAILED",
    ]
    errors = [
        json.loads(line)
        for line in run_context.errors_path.read_text(encoding="utf-8").splitlines()
    ]
    assert errors[-1]["error_type"] == "RuntimeError"


@pytest.mark.asyncio
async def test_operational_command_lifecycle_redacts_success_arguments(
    tmp_path: Path,
) -> None:
    workspace = create_workspace(root=tmp_path)
    router, _ = make_router(tmp_path, workspace)
    bridge = MagicMock()
    bridge.execute.return_value = "operation completed"
    router._operational_bridge = bridge
    run_context = RunContext(
        run_id="tui-operational-redaction",
        surface="tui",
        actor="test",
        log_root=tmp_path,
    )
    from vnalpha.observability.context import init_run_context

    with patch(
        "vnalpha.observability.context.make_run_context", return_value=run_context
    ):
        init_run_context("tui", actor="test", log_root=tmp_path)
    set_correlation_id("unset")

    await router.route("/logs errors --latest api_key=super-secret")

    records = [
        json.loads(line)
        for line in run_context.commands_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [record["event_type"] for record in records] == [
        "COMMAND_STARTED",
        "COMMAND_SUCCEEDED",
    ]
    assert all(record["correlation_id"] not in {"", "unset"} for record in records)
    assert "super-secret" not in run_context.commands_path.read_text(encoding="utf-8")


def test_router_close_closes_command_connection_once(tmp_path: Path) -> None:
    workspace = create_workspace(root=tmp_path)
    router, _ = make_router(tmp_path, workspace)
    connection = MagicMock()
    router._command_conn = connection

    router.close()
    router.close()

    connection.close.assert_called_once_with()
    assert router._command_conn is None


def test_executor_setup_closes_connection_when_migration_fails(tmp_path: Path) -> None:
    from vnalpha.tui.input_router import TuiInputRouter
    from vnalpha.tui.widgets.output_stream import OutputStream

    connection = MagicMock()
    output = MagicMock(spec=OutputStream)
    with patch.object(TuiInputRouter, "_setup_controller"):
        with patch(
            "vnalpha.warehouse.connection.get_connection", return_value=connection
        ):
            with patch(
                "vnalpha.warehouse.migrations.run_migrations",
                side_effect=RuntimeError("migration failed"),
            ):
                router = TuiInputRouter(
                    output_stream=output,
                    target_date="2026-07-10",
                    workspace=create_workspace(root=tmp_path),
                )

    connection.close.assert_called_once_with()
    assert router._command_conn is None
    assert router._command_executor is None


def test_executor_setup_retains_migrated_in_memory_connection(tmp_path: Path) -> None:
    from vnalpha.tui.input_router import TuiInputRouter
    from vnalpha.tui.widgets.output_stream import OutputStream

    connection = MagicMock()
    output = MagicMock(spec=OutputStream)
    with patch.object(TuiInputRouter, "_setup_controller"):
        with patch(
            "vnalpha.warehouse.connection.get_connection", return_value=connection
        ):
            with patch("vnalpha.warehouse.migrations.run_migrations") as migrations:
                router = TuiInputRouter(
                    output_stream=output,
                    target_date="2026-07-10",
                    workspace=create_workspace(root=tmp_path),
                )

    migrations.assert_called_once_with(conn=connection)
    assert router._command_conn is connection
    assert router._command_executor is not None
