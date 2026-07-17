from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vnalpha.tui.clipboard import (
    ClipboardError,
    ClipboardPort,
    ClipboardReceipt,
    TextualClipboardPort,
    prepare_clipboard_text,
)
from vnalpha.workspace_context.lifecycle import create_workspace


@dataclass
class FakeClipboard:
    copied: list[str] = field(default_factory=list)
    failure: Exception | None = None

    def copy(self, text: str) -> ClipboardReceipt:
        if self.failure is not None:
            raise self.failure
        self.copied.append(text)
        return ClipboardReceipt(confirmed=True, detail="test clipboard confirmed")


def _router(tmp_path: Path, clipboard: ClipboardPort | None):
    from vnalpha.tui.input_router import TuiInputRouter
    from vnalpha.tui.widgets.output_stream import OutputStream
    from vnalpha.tui.widgets.status_bar import StatusBar

    output = MagicMock(spec=OutputStream)
    output.latest_result_text.return_value = "latest result"
    output.transcript_text.return_value = "bounded transcript"
    output.current_artifact_id.return_value = "analysis:FPT:2026-07-15"
    status_bar = MagicMock(spec=StatusBar)
    with patch.object(TuiInputRouter, "_setup_controller"):
        with patch.object(TuiInputRouter, "_setup_executor"):
            router = TuiInputRouter(
                output_stream=output,
                status_bar=status_bar,
                workspace=create_workspace(root=tmp_path),
                clipboard=clipboard,
                log_text_provider=lambda: "filtered logs",
            )
    router._command_executor = MagicMock()
    router._record_workspace_input = MagicMock()
    return router, output, status_bar


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("/copy result", "latest result"),
        ("/copy output", "bounded transcript"),
        ("/copy logs", "filtered logs"),
        ("/copy artifact-id", "analysis:FPT:2026-07-15"),
    ],
)
async def test_copy_commands_are_local_and_run_before_busy_gate(
    tmp_path: Path, command: str, expected: str
) -> None:
    clipboard = FakeClipboard()
    router, output, status_bar = _router(tmp_path, clipboard)
    router._busy = True

    await router.route(command)

    assert clipboard.copied == [expected]
    router._command_executor.execute.assert_not_called()
    router._record_workspace_input.assert_not_called()
    output.show_warning.assert_not_called()
    status = status_bar.update_status.call_args.args[0]
    assert status.label == f"Copied {command.removeprefix('/copy ')}"
    assert status.detail == f"{len(expected)} characters"


@pytest.mark.asyncio
async def test_copy_missing_target_is_visible_and_non_mutating(tmp_path: Path) -> None:
    clipboard = FakeClipboard()
    router, output, status_bar = _router(tmp_path, clipboard)
    output.latest_result_text.return_value = ""

    await router.route("/copy result")

    assert clipboard.copied == []
    output.show_warning.assert_not_called()
    status = status_bar.update_status.call_args.args[0]
    assert status.state.value == "WARNING"
    assert status.detail == "Nothing to copy for result."


@pytest.mark.asyncio
async def test_copy_transport_failure_is_reported_truthfully(tmp_path: Path) -> None:
    clipboard = FakeClipboard(failure=ClipboardError("terminal clipboard unavailable"))
    router, output, status_bar = _router(tmp_path, clipboard)

    await router.route("/copy result")

    assert clipboard.copied == []
    assert output.latest_result_text.call_count == 1
    status = status_bar.update_status.call_args.args[0]
    assert status.state.value == "WARNING"
    assert status.detail == "Copy failed: clipboard backend error"


@pytest.mark.asyncio
async def test_unexpected_copy_transport_failure_is_bounded_and_redacted(
    tmp_path: Path,
) -> None:
    clipboard = FakeClipboard(failure=ValueError("api_key=super-secret"))
    router, _, status_bar = _router(tmp_path, clipboard)

    await router.route("/copy result")

    status = status_bar.update_status.call_args.args[0]
    assert status.state.value == "WARNING"
    assert status.detail == "Copy failed: clipboard backend error"
    assert "super-secret" not in status.detail


@pytest.mark.asyncio
async def test_copy_without_clipboard_port_never_claims_success(tmp_path: Path) -> None:
    router, _, status_bar = _router(tmp_path, None)

    await router.route("/copy result")

    status = status_bar.update_status.call_args.args[0]
    assert status.state.value == "WARNING"
    assert status.detail == "Copy failed: clipboard access is unavailable"


def test_textual_clipboard_reports_unconfirmed_transport_submission() -> None:
    copied: list[str] = []
    port = TextualClipboardPort(copied.append)

    receipt = port.copy("safe text")

    assert copied == ["safe text"]
    assert receipt.confirmed is False
    assert receipt.detail == "terminal confirmation unavailable"


@pytest.mark.asyncio
async def test_unconfirmed_textual_transport_never_claims_copy_success(
    tmp_path: Path,
) -> None:
    submitted: list[str] = []
    router, _, status_bar = _router(
        tmp_path,
        TextualClipboardPort(submitted.append),
    )

    await router.route("/copy result")

    assert submitted == ["latest result"]
    status = status_bar.update_status.call_args.args[0]
    assert status.label == "Clipboard request sent for result"
    assert status.detail.endswith("terminal confirmation unavailable")


def test_clipboard_defense_redacts_quoted_nested_secret_text() -> None:
    prepared, truncated = prepare_clipboard_text(
        "context={'credentials': {'api_key': 'live-secret'}}"
    )

    assert truncated is False
    assert "live-secret" not in prepared
    assert "[REDACTED]" in prepared
