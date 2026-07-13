from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import date, datetime
from typing import Any

from vnalpha.research_models.contracts import ResearchModel
from vnalpha.research_models.models import (
    ResearchAnswerAudit,
    ResearchScenarioPlan,
    SetupEvidenceSnapshot,
)

_EXECUTION_FIELD_NAMES = frozenset(
    {
        "account",
        "allocation",
        "broker",
        "execution",
        "margin",
        "order",
        "portfolio",
        "position",
        "transfer",
        "trade",
        "trading",
    }
)


class ResearchModelValidationError(ValueError):
    pass


def validate_research_model(model: ResearchModel) -> None:
    if not is_dataclass(model):
        raise ResearchModelValidationError("Research model must be a dataclass.")
    for field in fields(model):
        value = getattr(model, field.name)
        if field.name.endswith("_id") and not _is_nonempty(value):
            raise ResearchModelValidationError(f"{field.name} is required.")
        _reject_execution_fields(value, field.name)
    if hasattr(model, "as_of_date") and not isinstance(model.as_of_date, date):
        raise ResearchModelValidationError("as_of_date must be a date.")
    if not isinstance(model.created_at, datetime):
        raise ResearchModelValidationError("created_at must be a datetime.")
    if not _is_nonempty(model.correlation_id):
        raise ResearchModelValidationError("correlation_id is required.")
    if not isinstance(model, ResearchAnswerAudit):
        if not model.lineage:
            raise ResearchModelValidationError("lineage is required.")
        if not _is_nonempty(model.methodology_version):
            raise ResearchModelValidationError("methodology_version is required.")
        if not _is_nonempty(model.quality_status):
            raise ResearchModelValidationError("quality_status is required.")
        if not _is_nonempty(model.freshness):
            raise ResearchModelValidationError("freshness is required.")
    if isinstance(model, (ResearchScenarioPlan, SetupEvidenceSnapshot)):
        if not model.caveats:
            raise ResearchModelValidationError(
                "scenario and evidence records require caveats."
            )
    if isinstance(model, ResearchScenarioPlan):
        if model.policy_classification != "RESEARCH_ONLY":
            raise ResearchModelValidationError(
                "scenario policy_classification must be RESEARCH_ONLY."
            )


def _is_nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _reject_execution_fields(value: Any, path: str) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in _EXECUTION_FIELD_NAMES:
                raise ResearchModelValidationError(
                    f"Execution-oriented field is not allowed: {path}.{key}"
                )
            _reject_execution_fields(nested, f"{path}.{key}")
    elif isinstance(value, (tuple, list, set)):
        for index, nested in enumerate(value):
            _reject_execution_fields(nested, f"{path}[{index}]")


__all__ = ["ResearchModelValidationError", "validate_research_model"]
