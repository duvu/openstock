from __future__ import annotations

from pathlib import Path

import pytest

from vnalpha.observability.context import RunContext
from vnalpha.sandbox.artifact_manifest import SandboxArtifactManifest
from vnalpha.sandbox.artifact_writer import SandboxArtifactWriter
from vnalpha.sandbox.contracts import SandboxFilesystemPolicy, SandboxOutputSchema
from vnalpha.sandbox.models import (
    SandboxCorrelationId,
    SandboxJob,
    SandboxJobId,
    SandboxResourceLimits,
    SandboxRunId,
)
from vnalpha.sandbox.output_validation import SandboxOutputValidator
from vnalpha.sandbox.storage import SandboxArtifactStorage


def _job() -> SandboxJob:
    return SandboxJob(
        job_id=SandboxJobId("job-001"),
        run_id=SandboxRunId("run-001"),
        purpose="evaluate a reference dataset",
        code="import math\nresult = math.sqrt(9)\n",
        correlation_id=SandboxCorrelationId("correlation-001"),
        resource_limits=SandboxResourceLimits(
            cpu_millis=100, memory_mb=64, timeout_seconds=30
        ),
        network_enabled=False,
        filesystem_policy=SandboxFilesystemPolicy(),
    )


def _storage(tmp_path: Path) -> SandboxArtifactStorage:
    return SandboxArtifactStorage(
        RunContext(run_id="run-001", surface="test", actor="pytest", log_root=tmp_path),
        SandboxJobId("job-001"),
    )


def _finalize(
    writer: SandboxArtifactWriter, storage: SandboxArtifactStorage
) -> SandboxArtifactManifest:
    _ = storage.write_atomic_bytes(
        "output/result.json",
        b'{"artifacts":[],"schema_version":1,"summary":"done"}\n',
    )
    _ = storage.write_atomic_bytes("output/summary.md", b"# done\n")
    validation = SandboxOutputValidator(storage).validate(SandboxOutputSchema())
    return writer.persist_validation_and_manifest(validation, SandboxOutputSchema())


def test_persist_guard_requires_persisted_request_and_matching_digest(
    tmp_path: Path,
) -> None:
    from vnalpha.sandbox.artifact_writer import (
        SandboxArtifactWriter,
        SandboxArtifactWriterStateError,
    )
    from vnalpha.sandbox.static_guard import SandboxStaticGuard

    # Given
    job = _job()
    evidence = SandboxStaticGuard.evaluate(job.code)
    with _storage(tmp_path) as storage:
        writer = SandboxArtifactWriter(storage)

        # When / Then
        with pytest.raises(SandboxArtifactWriterStateError):
            writer.persist_guard(evidence)
        assert not (storage.job_dir / "guard.json").exists()
