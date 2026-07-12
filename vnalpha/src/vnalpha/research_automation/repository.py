"""Warehouse persistence for research automation metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Final

import duckdb

from vnalpha.research_automation.models import (
    DatasetRef,
    OfflineEventStudy,
    PatternScan,
    ResearchArtifact,
    ResearchArtifactStatus,
    ResearchArtifactLifecycleState,
    ResearchArtifactType,
    ResearchExperiment,
    ResearchFeature,
    ResearchHypothesis,
)


class ResearchAutomationPersistenceError(ValueError):
    """Research artifact persistence boundary error."""


class ResearchAutomationRepository:
    """Persist research-automation metadata for later audit and reuse."""

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn

    def save_artifact(self, artifact: ResearchArtifact) -> None:
        self._upsert_artifact(artifact)

    def get_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(_GET_ARTIFACT_SQL, [artifact_id]).fetchone()
        if row is None:
            return None
        return _artifact_payload(row)

    def list(self, limit: int | None = None) -> tuple[dict[str, Any], ...]:
        if limit is None:
            rows = self._conn.execute(
                _LIST_ARTIFACTS_SQL + " ORDER BY created_at_ts DESC"
            ).fetchall()
        else:
            rows = self._conn.execute(
                _LIST_ARTIFACTS_SQL + " ORDER BY created_at_ts DESC LIMIT ?",
                [limit],
            ).fetchall()
        return tuple(_artifact_payload(row) for row in rows)

    def list_by_correlation(
        self, correlation_id: str
    ) -> tuple[dict[str, Any], ...]:
        rows = self._conn.execute(
            _LIST_BY_CORRELATION_SQL, [correlation_id]
        ).fetchall()
        return tuple(_artifact_payload(row) for row in rows)

    def list_by_type(self, artifact_type: str) -> tuple[dict[str, Any], ...]:
        rows = self._conn.execute(_LIST_BY_TYPE_SQL, [artifact_type]).fetchall()
        return tuple(_artifact_payload(row) for row in rows)

    def list_by_lifecycle(
        self, lifecycle_state: ResearchArtifactLifecycleState | str
    ) -> tuple[dict[str, Any], ...]:
        state = _coerce_lifecycle_state(lifecycle_state)
        rows = self._conn.execute(
            _LIST_BY_LIFECYCLE_SQL, [state.value]
        ).fetchall()
        return tuple(_artifact_payload(row) for row in rows)

    def save_experiment(self, experiment: ResearchExperiment) -> None:
        self.save_artifact(experiment.artifact)
        self._upsert_definition(
            _UPSERT_EXPERIMENT_SQL,
            (
                experiment.artifact.artifact_id,
                experiment.definition,
                experiment.universe,
                experiment.start_date,
                experiment.end_date,
                experiment.horizon_sessions,
                _serialize_payload(
                    {
                        "definition": experiment.definition,
                        "universe": experiment.universe,
                        "start_date": str(experiment.start_date) if experiment.start_date else None,
                        "end_date": str(experiment.end_date) if experiment.end_date else None,
                        "horizon_sessions": experiment.horizon_sessions,
                    }
                ),
            ),
        )

    def save_feature(self, feature: ResearchFeature) -> None:
        self.save_artifact(feature.artifact)
        self._upsert_definition(
            _UPSERT_FEATURE_SQL,
            (
                feature.artifact.artifact_id,
                feature.feature_name,
                feature.feature_expression,
                feature.universe,
                _serialize_payload(
                    {
                        "feature_name": feature.feature_name,
                        "feature_expression": feature.feature_expression,
                        "universe": feature.universe,
                    }
                ),
            ),
        )

    def save_hypothesis(self, hypothesis: ResearchHypothesis) -> None:
        self.save_artifact(hypothesis.artifact)
        self._upsert_definition(
            _UPSERT_HYPOTHESIS_SQL,
            (
                hypothesis.artifact.artifact_id,
                hypothesis.hypothesis_text,
                hypothesis.outcome_metric,
                hypothesis.horizon_sessions,
                hypothesis.event_condition,
                _serialize_payload(
                    {
                        "hypothesis_text": hypothesis.hypothesis_text,
                        "outcome_metric": hypothesis.outcome_metric,
                        "horizon_sessions": hypothesis.horizon_sessions,
                        "event_condition": hypothesis.event_condition,
                    }
                ),
            ),
        )

    def mark_lifecycle_state(
        self, artifact_id: str, state: ResearchArtifactLifecycleState
    ) -> None:
        self._conn.execute(
            "UPDATE research_artifact SET lifecycle_state = ?, updated_at_ts = current_timestamp WHERE artifact_id = ?",
            [state.value, artifact_id],
        )

    def save_pattern_scan(self, scan: PatternScan) -> None:
        self.save_artifact(scan.artifact)
        self._upsert_definition(
            _UPSERT_PATTERN_SCAN_SQL,
            (
                scan.artifact.artifact_id,
                scan.pattern_description,
                scan.universe,
                scan.scan_date,
                _serialize_payload(
                    {
                        "pattern_description": scan.pattern_description,
                        "universe": scan.universe,
                        "scan_date": str(scan.scan_date) if scan.scan_date else None,
                    }
                ),
            ),
        )

    def save_offline_event_study(self, study: OfflineEventStudy) -> None:
        self.save_artifact(study.artifact)
        self._upsert_definition(
            _UPSERT_OFFLINE_EVENT_STUDY_SQL,
            (
                study.artifact.artifact_id,
                study.event_definition,
                study.entry_condition,
                study.exit_condition,
                study.horizon_sessions,
                study.universe,
                study.start_date,
                study.end_date,
                _serialize_payload(
                    {
                        "event_definition": study.event_definition,
                        "entry_condition": study.entry_condition,
                        "exit_condition": study.exit_condition,
                        "horizon_sessions": study.horizon_sessions,
                        "universe": study.universe,
                        "start_date": str(study.start_date) if study.start_date else None,
                        "end_date": str(study.end_date) if study.end_date else None,
                    }
                ),
            ),
        )

    def mark_status(self, artifact_id: str, status: ResearchArtifactStatus) -> None:
        self._conn.execute(
            "UPDATE research_artifact SET status = ? WHERE artifact_id = ?",
            [status.value, artifact_id],
        )
        if (
            self._conn.execute(
                "SELECT artifact_id FROM research_artifact WHERE artifact_id = ? LIMIT 1",
                [artifact_id],
            ).fetchone()
            is None
        ):
            raise ResearchAutomationPersistenceError(
                f"Unable to persist artifact status for {artifact_id!r}."
            )

    def _upsert_artifact(self, artifact: ResearchArtifact) -> None:
        outputs_payload = artifact.outputs.as_payload()
        self._conn.execute(
            _UPSERT_ARTIFACT_SQL,
            [
                artifact.artifact_id,
                artifact.artifact_type.value,
                artifact.name,
                artifact.purpose,
                artifact.created_at,
                artifact.created_by,
                artifact.run_id,
                artifact.correlation_id,
                artifact.status.value,
                artifact.sandbox_job_id,
                _serialize_payload(_dataset_refs_payload(artifact.input_datasets)),
                _serialize_payload(artifact.parameters),
                _serialize_payload(artifact.metrics),
                _serialize_payload(artifact.lineage),
                _serialize_payload(artifact.quality_status),
                _serialize_payload(tuple(artifact.caveats)),
                _serialize_payload(outputs_payload),
                _as_root_path(outputs_payload.get("manifest")),
                _as_path(outputs_payload.get("manifest")),
                _as_path(outputs_payload.get("result_json")),
                _as_path(outputs_payload.get("summary_md")),
                _as_path(outputs_payload.get("lineage_json")),
                _as_path(outputs_payload.get("validation_json")),
                _as_path(outputs_payload.get("reproducibility_manifest")),
                _as_path(outputs_payload.get("generated_code_path")),
                datetime.utcnow(),
                datetime.utcnow(),
            ],
        )

    def _upsert_definition(self, sql: str, args: tuple[Any, ...]) -> None:
        self._conn.execute(sql, args)


def _dataset_refs_payload(dataset_refs: tuple[DatasetRef, ...]) -> list[dict[str, Any]]:
    return [
        {
            "dataset_name": ref.dataset_name,
            "snapshot_id": ref.snapshot_id,
            "symbols": list(ref.symbols),
            "start_date": str(ref.start_date) if ref.start_date else None,
            "end_date": str(ref.end_date) if ref.end_date else None,
            "interval": ref.interval,
            "row_count": ref.row_count,
            "quality_status": dict(ref.quality_status),
        }
        for ref in dataset_refs
    ]


def _serialize_payload(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _coerce_lifecycle_state(
    value: ResearchArtifactLifecycleState | str,
) -> ResearchArtifactLifecycleState:
    if isinstance(value, ResearchArtifactLifecycleState):
        return value
    try:
        return ResearchArtifactLifecycleState(value)
    except ValueError:
        return ResearchArtifactLifecycleState.RUN


def _artifact_payload(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "artifact_id": row[0],
        "artifact_type": row[1],
        "name": row[2],
        "purpose": row[3],
        "created_at": row[4],
        "created_by": row[5],
        "run_id": row[6],
        "correlation_id": row[7],
        "status": row[8],
        "lifecycle_state": row[9],
        "sandbox_job_id": row[10],
        "related_experiment_id": row[11],
        "related_feature_id": row[12],
        "related_hypothesis_id": row[13],
        "related_pattern_id": row[14],
        "related_offline_event_study_id": row[15],
        "input_datasets_json": row[16],
        "parameters_json": row[17],
        "metrics_json": row[18],
        "lineage_json": row[19],
        "quality_status_json": row[20],
        "caveats_json": row[21],
        "outputs_json": row[22],
        "artifact_root_path": row[23],
        "manifest_path": row[24],
        "result_path": row[25],
        "summary_path": row[26],
        "lineage_path": row[27],
        "validation_path": row[28],
        "reproducibility_manifest_path": row[29],
        "generated_code_path": row[30],
        "created_at_ts": row[31],
        "updated_at_ts": row[32],
    }


def _as_root_path(value: str | None) -> str | None:
    if value is None:
        return None
    return str(Path(value).parent)


def _as_path(value: str | None) -> str | None:
    if value is None:
        return None
    return str(value)


_UPSERT_ARTIFACT_SQL = """
INSERT INTO research_artifact (
    artifact_id, artifact_type, name, purpose, created_at, created_by, run_id,
    correlation_id, status, lifecycle_state, sandbox_job_id,
    related_experiment_id, related_feature_id, related_hypothesis_id,
    related_pattern_id, related_offline_event_study_id,
    input_datasets_json,
    parameters_json, metrics_json, lineage_json, quality_status_json,
    caveats_json, outputs_json, artifact_root_path, manifest_path,
    result_path, summary_path, lineage_path, validation_path,
    reproducibility_manifest_path, generated_code_path, created_at_ts, updated_at_ts
) VALUES (
    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
) ON CONFLICT (artifact_id) DO UPDATE SET
    artifact_type = excluded.artifact_type,
    name = excluded.name,
    purpose = excluded.purpose,
    status = excluded.status,
    lifecycle_state = excluded.lifecycle_state,
    sandbox_job_id = excluded.sandbox_job_id,
    related_experiment_id = excluded.related_experiment_id,
    related_feature_id = excluded.related_feature_id,
    related_hypothesis_id = excluded.related_hypothesis_id,
    related_pattern_id = excluded.related_pattern_id,
    related_offline_event_study_id = excluded.related_offline_event_study_id,
    input_datasets_json = excluded.input_datasets_json,
    parameters_json = excluded.parameters_json,
    metrics_json = excluded.metrics_json,
    lineage_json = excluded.lineage_json,
    quality_status_json = excluded.quality_status_json,
    caveats_json = excluded.caveats_json,
    outputs_json = excluded.outputs_json,
    artifact_root_path = excluded.artifact_root_path,
    manifest_path = excluded.manifest_path,
    result_path = excluded.result_path,
    summary_path = excluded.summary_path,
    lineage_path = excluded.lineage_path,
    validation_path = excluded.validation_path,
    reproducibility_manifest_path = excluded.reproducibility_manifest_path,
    generated_code_path = excluded.generated_code_path,
    updated_at_ts = excluded.updated_at_ts
"""

_GET_ARTIFACT_SQL = """
SELECT
    artifact_id, artifact_type, name, purpose, created_at, created_by,
    run_id, correlation_id, status, lifecycle_state, sandbox_job_id,
    related_experiment_id, related_feature_id, related_hypothesis_id,
    related_pattern_id, related_offline_event_study_id,
    input_datasets_json, parameters_json, metrics_json, lineage_json,
    quality_status_json, caveats_json, outputs_json, artifact_root_path,
    manifest_path, result_path, summary_path, lineage_path, validation_path,
    reproducibility_manifest_path, generated_code_path, created_at_ts, updated_at_ts
FROM research_artifact
WHERE artifact_id = ?
"""

_LIST_ARTIFACTS_SQL = """
SELECT
    artifact_id, artifact_type, name, purpose, created_at, created_by,
    run_id, correlation_id, status, lifecycle_state, sandbox_job_id,
    related_experiment_id, related_feature_id, related_hypothesis_id,
    related_pattern_id, related_offline_event_study_id,
    input_datasets_json, parameters_json, metrics_json, lineage_json,
    quality_status_json, caveats_json, outputs_json, artifact_root_path,
    manifest_path, result_path, summary_path, lineage_path, validation_path,
    reproducibility_manifest_path, generated_code_path, created_at_ts, updated_at_ts
FROM research_artifact
"""

_LIST_BY_CORRELATION_SQL = _LIST_ARTIFACTS_SQL + "\nWHERE correlation_id = ?"

_LIST_BY_TYPE_SQL = _LIST_ARTIFACTS_SQL + "\nWHERE artifact_type = ?"

_LIST_BY_LIFECYCLE_SQL = _LIST_ARTIFACTS_SQL + "\nWHERE lifecycle_state = ?"

_UPSERT_EXPERIMENT_SQL = """
INSERT INTO research_experiment (
    artifact_id, definition, universe, start_date, end_date,
    horizon_sessions, definition_json
) VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (artifact_id) DO UPDATE SET
    definition = excluded.definition,
    universe = excluded.universe,
    start_date = excluded.start_date,
    end_date = excluded.end_date,
    horizon_sessions = excluded.horizon_sessions,
    definition_json = excluded.definition_json,
    updated_at_ts = current_timestamp
"""

_UPSERT_FEATURE_SQL = """
INSERT INTO research_feature (
    artifact_id, feature_name, feature_expression, universe, definition_json
) VALUES (?, ?, ?, ?, ?)
ON CONFLICT (artifact_id) DO UPDATE SET
    feature_name = excluded.feature_name,
    feature_expression = excluded.feature_expression,
    universe = excluded.universe,
    definition_json = excluded.definition_json,
    updated_at_ts = current_timestamp
"""

_UPSERT_HYPOTHESIS_SQL = """
INSERT INTO research_hypothesis (
    artifact_id, hypothesis_text, outcome_metric,
    horizon_sessions, event_condition, definition_json
) VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT (artifact_id) DO UPDATE SET
    hypothesis_text = excluded.hypothesis_text,
    outcome_metric = excluded.outcome_metric,
    horizon_sessions = excluded.horizon_sessions,
    event_condition = excluded.event_condition,
    definition_json = excluded.definition_json,
    updated_at_ts = current_timestamp
"""

_UPSERT_PATTERN_SCAN_SQL = """
INSERT INTO research_pattern_scan (
    artifact_id, pattern_description, universe, scan_date, definition_json
) VALUES (?, ?, ?, ?, ?)
ON CONFLICT (artifact_id) DO UPDATE SET
    pattern_description = excluded.pattern_description,
    universe = excluded.universe,
    scan_date = excluded.scan_date,
    definition_json = excluded.definition_json,
    updated_at_ts = current_timestamp
"""

_UPSERT_OFFLINE_EVENT_STUDY_SQL = """
INSERT INTO research_offline_event_study (
    artifact_id, event_definition, entry_condition, exit_condition,
    horizon_sessions, universe, start_date, end_date, definition_json
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (artifact_id) DO UPDATE SET
    event_definition = excluded.event_definition,
    entry_condition = excluded.entry_condition,
    exit_condition = excluded.exit_condition,
    horizon_sessions = excluded.horizon_sessions,
    universe = excluded.universe,
    start_date = excluded.start_date,
    end_date = excluded.end_date,
    definition_json = excluded.definition_json,
    updated_at_ts = current_timestamp
"""
