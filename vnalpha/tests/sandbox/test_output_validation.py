from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from vnalpha.observability.context import RunContext
from vnalpha.sandbox.contracts import (
    ExpectedArtifactPath,
    SandboxExpectedArtifact,
    SandboxOutputSchema,
)
from vnalpha.sandbox.models import SandboxJobId
from vnalpha.sandbox.storage import SandboxArtifactStorage


def _schema(*optional: SandboxExpectedArtifact) -> SandboxOutputSchema:
    return SandboxOutputSchema(artifacts=SandboxOutputSchema().artifacts + optional)


def _chart(path: str = "output/charts/chart.png") -> SandboxExpectedArtifact:
    return SandboxExpectedArtifact(
        kind="chart", path=ExpectedArtifactPath(path), media_type="image/png"
    )


def _table(path: str = "output/tables/table.csv") -> SandboxExpectedArtifact:
    return SandboxExpectedArtifact(
        kind="table", path=ExpectedArtifactPath(path), media_type="text/csv"
    )


def _result_bytes(
    *,
    artifacts: tuple[tuple[str, str], ...] = (),
    extra: bool = False,
) -> bytes:
    payload: dict[str, int | str | list[dict[str, str]] | dict[str, bool]] = {
        "schema_version": 1,
        "summary": "validated result summary",
        "artifacts": [{"kind": kind, "path": path} for kind, path in artifacts],
    }
    if extra:
        payload["research"] = {"accepted": True}
    return json.dumps(payload).encode("utf-8")


@pytest.fixture
def storage(tmp_path: Path) -> Iterator[SandboxArtifactStorage]:
    run_context = RunContext(
        run_id="run-001", surface="verify", actor="test", log_root=tmp_path
    )
    artifact_storage = SandboxArtifactStorage(run_context, SandboxJobId("job-001"))
    yield artifact_storage
    artifact_storage.close()


def _write_required(
    storage: SandboxArtifactStorage, result: bytes | None = None
) -> None:
    _ = storage.write_atomic_bytes("output/result.json", result or _result_bytes())
    _ = storage.write_atomic_bytes(
        "output/summary.md", b"# Summary\n\nValidated output.\n"
    )


def _validate(storage: SandboxArtifactStorage, schema: SandboxOutputSchema):
    from vnalpha.sandbox.output_validation import SandboxOutputValidator

    return SandboxOutputValidator(storage).validate(schema)


def test_validate_accepts_required_output_and_extra_research_fields(
    storage: SandboxArtifactStorage,
) -> None:
    # Given
    _write_required(storage, _result_bytes(extra=True))

    # When
    outcome = _validate(storage, _schema())

    # Then
    assert outcome.succeeded
    assert outcome.result is not None
    assert tuple(entry.path for entry in outcome.inventory) == (
        "output/result.json",
        "output/summary.md",
    )
