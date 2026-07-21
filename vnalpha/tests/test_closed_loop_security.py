from __future__ import annotations

from pathlib import Path

import pytest

from vnalpha.closed_loop.models import SandboxAttemptResult
from vnalpha.closed_loop.service import (
    ClosedLoopBoundaryError,
)
from vnalpha.closed_loop.store import ClosedLoopStore


class _CrashRunner:
    is_sandbox = True

    def run(self, bundle, proposal, attempt: int) -> SandboxAttemptResult:
        raise RuntimeError("runner crashed")


def test_closed_loop_store_rejects_traversal_ids(tmp_path: Path) -> None:
    store = ClosedLoopStore(tmp_path)

    with pytest.raises(ClosedLoopBoundaryError):
        store.load_bundle("../outside")
