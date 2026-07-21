from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vnalpha.tui.clipboard import (
    ClipboardPort,
    ClipboardReceipt,
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
