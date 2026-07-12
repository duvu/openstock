"""Domain models for research automation artifacts and definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, Mapping
from uuid import uuid4

_MAX_SYMBOL_LENGTH: Final = 24
_MAX_IDENTIFIER_LENGTH: Final = 64
_SYMBOL_CHARS: Final = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-.")
_ARTIFACT_ID_PREFIX: Final = "ra"


class ResearchArtifactStatus(str, Enum):
    """Lifecycle states for every research artifact."""

    CREATED = "created"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REJECTED = "rejected"
    VALIDATED = "validated"
    PROMOTED = "promoted"


class ResearchArtifactLifecycleState(str, Enum):
    """Canonical closed-loop lifecycle states."""

    RUN = "RUN"
    OBSERVE = "OBSERVE"
    PACKAGE = "PACKAGE"
    AI_FIX = "AI_FIX"
    VALIDATE = "VALIDATE"
    PROMOTE_READY = "PROMOTE_READY"
    PROMOTED = "PROMOTED"
    REJECTED = "REJECTED"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED = "FAILED"


class ResearchArtifactType(str, Enum):
    """Research artifact kinds supported by this slice."""

    INDICATOR_EXPERIMENT = "indicator_experiment"
    FEATURE = "feature"
    HYPOTHESIS_TEST = "hypothesis_test"
    PATTERN_SCAN = "pattern_scan"
    OFFLINE_EVENT_STUDY = "offline_event_study"


def now_utc() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(timezone.utc)


def new_research_artifact_id(prefix: str = _ARTIFACT_ID_PREFIX) -> str:
    """Return a safe artifact identifier for filesystem layouts."""

    value = f"{prefix}-{uuid4().hex}"
    return value[:_MAX_IDENTIFIER_LENGTH]


def _normalize_symbol(value: str) -> str:
    normalized = value.upper().strip()
    if not normalized:
        raise ValueError("symbol list entries must be non-empty")
    if len(normalized) > _MAX_SYMBOL_LENGTH:
        raise ValueError(f"symbol {value!r} exceeds {_MAX_SYMBOL_LENGTH} characters")
    if not set(normalized).issubset(_SYMBOL_CHARS):
        raise ValueError(f"symbol {value!r} contains unsupported characters")
    return normalized


def _normalize_identifier(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    if ".." in normalized:
        raise ValueError(f"{field_name} must not contain '..'")
    if len(normalized) > _MAX_IDENTIFIER_LENGTH:
        raise ValueError(f"{field_name} exceeds {_MAX_IDENTIFIER_LENGTH} characters")
    return normalized


def _normalize_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(value))


def _normalize_tuple(value: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value))


@dataclass(frozen=True, slots=True)
class DatasetRef:
    """A canonical dataset reference used for reproducibility evidence."""

    dataset_name: str
    snapshot_id: str | None
    symbols: tuple[str, ...]
    start_date: date | None = None
    end_date: date | None = None
    interval: str = "1D"
    row_count: int | None = None
    quality_status: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "dataset_name", _normalize_identifier(self.dataset_name, "dataset_name"))
        object.__setattr__(
            self,
            "symbols",
            tuple(
                _normalize_symbol(item)
                for item in _normalize_tuple(tuple(s.strip() for s in self.symbols))
            ),
        )
        if self.end_date is not None and self.start_date is not None:
            if self.end_date < self.start_date:
                raise ValueError("start_date must be before or equal to end_date")
        if self.row_count is not None and self.row_count < 0:
            raise ValueError("row_count must be non-negative")
        object.__setattr__(self, "interval", _normalize_identifier(self.interval, "interval"))
        object.__setattr__(self, "quality_status", _normalize_mapping(self.quality_status))


@dataclass(frozen=True, slots=True)
class ArtifactOutputs:
    """Physical artifact locations produced by one workflow run."""

    manifest: Path
    result_json: Path
    summary_md: Path
    lineage_json: Path
    validation_json: Path
    reproducibility_manifest: Path | None = None
    generated_code_path: Path | None = None
    metrics_csv: Path | None = None
    candidates_csv: Path | None = None
    charts: tuple[Path, ...] = ()
    extra_paths: Mapping[str, Path] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "charts", tuple(self.charts))
        object.__setattr__(self, "extra_paths", _normalize_mapping(self.extra_paths))

    def as_payload(self) -> dict[str, Any]:
        """Serialize output paths for JSON persistence layers."""

        return {
            "manifest": str(self.manifest),
            "result_json": str(self.result_json),
            "summary_md": str(self.summary_md),
            "lineage_json": str(self.lineage_json),
            "validation_json": str(self.validation_json),
            "reproducibility_manifest": _maybe_path(self.reproducibility_manifest),
            "generated_code_path": _maybe_path(self.generated_code_path),
            "metrics_csv": _maybe_path(self.metrics_csv),
            "candidates_csv": _maybe_path(self.candidates_csv),
            "charts": [str(chart) for chart in self.charts],
            "extra_paths": {
                key: str(path) for key, path in sorted(self.extra_paths.items())
            },
        }


_LIFECYCLE_FROM_LEGACY: Final = {
    ResearchArtifactStatus.CREATED: ResearchArtifactLifecycleState.RUN,
    ResearchArtifactStatus.RUNNING: ResearchArtifactLifecycleState.OBSERVE,
    ResearchArtifactStatus.SUCCEEDED: ResearchArtifactLifecycleState.PROMOTE_READY,
    ResearchArtifactStatus.VALIDATED: ResearchArtifactLifecycleState.VALIDATE,
    ResearchArtifactStatus.PROMOTED: ResearchArtifactLifecycleState.PROMOTED,
    ResearchArtifactStatus.REJECTED: ResearchArtifactLifecycleState.REJECTED,
    ResearchArtifactStatus.FAILED: ResearchArtifactLifecycleState.FAILED,
}


def _coerce_lifecycle_state(
    value: ResearchArtifactLifecycleState | str | None,
    legacy_status: ResearchArtifactStatus,
) -> ResearchArtifactLifecycleState:
    if value is None:
        return _LIFECYCLE_FROM_LEGACY.get(
            legacy_status,
            ResearchArtifactLifecycleState.RUN,
        )
    if isinstance(value, ResearchArtifactLifecycleState):
        return value
    try:
        return ResearchArtifactLifecycleState(value)
    except ValueError:
        return _LIFECYCLE_FROM_LEGACY.get(
            legacy_status,
            ResearchArtifactLifecycleState.RUN,
        )


@dataclass(frozen=True, slots=True)
class ResearchArtifact:
    """Canonical metadata required for all research automation outputs."""

    artifact_id: str
    artifact_type: ResearchArtifactType
    name: str
    purpose: str
    created_at: datetime
    created_by: str
    correlation_id: str
    status: ResearchArtifactStatus
    input_datasets: tuple[DatasetRef, ...]
    lifecycle_state: ResearchArtifactLifecycleState = ResearchArtifactLifecycleState.RUN
    sandbox_job_id: str | None
    parameters: Mapping[str, Any]
    metrics: Mapping[str, Any]
    lineage: Mapping[str, Any]
    quality_status: Mapping[str, Any]
    caveats: tuple[str, ...]
    outputs: ArtifactOutputs
    run_id: str | None = None
    related_experiment_id: str | None = None
    related_feature_id: str | None = None
    related_hypothesis_id: str | None = None
    related_pattern_id: str | None = None
    related_offline_event_study_id: str | None = None

    def __post_init__(self) -> None:
        artifact_type = ResearchArtifactType(self.artifact_type)
        status = ResearchArtifactStatus(self.status)
        object.__setattr__(self, "artifact_type", artifact_type)
        object.__setattr__(self, "status", status)
        object.__setattr__(
            self,
            "lifecycle_state",
            _coerce_lifecycle_state(self.lifecycle_state, status),
        )
        object.__setattr__(self, "artifact_id", _normalize_identifier(self.artifact_id, "artifact_id"))
        object.__setattr__(self, "name", _normalize_identifier(self.name, "name"))
        object.__setattr__(self, "purpose", self.purpose.strip())
        if not self.purpose:
            raise ValueError("purpose must be non-empty")
        object.__setattr__(self, "created_by", _normalize_identifier(self.created_by, "created_by"))
        object.__setattr__(self, "correlation_id", _normalize_identifier(self.correlation_id, "correlation_id"))
        if self.created_at.tzinfo is None:
            object.__setattr__(self, "created_at", self.created_at.replace(tzinfo=timezone.utc))
        object.__setattr__(self, "input_datasets", tuple(self.input_datasets))
        object.__setattr__(self, "parameters", _normalize_mapping(self.parameters))
        object.__setattr__(self, "metrics", _normalize_mapping(self.metrics))
        object.__setattr__(self, "lineage", _normalize_mapping(self.lineage))
        object.__setattr__(self, "quality_status", _normalize_mapping(self.quality_status))
        object.__setattr__(self, "caveats", _normalize_tuple(self.caveats))
        if self.sandbox_job_id is not None:
            object.__setattr__(
                self,
                "sandbox_job_id",
                _normalize_identifier(self.sandbox_job_id, "sandbox_job_id"),
            )
        if self.related_experiment_id is not None:
            object.__setattr__(
                self,
                "related_experiment_id",
                _normalize_identifier(self.related_experiment_id, "related_experiment_id"),
            )
        if self.related_feature_id is not None:
            object.__setattr__(
                self,
                "related_feature_id",
                _normalize_identifier(self.related_feature_id, "related_feature_id"),
            )
        if self.related_hypothesis_id is not None:
            object.__setattr__(
                self,
                "related_hypothesis_id",
                _normalize_identifier(self.related_hypothesis_id, "related_hypothesis_id"),
            )
        if self.related_pattern_id is not None:
            object.__setattr__(
                self,
                "related_pattern_id",
                _normalize_identifier(self.related_pattern_id, "related_pattern_id"),
            )
        if self.related_offline_event_study_id is not None:
            object.__setattr__(
                self,
                "related_offline_event_study_id",
                _normalize_identifier(
                    self.related_offline_event_study_id,
                    "related_offline_event_study_id",
                ),
            )
        if self.run_id is not None:
            object.__setattr__(self, "run_id", _normalize_identifier(self.run_id, "run_id"))
        if self.created_by == "":
            raise ValueError("created_by must be non-empty")


@dataclass(frozen=True, slots=True)
class ResearchExperiment:
    """Definition and run metadata for a research experiment."""

    artifact: ResearchArtifact
    definition: str
    universe: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    horizon_sessions: int | None = None

    def __post_init__(self) -> None:
        definition = self.definition.strip()
        if not definition:
            raise ValueError("experiment definition must be non-empty")
        if self.horizon_sessions is not None and self.horizon_sessions <= 0:
            raise ValueError("horizon_sessions must be positive")
        object.__setattr__(self, "definition", definition)
        if self.universe is not None:
            object.__setattr__(self, "universe", _normalize_identifier(self.universe, "universe"))
        if self.end_date is not None and self.start_date is not None:
            if self.end_date < self.start_date:
                raise ValueError("experiment start_date must be before or equal end_date")


@dataclass(frozen=True, slots=True)
class ResearchFeature:
    """Feature definition to be computed/reused in future research steps."""

    artifact: ResearchArtifact
    feature_name: str
    feature_expression: str
    universe: str | None = None

    def __post_init__(self) -> None:
        feature_name = self.feature_name.strip().upper()
        expression = self.feature_expression.strip()
        if not feature_name:
            raise ValueError("feature_name must be non-empty")
        if not expression:
            raise ValueError("feature_expression must be non-empty")
        object.__setattr__(self, "feature_name", feature_name)
        object.__setattr__(self, "feature_expression", expression)
        if self.universe is not None:
            object.__setattr__(self, "universe", _normalize_identifier(self.universe, "universe"))


@dataclass(frozen=True, slots=True)
class ResearchHypothesis:
    """A hypothesis test definition and metadata."""

    artifact: ResearchArtifact
    hypothesis_text: str
    outcome_metric: str | None = None
    horizon_sessions: int | None = None
    event_condition: str | None = None

    def __post_init__(self) -> None:
        hypothesis_text = self.hypothesis_text.strip()
        if not hypothesis_text:
            raise ValueError("hypothesis_text must be non-empty")
        if self.horizon_sessions is not None and self.horizon_sessions <= 0:
            raise ValueError("horizon_sessions must be positive")
        object.__setattr__(self, "hypothesis_text", hypothesis_text)
        if self.outcome_metric is not None:
            object.__setattr__(self, "outcome_metric", self.outcome_metric.strip())
        if self.event_condition is not None:
            object.__setattr__(self, "event_condition", self.event_condition.strip())


@dataclass(frozen=True, slots=True)
class PatternScan:
    """Pattern-scanning workflow and definition metadata."""

    artifact: ResearchArtifact
    pattern_description: str
    universe: str | None = None
    scan_date: date | None = None

    def __post_init__(self) -> None:
        description = self.pattern_description.strip()
        if not description:
            raise ValueError("pattern_description must be non-empty")
        object.__setattr__(self, "pattern_description", description)
        if self.universe is not None:
            object.__setattr__(self, "universe", _normalize_identifier(self.universe, "universe"))


@dataclass(frozen=True, slots=True)
class OfflineEventStudy:
    """Offline event-study artifact definition."""

    artifact: ResearchArtifact
    event_definition: str
    entry_condition: str
    exit_condition: str | None = None
    horizon_sessions: int | None = None
    universe: str | None = None
    start_date: date | None = None
    end_date: date | None = None

    def __post_init__(self) -> None:
        event_definition = self.event_definition.strip()
        entry_condition = self.entry_condition.strip()
        if not event_definition:
            raise ValueError("event_definition must be non-empty")
        if not entry_condition:
            raise ValueError("entry_condition must be non-empty")
        if self.horizon_sessions is not None and self.horizon_sessions <= 0:
            raise ValueError("horizon_sessions must be positive")
        object.__setattr__(self, "event_definition", event_definition)
        object.__setattr__(self, "entry_condition", entry_condition)
        if self.exit_condition is not None:
            object.__setattr__(self, "exit_condition", self.exit_condition.strip())
        if self.universe is not None:
            object.__setattr__(self, "universe", _normalize_identifier(self.universe, "universe"))
        if self.end_date is not None and self.start_date is not None:
            if self.end_date < self.start_date:
                raise ValueError("start_date must be before or equal end_date")


def _maybe_path(value: Path | None) -> str | None:
    if value is None:
        return None
    return str(value)
