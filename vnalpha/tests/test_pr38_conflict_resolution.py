from __future__ import annotations

from vnalpha.commands.models import (
    CommandStatus,
)
from vnalpha.tui.routing.status_adapter import StatusAdapter
from vnalpha.tui.runtime_status import RuntimeState
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
