from __future__ import annotations

import duckdb
import pytest
from pydantic import ValidationError

from vnalpha.sandbox.contracts import SandboxOutputSchema


def _insert_sandbox_row(
    conn: duckdb.DuckDBPyConnection,
    filesystem_policy_json: str | None,
) -> None:
    _ = conn.execute(
        """
        INSERT INTO sandbox_job (
            job_id, run_id, correlation_id, purpose, code_digest, status,
            cpu_millis, memory_mb, timeout_seconds, network_enabled,
            filesystem_policy_json, output_artifacts
        ) VALUES ('job-001', 'run-001', 'contracts-42', 'evaluate', 'digest',
                  'queued', 1, 16, 1, FALSE, ?, ?)
        """,
        [
            filesystem_policy_json,
            [
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
            ],
        ],
    )


def test_output_schema_rejects_more_than_32_artifacts() -> None:
    artifacts = (
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
        *tuple(
            {
                "kind": "chart",
                "path": f"output/charts/chart-{index}.png",
                "media_type": "image/png",
            }
            for index in range(31)
        ),
    )

    with pytest.raises(ValidationError):
        _ = SandboxOutputSchema.model_validate({"artifacts": artifacts})
