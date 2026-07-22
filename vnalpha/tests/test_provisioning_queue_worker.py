from __future__ import annotations

from pathlib import Path

import pytest

from tests.provisioning_queue_worker_control_scenarios import (
    assert_stage_control_boundaries,
)
from tests.provisioning_queue_worker_recovery_scenarios import (
    assert_worker_recovery_boundaries,
)
from tests.provisioning_queue_worker_runtime_scenarios import (
    assert_worker_runtime_boundaries,
)


def test_sequential_provisioning_worker_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert_worker_recovery_boundaries(tmp_path)
    assert_stage_control_boundaries(tmp_path, monkeypatch)
    assert_worker_runtime_boundaries(tmp_path)
