from __future__ import annotations

import duckdb
import pytest
from pydantic import ValidationError

from vnalpha.sandbox.contracts import SandboxOutputSchema
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations

_OVERLONG_CHART_PATH = f"output/charts/{'a' * 1_025}.png"


def test_output_schema_rejects_overlong_optional_artifact_path() -> None:
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
                    {
                        "kind": "chart",
                        "path": _OVERLONG_CHART_PATH,
                        "media_type": "image/png",
                    },
                )
            }
        )


def test_database_rejects_overlong_optional_artifact_path() -> None:
    with in_memory_connection() as conn:
        run_migrations(conn=conn)

        with pytest.raises(duckdb.ConstraintException):
            _ = conn.execute(
                f"""
                INSERT INTO sandbox_job (
                    job_id, run_id, correlation_id, purpose, code_digest, status,
                    cpu_millis, memory_mb, timeout_seconds, network_enabled,
                    filesystem_policy_json, output_artifacts
                ) VALUES (
                    'path-length-job', 'path-length-run', 'path-length-correlation',
                    'evaluate', 'digest', 'queued', 1, 16, 1, FALSE,
                    '{{"approved_read_paths":[],"writable_output_directory":"output"}}',
                    [
                        {{'kind': 'result', 'path': 'output/result.json', 'media_type': 'application/json'}},
                        {{'kind': 'summary', 'path': 'output/summary.md', 'media_type': 'text/markdown'}},
                        {{'kind': 'chart', 'path': '{_OVERLONG_CHART_PATH}', 'media_type': 'image/png'}}
                    ]
                )
                """
            )
