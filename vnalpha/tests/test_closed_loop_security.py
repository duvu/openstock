from __future__ import annotations

from pathlib import Path

import pytest

from tests.test_closed_loop_service import _artifact, _failed_run
from vnalpha.closed_loop.models import PromotableArtifactType, SandboxAttemptResult
from vnalpha.closed_loop.service import (
    ClosedLoopBoundaryError,
    ClosedLoopService,
    PromotionGateError,
)
from vnalpha.closed_loop.store import ClosedLoopStore
from vnalpha.observability.redaction import redact_dict, redact_str


class _CrashRunner:
    is_sandbox = True

    def run(self, bundle, proposal, attempt: int) -> SandboxAttemptResult:
        raise RuntimeError("runner crashed")


def test_closed_loop_store_rejects_traversal_ids(tmp_path: Path) -> None:
    store = ClosedLoopStore(tmp_path)

    with pytest.raises(ClosedLoopBoundaryError):
        store.load_bundle("../outside")


def test_runner_failure_is_persisted_and_terminal_retry_is_rejected(
    tmp_path: Path,
) -> None:
    store = ClosedLoopStore(tmp_path)
    service = ClosedLoopService(store, max_attempts=1)
    bundle = service.prepare_failed_run(_failed_run(tmp_path))
    service.propose(bundle.repair_id)

    attempt = service.apply(bundle.repair_id, attempt=1, runner=_CrashRunner())

    assert attempt.passed is False
    assert "runner crashed" in attempt.error_trace
    assert store.current_lifecycle(bundle.repair_id).state.value == "FAILED"
    with pytest.raises(ClosedLoopBoundaryError, match="terminal"):
        service.apply(bundle.repair_id, attempt=1, runner=_CrashRunner())


def test_promotion_rechecks_artifact_digest_and_boundary(tmp_path: Path) -> None:
    store = ClosedLoopStore(tmp_path)
    service = ClosedLoopService(store)
    artifact_root = _artifact(tmp_path)
    service.validate("artifact-valid", artifact_root=artifact_root)
    verification = service.verify(
        "artifact-valid",
        artifact_root=artifact_root,
        candidate_type=PromotableArtifactType.FEATURE_DEFINITION,
        deployment_id="deployment-safe",
    )
    assert verification.passed is True

    (artifact_root / "generated_code.py").write_text(
        "client.buy('FPT')\n", encoding="utf-8"
    )

    with pytest.raises(PromotionGateError, match="changed"):
        service.promote("artifact-valid", deployment_id="deployment-safe")


def test_default_redaction_recurses_through_lists_and_json_text() -> None:
    payload = redact_dict(
        {"nested": [{"token": "secret-value"}, '{"password":"secret"}']},
        mode="redacted",
    )

    assert "secret-value" not in str(payload)
    assert "secret" not in redact_str('{"token":"secret"}', mode="redacted")
