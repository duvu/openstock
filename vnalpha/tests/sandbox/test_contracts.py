from __future__ import annotations

import pytest
from pydantic import ValidationError


def test_filesystem_policy_canonicalizes_approved_relative_read_paths() -> None:
    from vnalpha.sandbox.contracts import SandboxFilesystemPolicy

    policy = SandboxFilesystemPolicy.model_validate(
        {"approved_read_paths": ("inputs/candidate.json", "data/prices.parquet")}
    )

    assert policy.approved_read_paths == (
        "inputs/candidate.json",
        "data/prices.parquet",
    )
    assert policy.writable_directory == "output"


@pytest.mark.parametrize(
    "path",
    (
        "/secrets.txt",
        "C:\\secrets.txt",
        "../secrets.txt",
        "output/result.json",
    ),
)
def test_filesystem_policy_rejects_unsafe_or_output_overlapping_read_paths(
    path: str,
) -> None:
    from vnalpha.sandbox.contracts import SandboxFilesystemPolicy

    with pytest.raises(ValidationError):
        _ = SandboxFilesystemPolicy.model_validate({"approved_read_paths": (path,)})


def test_output_schema_defaults_require_result_and_summary_artifacts() -> None:
    from vnalpha.sandbox.contracts import SandboxOutputSchema

    schema = SandboxOutputSchema()

    assert tuple(
        (artifact.path, artifact.media_type) for artifact in schema.artifacts
    ) == (
        ("output/result.json", "application/json"),
        ("output/summary.md", "text/markdown"),
    )


@pytest.mark.parametrize(
    "payload",
    (
        {"approved_read_paths": ("inputs/a.json", "inputs/a.json")},
        {"approved_read_paths": ("inputs/./a.json",)},
    ),
)
def test_filesystem_policy_rejects_duplicate_or_noncanonical_read_paths(
    payload: dict[str, tuple[str, ...]],
) -> None:
    from vnalpha.sandbox.contracts import SandboxFilesystemPolicy

    with pytest.raises(ValidationError):
        _ = SandboxFilesystemPolicy.model_validate(payload)


@pytest.mark.parametrize("path", (".", "inputs\\candidate.json"))
def test_filesystem_policy_rejects_noncanonical_posix_read_paths(path: str) -> None:
    from vnalpha.sandbox.contracts import (
        ApprovedReadPath as ApprovedInputPath,
    )
    from vnalpha.sandbox.contracts import (
        SandboxFilesystemPolicy,
    )

    with pytest.raises(ValidationError):
        _ = SandboxFilesystemPolicy.model_validate(
            {"approved_read_paths": (ApprovedInputPath(path),)}
        )


@pytest.mark.parametrize(
    "artifact",
    (
        {"kind": "result", "path": "output/result.json", "media_type": ""},
        {
            "kind": "binary",
            "path": "output/data.bin",
            "media_type": "application/octet-stream",
        },
        {"kind": "chart", "path": "output/chart.png", "media_type": "image/png"},
        {"kind": "table", "path": "output/table/data.csv", "media_type": "text/csv"},
    ),
)
def test_output_schema_rejects_invalid_or_out_of_scope_artifacts(
    artifact: dict[str, str],
) -> None:
    from vnalpha.sandbox.contracts import SandboxOutputSchema

    with pytest.raises(ValidationError):
        _ = SandboxOutputSchema.model_validate(
            {
                "artifacts": (
                    {
                        "kind": "result",
                        "path": "output/result.json",
                        "media_type": "application/json",
                    },
                    {
                        "kind": "summary",
                        "path": "output/summary.md",
                        "media_type": "text/markdown",
                    },
                    artifact,
                )
            }
        )


def test_output_schema_accepts_unique_chart_and_table_artifacts_under_their_directories() -> (
    None
):
    from vnalpha.sandbox.contracts import SandboxOutputSchema

    schema = SandboxOutputSchema.model_validate(
        {
            "artifacts": (
                {
                    "kind": "result",
                    "path": "output/result.json",
                    "media_type": "application/json",
                },
                {
                    "kind": "summary",
                    "path": "output/summary.md",
                    "media_type": "text/markdown",
                },
                {
                    "kind": "chart",
                    "path": "output/charts/price.png",
                    "media_type": "image/png",
                },
                {
                    "kind": "table",
                    "path": "output/tables/prices.csv",
                    "media_type": "text/csv",
                },
            )
        }
    )

    assert tuple(artifact.path for artifact in schema.artifacts[2:]) == (
        "output/charts/price.png",
        "output/tables/prices.csv",
    )


def test_output_schema_requires_the_canonical_result_and_summary_artifacts() -> None:
    from vnalpha.sandbox.contracts import SandboxOutputSchema

    with pytest.raises(ValidationError):
        _ = SandboxOutputSchema.model_validate(
            {
                "artifacts": (
                    {
                        "kind": "result",
                        "path": "output/result.json",
                        "media_type": "application/json",
                    },
                )
            }
        )


def test_request_binds_filesystem_policy_and_output_schema_to_the_job() -> None:
    from vnalpha.sandbox.models import SandboxJobId, SandboxJobRequest, SandboxRunId

    request = SandboxJobRequest.model_validate(
        {
            "purpose": "evaluate",
            "code": "result = 1",
            "correlation_id": "contracts-42",
            "resource_limits": {
                "cpu_millis": 500,
                "memory_mb": 128,
                "timeout_seconds": 10,
            },
            "approved_input_paths": ("inputs/candidate.json",),
        }
    )

    job = request.into_job(
        job_id=SandboxJobId("job-001"), run_id=SandboxRunId("run-001")
    )

    assert job.filesystem_policy.approved_read_paths == ("inputs/candidate.json",)
    assert tuple(artifact.path for artifact in job.output_schema.artifacts) == (
        "output/result.json",
        "output/summary.md",
    )
