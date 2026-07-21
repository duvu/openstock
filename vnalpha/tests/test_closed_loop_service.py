from __future__ import annotations

import json
from pathlib import Path

from vnalpha.closed_loop.models import (
    LifecycleState,
    PromotableArtifactType,
    SandboxAttemptResult,
)
from vnalpha.closed_loop.service import (
    ClosedLoopService,
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
