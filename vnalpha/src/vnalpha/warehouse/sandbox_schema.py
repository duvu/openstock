from __future__ import annotations

from typing import Final

from vnalpha.sandbox.contracts import (
    MAX_APPROVED_READ_PATHS,
    MAX_APPROVED_READ_PATHS_JSON_LENGTH,
    MAX_OUTPUT_ARTIFACT_PATH_LENGTH,
    MAX_OUTPUT_ARTIFACTS,
)
from vnalpha.sandbox.models import (
    MAX_SANDBOX_CORRELATION_ID_LENGTH,
    MAX_SANDBOX_JOB_DETAIL_LENGTH,
    MAX_SANDBOX_PURPOSE_LENGTH,
)

SANDBOX_ARTIFACT_KIND_DDL: Final = """
CREATE TYPE IF NOT EXISTS sandbox_artifact_kind AS ENUM ('result', 'summary', 'chart', 'table')
"""

_ARTIFACT_MEMBER_CHECKS: Final = "\n        AND ".join(
    f"(length(artifacts) < {index} OR sandbox_artifact_is_valid(list_extract(artifacts, {index})))"
    for index in range(1, MAX_OUTPUT_ARTIFACTS + 1)
)

SANDBOX_ARTIFACT_VALIDATION_DDL: Final = f"""
CREATE MACRO IF NOT EXISTS sandbox_artifact_is_valid(artifact) AS (
    coalesce(
        artifact IS NOT NULL
        AND artifact.kind IS NOT NULL
        AND artifact.path IS NOT NULL
        AND artifact.media_type IS NOT NULL
        AND length(artifact.path) > 0
        AND length(artifact.path) <= {MAX_OUTPUT_ARTIFACT_PATH_LENGTH}
        AND NOT starts_with(artifact.path, '/')
        AND instr(artifact.path, '\\') = 0
        AND NOT list_contains(string_split(artifact.path, '/'), '')
        AND NOT list_contains(string_split(artifact.path, '/'), '.')
        AND NOT list_contains(string_split(artifact.path, '/'), '..')
        AND CASE artifact.kind
            WHEN 'result'::sandbox_artifact_kind THEN
                artifact.path = 'output/result.json'
                AND artifact.media_type = 'application/json'
            WHEN 'summary'::sandbox_artifact_kind THEN
                artifact.path = 'output/summary.md'
                AND artifact.media_type = 'text/markdown'
            WHEN 'chart'::sandbox_artifact_kind THEN
                starts_with(artifact.path, 'output/charts/')
                AND length(artifact.path) > length('output/charts/')
                AND artifact.media_type = 'image/png'
            WHEN 'table'::sandbox_artifact_kind THEN
                starts_with(artifact.path, 'output/tables/')
                AND length(artifact.path) > length('output/tables/')
                AND artifact.media_type = 'text/csv'
            ELSE FALSE
        END,
        FALSE
    )
)
"""

SANDBOX_ARTIFACT_LIST_VALIDATION_DDL: Final = f"""
CREATE MACRO IF NOT EXISTS sandbox_artifacts_are_valid(artifacts) AS (
    {_ARTIFACT_MEMBER_CHECKS}
)
"""

_SANDBOX_JOB_TABLE_DDL: Final = f"""
CREATE TABLE IF NOT EXISTS sandbox_job (
    job_id VARCHAR PRIMARY KEY,
    run_id VARCHAR NOT NULL,
    correlation_id VARCHAR NOT NULL CHECK (
        length(correlation_id) BETWEEN 1 AND {MAX_SANDBOX_CORRELATION_ID_LENGTH}
    ),
    purpose VARCHAR NOT NULL CHECK (
        length(purpose) BETWEEN 1 AND {MAX_SANDBOX_PURPOSE_LENGTH}
    ),
    code_digest VARCHAR NOT NULL,
    status VARCHAR NOT NULL CHECK (status IN (
        'queued', 'validating', 'running', 'succeeded',
        'failed', 'rejected', 'cancelled'
    )),
    cpu_millis INTEGER NOT NULL CHECK (cpu_millis > 0),
    memory_mb INTEGER NOT NULL CHECK (memory_mb > 0),
    timeout_seconds INTEGER NOT NULL CHECK (timeout_seconds > 0),
    network_enabled BOOLEAN NOT NULL CHECK (network_enabled = FALSE),
    filesystem_policy_json VARCHAR NOT NULL CHECK (
        length(filesystem_policy_json) <= {MAX_APPROVED_READ_PATHS_JSON_LENGTH}
        AND json_valid(filesystem_policy_json)
        AND json_type(json_extract(filesystem_policy_json, '$.approved_read_paths')) = 'ARRAY'
        AND json_array_length(json_extract(filesystem_policy_json, '$.approved_read_paths')) <= {MAX_APPROVED_READ_PATHS}
        AND json_extract_string(filesystem_policy_json, '$.writable_output_directory') = 'output'
        AND filesystem_policy_json NOT LIKE '%..%'
    ),
    output_artifacts STRUCT(kind sandbox_artifact_kind, path VARCHAR, media_type VARCHAR)[] NOT NULL,
    CHECK (
        length(output_artifacts) BETWEEN 2 AND {MAX_OUTPUT_ARTIFACTS}
        AND sandbox_artifacts_are_valid(output_artifacts)
        AND length(list_distinct(output_artifacts))
            = length(output_artifacts)
        AND list_contains(output_artifacts, {{
            'kind': 'result'::sandbox_artifact_kind,
            'path': 'output/result.json',
            'media_type': 'application/json'
        }})
        AND list_contains(output_artifacts, {{
            'kind': 'summary'::sandbox_artifact_kind,
            'path': 'output/summary.md',
            'media_type': 'text/markdown'
        }})
    ),
    result_summary VARCHAR,
    rejection_reason VARCHAR,
    failure_reason VARCHAR,
    CHECK (result_summary IS NULL OR (
        length(trim(result_summary)) BETWEEN 1 AND {MAX_SANDBOX_JOB_DETAIL_LENGTH}
    )),
    CHECK (rejection_reason IS NULL OR (
        length(trim(rejection_reason)) BETWEEN 1 AND {MAX_SANDBOX_JOB_DETAIL_LENGTH}
    )),
    CHECK (failure_reason IS NULL OR (
        length(trim(failure_reason)) BETWEEN 1 AND {MAX_SANDBOX_JOB_DETAIL_LENGTH}
    )),
    created_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp
)
"""

SANDBOX_DDL: Final[tuple[str, ...]] = (
    SANDBOX_ARTIFACT_KIND_DDL,
    SANDBOX_ARTIFACT_VALIDATION_DDL,
    SANDBOX_ARTIFACT_LIST_VALIDATION_DDL,
    _SANDBOX_JOB_TABLE_DDL,
    "CREATE INDEX IF NOT EXISTS sandbox_job_correlation_idx ON sandbox_job (correlation_id)",
)


def sandbox_job_table_ddl(table_name: str) -> str:
    return _SANDBOX_JOB_TABLE_DDL.replace("sandbox_job (", f"{table_name} (")
