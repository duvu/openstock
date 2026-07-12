from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from vnalpha.closed_loop.bundle import latest_failed_run
from vnalpha.closed_loop.models import (
    LifecycleState,
    PromotableArtifactType,
    RepairScope,
    SandboxAttemptResult,
)
from vnalpha.closed_loop.service import (
    ClosedLoopBoundaryError,
    ClosedLoopService,
    PromotionGateError,
)
from vnalpha.closed_loop.store import ClosedLoopStore


def _jsonl(path: Path, payload: dict[str, str]) -> None:
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _failed_run(tmp_path: Path) -> Path:
    run_dir = tmp_path / "runs" / "failed-run"
    run_dir.mkdir(parents=True)
    (run_dir / "environment.json").write_text(
        json.dumps({"run_id": "failed-run", "request": "build feature"}),
        encoding="utf-8",
    )
    _jsonl(
        run_dir / "errors.jsonl",
        {
            "event_type": "EXCEPTION_CAPTURED",
            "correlation_id": "corr-failed-run",
            "job_id": "job-failed",
            "session_id": "session-failed",
            "error_type": "ValueError",
            "error_message": "feature input failed",
            "stacktrace": "Traceback: feature input failed",
        },
    )
    _jsonl(
        run_dir / "commands.jsonl",
        {
            "event_type": "COMMAND_FAILED",
            "correlation_id": "corr-failed-run",
            "command": "/sandbox run feature",
            "status": "FAILED",
            "stdout_tail": "partial output",
            "stderr_tail": "feature input failed",
        },
    )
    (run_dir / "generated_code.py").write_text("result = 1\n", encoding="utf-8")
    (run_dir / "guard.json").write_text(json.dumps({"allowed": True}), encoding="utf-8")
    (run_dir / "input_references.json").write_text(
        json.dumps({"datasets": ["ohlcv:2026-07-10"]}), encoding="utf-8"
    )
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {"artifact_id": "artifact-failed", "artifact_type": "feature_definition"}
        ),
        encoding="utf-8",
    )
    (run_dir / "validation.json").write_text(
        json.dumps({"status": "FAILED"}), encoding="utf-8"
    )
    (run_dir / "stdout.txt").write_text("stdout\n", encoding="utf-8")
    (run_dir / "stderr.txt").write_text("stderr\n", encoding="utf-8")
    return run_dir


def _artifact(tmp_path: Path, artifact_id: str = "artifact-valid") -> Path:
    root = tmp_path / "research" / artifact_id
    root.mkdir(parents=True)
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "artifact_id": artifact_id,
                "artifact_type": PromotableArtifactType.FEATURE_DEFINITION.value,
                "outputs": ["result.json", "summary.md"],
            }
        ),
        encoding="utf-8",
    )
    (root / "result.json").write_text(json.dumps({"sample_size": 42}), encoding="utf-8")
    (root / "summary.md").write_text(
        "# Research result\n\nCaveats: offline and research-only.\n",
        encoding="utf-8",
    )
    (root / "lineage.json").write_text(
        json.dumps({"dataset": "ohlcv:2026-07-10"}), encoding="utf-8"
    )
    (root / "validation.json").write_text(
        json.dumps(
            {
                "quality_status": {"status": "PASS"},
                "caveats": ["research-only"],
                "sandbox_execution_passed": True,
                "output_schema_passed": True,
                "artifact_manifest_passed": True,
                "read_only_boundary_passed": True,
            }
        ),
        encoding="utf-8",
    )
    (root / "execution.json").write_text(
        json.dumps({"status": "succeeded"}), encoding="utf-8"
    )
    (root / "generated_code.py").write_text("result = 1\n", encoding="utf-8")
    return root


def test_prepare_packages_complete_bundle_and_lifecycle(tmp_path: Path) -> None:
    store = ClosedLoopStore(tmp_path)
    service = ClosedLoopService(store)

    bundle = service.prepare_failed_run(_failed_run(tmp_path))

    persisted = store.load_bundle(bundle.repair_id)
    assert persisted.repair_id == bundle.repair_id
    assert persisted.correlation_id == "corr-failed-run"
    assert persisted.failed_job_id == "job-failed"
    assert persisted.generated_code == "result = 1\n"
    assert persisted.static_guard_result["allowed"] is True
    assert persisted.input_dataset_references == ("ohlcv:2026-07-10",)
    assert store.current_lifecycle(bundle.repair_id).state is LifecycleState.PACKAGE
    assert "REPAIR_BUNDLE_CREATED" in store.event_types(bundle.repair_id)


def test_latest_failed_run_ignores_a_newer_successful_run(tmp_path: Path) -> None:
    failed = _failed_run(tmp_path)
    successful = tmp_path / "runs" / "successful-run"
    successful.mkdir(parents=True)
    _jsonl(
        successful / "commands.jsonl",
        {"event_type": "COMMAND_SUCCEEDED", "status": "SUCCESS"},
    )
    newest = failed.stat().st_mtime + 10
    os.utime(successful, (newest, newest))
    assert latest_failed_run(tmp_path) == failed


def test_repair_proposal_rejects_execution_scope(tmp_path: Path) -> None:
    store = ClosedLoopStore(tmp_path)
    service = ClosedLoopService(store)
    bundle = service.prepare_failed_run(_failed_run(tmp_path))

    proposal = service.propose(
        bundle.repair_id,
        scope=RepairScope.SANDBOX_RESEARCH_CODE,
        patch="broker.place_order(symbol='FPT')",
    )

    assert proposal.accepted is False
    assert "trading" in (proposal.rejection_reason or "").lower()
    assert "REPAIR_PROPOSAL_CREATED" in store.event_types(bundle.repair_id)
    assert store.current_lifecycle(bundle.repair_id).state is LifecycleState.REJECTED


class _FailingSandboxRunner:
    is_sandbox = True

    def run(self, bundle, proposal, attempt: int) -> SandboxAttemptResult:
        return SandboxAttemptResult(
            passed=False,
            stdout=f"attempt {attempt}",
            stderr="still failing",
            error_trace="Traceback: still failing",
        )


class _LocalRunner:
    is_sandbox = False

    def run(self, bundle, proposal, attempt: int) -> SandboxAttemptResult:
        return SandboxAttemptResult(passed=True)


class _SecretSandboxRunner:
    is_sandbox = True

    def run(self, bundle, proposal, attempt: int) -> SandboxAttemptResult:
        return SandboxAttemptResult(
            passed=False,
            stdout="token=secret-value",
            stderr="authorization=secret-header",
            error_trace="password=secret-password",
        )


def test_repair_attempt_output_is_redacted_by_default(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("VNALPHA_LOG_CONTENT_MODE", raising=False)
    store = ClosedLoopStore(tmp_path)
    service = ClosedLoopService(store)
    bundle = service.prepare_failed_run(_failed_run(tmp_path))
    service.propose(bundle.repair_id)

    service.apply(bundle.repair_id, attempt=1, runner=_SecretSandboxRunner())

    attempt = store.list_attempts(bundle.repair_id)[0]
    assert "secret-value" not in attempt.stdout
    assert "[REDACTED]" in attempt.stdout


def test_repair_loop_is_bounded_and_persists_terminal_failure(tmp_path: Path) -> None:
    store = ClosedLoopStore(tmp_path)
    service = ClosedLoopService(store, max_attempts=2)
    bundle = service.prepare_failed_run(_failed_run(tmp_path))
    proposal = service.propose(bundle.repair_id)

    first = service.apply(bundle.repair_id, attempt=1, runner=_FailingSandboxRunner())
    second = service.apply(bundle.repair_id, attempt=2, runner=_FailingSandboxRunner())

    assert first.passed is False
    assert second.passed is False
    assert len(store.list_attempts(bundle.repair_id)) == 2
    assert store.current_lifecycle(bundle.repair_id).state is LifecycleState.FAILED
    with pytest.raises(ClosedLoopBoundaryError, match="maximum repair attempts"):
        service.apply(bundle.repair_id, attempt=3, runner=_FailingSandboxRunner())
    assert proposal.repair_id == bundle.repair_id


def test_repair_attempt_limit_can_be_configured_from_environment(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("VNALPHA_MAX_REPAIR_ATTEMPTS", "4")
    assert ClosedLoopService(ClosedLoopStore(tmp_path)).max_attempts == 4


def test_repair_loop_rejects_non_sandbox_runner(tmp_path: Path) -> None:
    store = ClosedLoopStore(tmp_path)
    service = ClosedLoopService(store)
    bundle = service.prepare_failed_run(_failed_run(tmp_path))
    service.propose(bundle.repair_id)

    with pytest.raises(ClosedLoopBoundaryError, match="sandbox"):
        service.apply(bundle.repair_id, attempt=1, runner=_LocalRunner())


def test_validation_gate_requires_all_research_evidence(tmp_path: Path) -> None:
    store = ClosedLoopStore(tmp_path)
    service = ClosedLoopService(store)
    artifact_root = _artifact(tmp_path)

    report = service.validate("artifact-valid", artifact_root=artifact_root)

    assert report.passed is True
    assert {check.name for check in report.checks} == {
        "static_guard",
        "sandbox_execution",
        "output_schema",
        "artifact_manifest",
        "lineage",
        "quality_status",
        "caveats",
        "read_only_boundary",
    }
    assert store.load_validation_report("artifact-valid").passed is True


def test_validation_fails_when_lineage_or_caveats_are_missing(tmp_path: Path) -> None:
    store = ClosedLoopStore(tmp_path)
    service = ClosedLoopService(store)
    artifact_root = _artifact(tmp_path)
    (artifact_root / "lineage.json").unlink()
    (artifact_root / "validation.json").write_text(
        json.dumps({"quality_status": {"status": "PASS"}}), encoding="utf-8"
    )
    (artifact_root / "summary.md").write_text("# Result\n", encoding="utf-8")

    report = service.validate("artifact-valid", artifact_root=artifact_root)

    assert report.passed is False
    assert report.check("lineage").passed is False
    assert report.check("caveats").passed is False


def test_deploy_verify_promote_and_rollback_are_research_only(tmp_path: Path) -> None:
    store = ClosedLoopStore(tmp_path)
    service = ClosedLoopService(store)
    artifact_root = _artifact(tmp_path)
    service.validate("artifact-valid", artifact_root=artifact_root)

    verification = service.verify(
        "artifact-valid",
        artifact_root=artifact_root,
        candidate_type=PromotableArtifactType.FEATURE_DEFINITION,
        deployment_id="deployment-1",
    )
    promoted = service.promote("artifact-valid", deployment_id="deployment-1")
    rolled_back = service.rollback("deployment-1", reason="validation review")

    assert verification.passed is True
    assert promoted.status == "PROMOTED"
    assert rolled_back.status == "ROLLED_BACK"
    assert store.event_types("artifact-valid")[-2:] == [
        "RESEARCH_ARTIFACT_PROMOTED",
        "RESEARCH_ARTIFACT_ROLLED_BACK",
    ]


def test_deploy_promotion_requires_validation_evidence(tmp_path: Path) -> None:
    store = ClosedLoopStore(tmp_path)
    service = ClosedLoopService(store)

    with pytest.raises(PromotionGateError, match="validation"):
        service.promote("artifact-unvalidated", deployment_id="deployment-2")


def test_deploy_verify_rejects_candidate_type_mismatch(tmp_path: Path) -> None:
    store = ClosedLoopStore(tmp_path)
    service = ClosedLoopService(store)
    artifact_root = _artifact(tmp_path)
    service.validate("artifact-valid", artifact_root=artifact_root)

    verification = service.verify(
        "artifact-valid",
        artifact_root=artifact_root,
        candidate_type=PromotableArtifactType.PATTERN_SCANNER_DEFINITION,
    )

    assert verification.passed is False
