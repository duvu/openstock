from __future__ import annotations

from vnalpha.commands.models import (
    CommandResult,
    CommandStatus,
    ResultArtifact,
)
from vnalpha.tui.routing.status_adapter import StatusAdapter
from vnalpha.tui.runtime_status import RuntimeState
from vnalpha.tui.workspace_context import (
    record_command_artifacts,
    refreshed_workspace_for_context_command,
)
from vnalpha.workspace_context.models import WorkspaceState


class _FakeStatusBar:
    def __init__(self) -> None:
        self.last_status = None

    def update_status(self, status) -> None:
        self.last_status = status


def _workspace() -> WorkspaceState:
    return WorkspaceState(
        workspace_id="ws-test",
        title="Test workspace",
        status="active",
        mode="general",
        created_at="2026-07-11T00:00:00+00:00",
        updated_at="2026-07-11T00:00:00+00:00",
    )


def test_status_adapter_maps_failed_result_to_error() -> None:
    bar = _FakeStatusBar()
    adapter = StatusAdapter(bar)

    adapter.command_result(CommandStatus.FAILED, "provider unavailable", [])

    assert bar.last_status is not None
    assert bar.last_status.state is RuntimeState.ERROR
    assert "provider unavailable" in bar.last_status.detail


def test_status_adapter_maps_empty_and_partial_to_warning() -> None:
    bar = _FakeStatusBar()
    adapter = StatusAdapter(bar)

    adapter.command_result(CommandStatus.EMPTY_RESULT, "No scores found", [])
    assert bar.last_status.state is RuntimeState.WARNING

    adapter.command_result(CommandStatus.PARTIAL, "Partial analysis", ["stale data"])
    assert bar.last_status.state is RuntimeState.WARNING
    assert "stale data" in bar.last_status.detail


def test_partial_command_artifacts_are_recorded(monkeypatch) -> None:
    recorded = []
    monkeypatch.setattr(
        "vnalpha.tui.workspace_context.record_artifact",
        lambda _workspace_state, artifact: recorded.append(artifact),
    )
    result = CommandResult(
        status=CommandStatus.PARTIAL,
        title="/explain FPT",
        artifacts=[ResultArtifact(name="analysis", data={"symbol": "FPT"})],
    )

    record_command_artifacts(_workspace(), result)

    assert len(recorded) == 1
    assert recorded[0].metadata == {"name": "analysis"}


def test_empty_command_artifacts_are_ignored(monkeypatch) -> None:
    recorded = []
    monkeypatch.setattr(
        "vnalpha.tui.workspace_context.record_artifact",
        lambda _workspace_state, artifact: recorded.append(artifact),
    )
    result = CommandResult(
        status=CommandStatus.EMPTY_RESULT,
        title="/compare FPT MWG",
        artifacts=[ResultArtifact(name="unexpected", data={})],
    )

    record_command_artifacts(_workspace(), result)

    assert recorded == []


def test_model_override_commands_refresh_workspace(monkeypatch) -> None:
    workspace = _workspace()
    monkeypatch.setattr(
        "vnalpha.tui.workspace_context.load_active_workspace",
        lambda: workspace,
    )

    refreshed = refreshed_workspace_for_context_command(
        "/model use reasoning", CommandStatus.SUCCESS
    )

    assert refreshed is workspace
    assert (
        refreshed_workspace_for_context_command(
            "/model use reasoning", CommandStatus.PARTIAL
        )
        is None
    )
