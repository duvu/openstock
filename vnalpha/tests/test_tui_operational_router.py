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
