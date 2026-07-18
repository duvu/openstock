"""Data availability models — result types and status enums."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TypeAlias

JsonValue: TypeAlias = (
    str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
)


class EnsureDataStatus(str, Enum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class EnsureDataAction(str, Enum):
    CACHE_HIT = "CACHE_HIT"
    SYMBOLS_SYNCED = "SYMBOLS_SYNCED"
    OHLCV_SYNCED = "OHLCV_SYNCED"
    CANONICAL_BUILT = "CANONICAL_BUILT"
    BENCHMARK_SYNCED = "BENCHMARK_SYNCED"
    BENCHMARK_CANONICAL_BUILT = "BENCHMARK_CANONICAL_BUILT"
    FEATURES_BUILT = "FEATURES_BUILT"
    SCORED = "SCORED"


class EnsureDataActionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class EnsureDataActionOutcome:
    action: EnsureDataAction
    status: EnsureDataActionStatus


class DataArtifact(str, Enum):
    """Core persisted data required for deep-analysis readiness."""

    SYMBOL_MASTER = "symbol_master"
    CANONICAL_OHLCV = "canonical_ohlcv"
    BENCHMARK_OHLCV = "benchmark_ohlcv"
    FEATURE_SNAPSHOT = "feature_snapshot"
    CANDIDATE_SCORE = "candidate_score"


class EvidenceIssue(str, Enum):
    SCORE_MISSING = "score_missing"
    SCORE_STALE = "score_stale"
    FEATURE_SNAPSHOT_MISSING = "feature_snapshot_missing"
    FEATURE_SNAPSHOT_INVALID = "feature_snapshot_invalid"
    FEATURE_LINEAGE_INCOMPLETE = "feature_lineage_incomplete"
    CANONICAL_HISTORY_INSUFFICIENT = "canonical_history_insufficient"
    CANONICAL_GAPS_UNRESOLVED = "canonical_gaps_unresolved"
    BENCHMARK_HISTORY_INSUFFICIENT = "benchmark_history_insufficient"
    QUALITY_UNACCEPTABLE = "quality_unacceptable"
    LINEAGE_INCOMPLETE = "lineage_incomplete"


def evidence_issue_artifact(issue: EvidenceIssue) -> DataArtifact:
    """Return the persisted artifact whose readiness is affected by an issue."""

    if issue in {
        EvidenceIssue.SCORE_MISSING,
        EvidenceIssue.SCORE_STALE,
        EvidenceIssue.LINEAGE_INCOMPLETE,
    }:
        return DataArtifact.CANDIDATE_SCORE
    if issue in {
        EvidenceIssue.FEATURE_SNAPSHOT_MISSING,
        EvidenceIssue.FEATURE_SNAPSHOT_INVALID,
        EvidenceIssue.FEATURE_LINEAGE_INCOMPLETE,
    }:
        return DataArtifact.FEATURE_SNAPSHOT
    if issue in {
        EvidenceIssue.CANONICAL_HISTORY_INSUFFICIENT,
        EvidenceIssue.CANONICAL_GAPS_UNRESOLVED,
        EvidenceIssue.QUALITY_UNACCEPTABLE,
    }:
        return DataArtifact.CANONICAL_OHLCV
    return DataArtifact.BENCHMARK_OHLCV


@dataclass(frozen=True, slots=True)
class ArtifactEvidence:
    """Independent, typed warehouse evidence for one core artifact."""

    artifact: DataArtifact
    available: bool
    row_count: int | None = None
    required_row_count: int | None = None
    window_start_date: str | None = None
    observed_as_of_date: str | None = None
    freshness: str = "unknown"
    quality_status: str = "not_applicable"
    lineage_status: str = "not_applicable"
    lineage_fields: frozenset[str] = frozenset()
    provider: str | None = None
    ingestion_run_id: str | None = None
    generated_at: str | None = None
    methodology_version: str | None = None
    feature_build_version: str | None = None
    scoring_version: str | None = None
    benchmark_as_of_date: str | None = None
    benchmark_row_count: int | None = None
    source_symbol: str | None = None
    symbol_metadata: tuple[tuple[str, str], ...] = ()
    issues: tuple[EvidenceIssue, ...] = ()


@dataclass(frozen=True, slots=True)
class CacheEligibility:
    eligible: bool
    reasons: tuple[str, ...]
    score_fresh: bool
    feature_present: bool
    canonical_sufficient: bool
    benchmark_sufficient: bool
    quality_acceptable: bool
    lineage_acceptable: bool
    issues: tuple[EvidenceIssue, ...] = ()


@dataclass
class EnsureDataResult:
    """Result from ensure_symbol_analysis_ready."""

    symbol: str
    target_date: str
    status: EnsureDataStatus
    actions_taken: list[EnsureDataAction] = field(default_factory=list)
    action_outcomes: list[EnsureDataActionOutcome] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    # diagnostics for the panels
    canonical_bars: int = 0
    feature_snapshot_exists: bool = False
    candidate_score_exists: bool = False
    freshness: str = "unknown"
    lineage_actions: list[str] = field(default_factory=list)
    cache_rejection_reasons: list[str] = field(default_factory=list)
    symbol_known: bool | None = None
    benchmark_bars: int | None = None
    candidate_score_as_of_date: str | None = None
    quality_status: str | None = None
    lineage_fields: frozenset[str] = frozenset()
    core_evidence_evaluated: bool = False
    failure_code: str | None = None
    artifact_evidence: tuple[ArtifactEvidence, ...] = ()
    extra: dict[str, JsonValue] = field(default_factory=dict)

    @property
    def is_ready(self) -> bool:
        return self.status == EnsureDataStatus.READY

    def to_panel_dict(self) -> dict[str, JsonValue]:
        """Return a dict suitable for a ResultPanel."""
        return {
            "status": self.status.value,
            "canonical_bars": self.canonical_bars,
            "feature_snapshot": self.feature_snapshot_exists,
            "candidate_score": self.candidate_score_exists,
            "freshness": self.freshness,
            "lineage_actions": self.lineage_actions,
            "cache_rejection_reasons": self.cache_rejection_reasons,
            "actions_taken": [a.value for a in self.actions_taken],
            "action_outcomes": [
                {"action": outcome.action.value, "status": outcome.status.value}
                for outcome in self.action_outcomes
            ],
            "warnings": self.warnings,
            "errors": self.errors,
        }
