from __future__ import annotations

from datetime import date
from typing import Any

from vnalpha.research_automation.feature_service import FeatureAutomationService
from vnalpha.research_automation.study_service import ResearchStudyService
from vnalpha.research_automation.workflow_service import ResearchWorkflowService


def create_feature(conn, **kwargs: Any) -> dict[str, Any]:
    feature = FeatureAutomationService(conn).create(
        str(kwargs.get("definition", "")),
        universe=_optional_text(kwargs.get("universe")),
    )
    return _artifact_payload(feature.artifact)


def validate_feature(conn, **kwargs: Any) -> dict[str, Any]:
    validation = FeatureAutomationService(conn).validate(str(kwargs.get("feature", "")))
    return validation.as_payload()


def run_indicator(conn, **kwargs: Any) -> dict[str, Any]:
    outcome = ResearchWorkflowService(conn).indicator(
        str(kwargs.get("description", "")),
        universe=_optional_text(kwargs.get("universe")),
        start_date=_optional_date(kwargs.get("start_date")),
        end_date=_optional_date(kwargs.get("end_date")),
    )
    return _artifact_payload(outcome.artifact)


def scan_pattern(conn, **kwargs: Any) -> dict[str, Any]:
    outcome = ResearchWorkflowService(conn).pattern(
        str(kwargs.get("pattern", "")),
        universe=_optional_text(kwargs.get("universe")),
        scan_date=_optional_date(kwargs.get("date")),
    )
    return {
        **_artifact_payload(outcome.artifact),
        "candidates": [list(row) for row in outcome.rows],
    }


def test_hypothesis(conn, **kwargs: Any) -> dict[str, Any]:
    outcome = ResearchStudyService(conn).hypothesis(str(kwargs.get("hypothesis", "")))
    return {
        **_artifact_payload(outcome.artifact),
        "assumptions": list(outcome.assumptions),
    }


def run_event_study(conn, **kwargs: Any) -> dict[str, Any]:
    outcome = ResearchStudyService(conn).event_study(
        str(kwargs.get("event_condition", "")),
        horizon=int(kwargs.get("horizon", 10)),
        start_date=_optional_date(kwargs.get("start_date")),
        end_date=_optional_date(kwargs.get("end_date")),
    )
    return _artifact_payload(outcome.artifact)


def _artifact_payload(artifact) -> dict[str, Any]:
    return {
        "artifact_id": artifact.artifact_id,
        "artifact_type": artifact.artifact_type.value,
        "status": artifact.status.value,
        "metrics": dict(artifact.metrics),
        "caveats": list(artifact.caveats),
        "dataset_refs": [
            {
                "dataset_name": item.dataset_name,
                "snapshot_id": item.snapshot_id,
                "row_count": item.row_count,
            }
            for item in artifact.input_datasets
        ],
        "artifact_refs": list(artifact.outputs.as_payload().values()),
        "research_only": True,
    }


def _optional_text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _optional_date(value: Any) -> date | None:
    text = _optional_text(value)
    return date.fromisoformat(text) if text else None


__all__ = [
    "create_feature",
    "run_event_study",
    "run_indicator",
    "scan_pattern",
    "test_hypothesis",
    "validate_feature",
]
