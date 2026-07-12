from __future__ import annotations

import json
import os
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


def test_validate_accepts_declared_chart_and_table_in_schema_order(
    storage: SandboxArtifactStorage,
) -> None:
    # Given
    chart = _chart()
    table = _table()
    _write_required(
        storage,
        _result_bytes(
            artifacts=(("chart", str(chart.path)), ("table", str(table.path)))
        ),
    )
    _ = storage.write_atomic_bytes(str(chart.path), b"chart-bytes")
    _ = storage.write_atomic_bytes(str(table.path), b"table-bytes")

    # When
    outcome = _validate(storage, _schema(chart, table))

    # Then
    assert outcome.succeeded
    assert tuple(entry.path for entry in outcome.inventory) == (
        "output/result.json",
        "output/summary.md",
        "output/charts/chart.png",
        "output/tables/table.csv",
    )
    assert tuple(entry.media_type for entry in outcome.inventory) == (
        "application/json",
        "text/markdown",
        "image/png",
        "text/csv",
    )
    assert tuple(entry.byte_length for entry in outcome.inventory) == (
        len(
            _result_bytes(
                artifacts=(("chart", str(chart.path)), ("table", str(table.path)))
            )
        ),
        len(b"# Summary\n\nValidated output.\n"),
        len(b"chart-bytes"),
        len(b"table-bytes"),
    )


@pytest.mark.parametrize(
    "result",
    (
        b'{"schema_version":1,"schema_version":1,"summary":"x","artifacts":[]}',
        b'{"schema_version":NaN,"summary":"x","artifacts":[]}',
        b'{"schema_version":Infinity,"summary":"x","artifacts":[]}',
        b'{"schema_version":-Infinity,"summary":"x","artifacts":[]}',
        b"\xff",
        b"[]",
        b'{"summary":"x","artifacts":[]}',
        b'{"schema_version":2,"summary":"x","artifacts":[]}',
        b'{"schema_version":true,"summary":"x","artifacts":[]}',
        b'{"schema_version":1,"artifacts":[]}',
        b'{"schema_version":1,"summary":3,"artifacts":[]}',
        b'{"schema_version":1,"summary":"   ","artifacts":[]}',
        b'{"schema_version":1,"summary":"x"}',
        b'{"schema_version":1,"summary":"x","artifacts":{}}',
        json.dumps(
            {"schema_version": 1, "summary": "x" * 1_001, "artifacts": []}
        ).encode("utf-8"),
    ),
)
def test_validate_rejects_malformed_result_envelope(
    storage: SandboxArtifactStorage, result: bytes
) -> None:
    # Given
    _write_required(storage, result)

    # When
    outcome = _validate(storage, _schema())

    # Then
    assert not outcome.succeeded
    assert outcome.result is None
    assert outcome.evidence.artifact_path == "output/result.json"
    assert "output/result.json" in tuple(entry.path for entry in outcome.inventory)
    assert result not in outcome.evidence.to_json_bytes()


@pytest.mark.parametrize(
    "summary",
    (b"", b" \n\t ", b"\xff"),
)
def test_validate_rejects_blank_or_invalid_utf8_summary(
    storage: SandboxArtifactStorage, summary: bytes
) -> None:
    # Given
    _ = storage.write_atomic_bytes("output/result.json", _result_bytes())
    _ = storage.write_atomic_bytes("output/summary.md", summary)

    # When
    outcome = _validate(storage, _schema())

    # Then
    assert not outcome.succeeded
    assert outcome.evidence.artifact_path == "output/summary.md"


def test_validate_rejects_missing_summary(storage: SandboxArtifactStorage) -> None:
    # Given
    _ = storage.write_atomic_bytes("output/result.json", _result_bytes())

    # When
    outcome = _validate(storage, _schema())

    # Then
    assert not outcome.succeeded
    assert outcome.evidence.artifact_path == "output/summary.md"


def test_validate_rejects_missing_result(storage: SandboxArtifactStorage) -> None:
    # Given
    _ = storage.write_atomic_bytes("output/summary.md", b"summary")

    # When
    outcome = _validate(storage, _schema())

    # Then
    assert not outcome.succeeded
    assert outcome.evidence.artifact_path == "output/result.json"


@pytest.mark.parametrize(
    ("path", "content"),
    (
        ("output/result.json", b"x" * (1_048_576 + 1)),
        ("output/summary.md", b"x" * (262_144 + 1)),
    ),
)
def test_validate_rejects_oversized_required_artifact(
    storage: SandboxArtifactStorage, path: str, content: bytes
) -> None:
    # Given
    _write_required(storage)
    _ = storage.write_atomic_bytes(path, content)

    # When
    outcome = _validate(storage, _schema())

    # Then
    assert not outcome.succeeded
    assert outcome.evidence.artifact_path == path


@pytest.mark.parametrize("kind", ("result", "summary"))
def test_validate_rejects_required_kinds_as_references(
    storage: SandboxArtifactStorage, kind: str
) -> None:
    # Given
    _write_required(storage, _result_bytes(artifacts=((kind, "output/result.json"),)))

    # When
    outcome = _validate(storage, _schema())

    # Then
    assert not outcome.succeeded
    assert outcome.evidence.artifact_path == "output/result.json"


def test_validate_rejects_extra_reference_field(
    storage: SandboxArtifactStorage,
) -> None:
    # Given
    result = b'{"schema_version":1,"summary":"x","artifacts":[{"kind":"chart","path":"output/charts/chart.png","media_type":"image/png"}]}'
    _write_required(storage, result)

    # When
    outcome = _validate(storage, _schema())

    # Then
    assert not outcome.succeeded
    assert outcome.evidence.artifact_path == "output/result.json"


@pytest.mark.parametrize(
    "artifacts",
    (
        (("chart", "output/charts/undeclared.png"),),
        (("table", "output/charts/chart.png"),),
        (("chart", "output/charts/chart.png"), ("chart", "output/charts/chart.png")),
    ),
)
def test_validate_rejects_mismatched_duplicate_or_undeclared_references(
    storage: SandboxArtifactStorage, artifacts: tuple[tuple[str, str], ...]
) -> None:
    # Given
    chart = _chart()
    _write_required(storage, _result_bytes(artifacts=artifacts))
    _ = storage.write_atomic_bytes(str(chart.path), b"chart-bytes")

    # When
    outcome = _validate(storage, _schema(chart))

    # Then
    assert not outcome.succeeded
    assert outcome.evidence.artifact_path == "output/result.json"


def test_validate_rejects_missing_declared_optional_artifact(
    storage: SandboxArtifactStorage,
) -> None:
    # Given
    chart = _chart()
    _write_required(storage, _result_bytes(artifacts=(("chart", str(chart.path)),)))

    # When
    outcome = _validate(storage, _schema(chart))

    # Then
    assert not outcome.succeeded
    assert outcome.evidence.artifact_path == "output/charts/chart.png"


def test_validate_ignores_arbitrary_path_in_extra_research_field(
    storage: SandboxArtifactStorage,
) -> None:
    # Given
    result = b'{"schema_version":1,"summary":"validated result summary","artifacts":[],"research_path":"output/not-declared.bin"}'
    _write_required(storage, result)

    # When
    outcome = _validate(storage, _schema())

    # Then
    assert outcome.succeeded
    assert "output/not-declared.bin" not in tuple(
        entry.path for entry in outcome.inventory
    )


def test_validate_writes_stable_safe_evidence(storage: SandboxArtifactStorage) -> None:
    # Given
    malicious = (
        b'{"schema_version":1,"summary":"secret","artifacts":[],"bad":"/host/path"}'
    )
    _write_required(storage, malicious)

    # When
    outcome = _validate(storage, _schema())

    # Then
    evidence = outcome.evidence.to_json_bytes()
    assert evidence.endswith(b"\n")
    assert (
        evidence
        == b'{"artifact_path":null,"detail":"sandbox outputs satisfy the expected artifact contract","failure_code":null,"schema_version":1,"status":"succeeded","validated_paths":["output/result.json","output/summary.md"]}\n'
    )
    assert b"secret" not in evidence
    assert b"/host/path" not in evidence


def test_validate_stops_before_optional_reads_when_result_is_invalid(
    storage: SandboxArtifactStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given
    chart = _chart()
    _write_required(storage, b"not-json")
    called_paths: list[str] = []
    original_read = SandboxArtifactStorage.read_bounded_regular_file

    def record_read(
        instance: SandboxArtifactStorage, raw_path: str, *, max_bytes: int
    ) -> bytes:
        called_paths.append(raw_path)
        return original_read(instance, raw_path, max_bytes=max_bytes)

    monkeypatch.setattr(
        SandboxArtifactStorage, "read_bounded_regular_file", record_read
    )

    # When
    outcome = _validate(storage, _schema(chart))

    # Then
    assert not outcome.succeeded
    assert called_paths == ["output/result.json"]


def test_validate_rejects_symlink_and_special_optional_artifacts(
    storage: SandboxArtifactStorage, tmp_path: Path
) -> None:
    # Given
    chart = _chart()
    _write_required(storage, _result_bytes(artifacts=(("chart", str(chart.path)),)))
    output_dir = storage.ensure_directory("output/charts")
    outside = tmp_path / "outside.png"
    _ = outside.write_bytes(b"outside")
    (output_dir / "chart.png").symlink_to(outside)

    # When
    outcome = _validate(storage, _schema(chart))

    # Then
    assert not outcome.succeeded
    assert outcome.evidence.artifact_path == "output/charts/chart.png"

    # Given
    (output_dir / "chart.png").unlink()
    os.mkfifo(output_dir / "chart.png")

    # When
    special_outcome = _validate(storage, _schema(chart))

    # Then
    assert not special_outcome.succeeded
    assert special_outcome.evidence.artifact_path == "output/charts/chart.png"


def test_validate_rejects_oversized_optional_artifact(
    storage: SandboxArtifactStorage,
) -> None:
    # Given
    chart = _chart()
    _write_required(storage, _result_bytes(artifacts=(("chart", str(chart.path)),)))
    _ = storage.write_atomic_bytes(str(chart.path), b"x" * (10_485_760 + 1))

    # When
    outcome = _validate(storage, _schema(chart))

    # Then
    assert not outcome.succeeded
    assert outcome.evidence.artifact_path == "output/charts/chart.png"
