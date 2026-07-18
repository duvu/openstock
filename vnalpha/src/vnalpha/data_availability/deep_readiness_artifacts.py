from __future__ import annotations

from vnalpha.data_availability.deep_readiness_models import (
    ReadinessArtifact,
    ReadinessArtifactStatus,
    RemediationStep,
)
from vnalpha.data_availability.deep_readiness_remediation import (
    RemediationRequest,
    remediation_steps,
)
from vnalpha.data_availability.models import (
    ArtifactEvidence,
    DataArtifact,
    EnsureDataAction,
    EnsureDataResult,
)
from vnalpha.data_availability.planner import compute_lookback_start
from vnalpha.data_availability.policy import DEFAULT_POLICY

_PROVISION_ACTIONS: dict[DataArtifact, tuple[EnsureDataAction, ...]] = {
    DataArtifact.SYMBOL_MASTER: (EnsureDataAction.SYMBOLS_SYNCED,),
    DataArtifact.CANONICAL_OHLCV: (
        EnsureDataAction.OHLCV_SYNCED,
        EnsureDataAction.CANONICAL_BUILT,
    ),
    DataArtifact.BENCHMARK_OHLCV: (
        EnsureDataAction.BENCHMARK_SYNCED,
        EnsureDataAction.BENCHMARK_CANONICAL_BUILT,
    ),
    DataArtifact.FEATURE_SNAPSHOT: (EnsureDataAction.FEATURES_BUILT,),
    DataArtifact.CANDIDATE_SCORE: (EnsureDataAction.SCORED,),
}


def build_artifacts(
    *,
    result: EnsureDataResult,
    actions: tuple[str, ...],
    requested_date: str | None,
    resolved_date: str,
) -> tuple[ReadinessArtifact, ...]:
    evidence_by_artifact = {item.artifact: item for item in result.artifact_evidence}
    lookback_start = compute_lookback_start(resolved_date, DEFAULT_POLICY.lookback_days)
    return tuple(
        _artifact(
            evidence=evidence_by_artifact.get(
                artifact,
                _legacy_evidence(artifact, result, resolved_date)
                if result.core_evidence_evaluated
                else _unknown_evidence(artifact),
            ),
            result=result,
            actions=actions,
            requested_date=requested_date,
            resolved_date=resolved_date,
            remediation=remediation_steps(
                RemediationRequest(
                    artifact=artifact.value,
                    symbol=result.symbol,
                    resolved_date=resolved_date,
                    lookback_start=lookback_start,
                    issues=evidence_by_artifact.get(
                        artifact, _unknown_evidence(artifact)
                    ).issues,
                    raw_window_ready=result.extra.get("raw_window_ready") is True,
                )
            ),
        )
        for artifact in DataArtifact
    )


def _artifact(
    *,
    evidence: ArtifactEvidence,
    result: EnsureDataResult,
    actions: tuple[str, ...],
    requested_date: str | None,
    resolved_date: str,
    remediation: tuple[RemediationStep, ...],
) -> ReadinessArtifact:
    relevant_actions = tuple(
        action.value
        for action in _PROVISION_ACTIONS[evidence.artifact]
        if action.value in actions
    )
    failed = (
        not evidence.available
        or bool(evidence.issues)
        or not result.core_evidence_evaluated
    )
    error_code = _error_code(evidence, result) if failed else None
    error = _error(evidence.artifact, result, error_code) if failed else None
    return ReadinessArtifact(
        name=evidence.artifact.value,
        status=_status(failed, relevant_actions),
        actions=relevant_actions,
        freshness=evidence.freshness,
        lineage=tuple(sorted(evidence.lineage_fields)) or relevant_actions,
        error=error,
        remediation=remediation[0].command if failed and remediation else None,
        available=evidence.available,
        requested_date=requested_date,
        resolved_date=resolved_date,
        observed_as_of_date=evidence.observed_as_of_date,
        row_count=evidence.row_count,
        required_row_count=evidence.required_row_count,
        window_start_date=evidence.window_start_date,
        quality_status=evidence.quality_status,
        lineage_status=evidence.lineage_status,
        provider=evidence.provider,
        ingestion_run_id=evidence.ingestion_run_id,
        generated_at=evidence.generated_at,
        methodology_version=evidence.methodology_version,
        feature_build_version=evidence.feature_build_version,
        scoring_version=evidence.scoring_version,
        benchmark_as_of_date=evidence.benchmark_as_of_date,
        benchmark_row_count=evidence.benchmark_row_count,
        source_symbol=evidence.source_symbol,
        symbol_metadata=evidence.symbol_metadata,
        error_code=error_code,
        remediation_steps=remediation if failed else (),
    )


def _legacy_evidence(
    artifact: DataArtifact, result: EnsureDataResult, resolved_date: str
) -> ArtifactEvidence:
    if artifact is DataArtifact.SYMBOL_MASTER:
        return ArtifactEvidence(
            artifact=artifact, available=result.symbol_known is not False
        )
    if artifact is DataArtifact.CANONICAL_OHLCV:
        return ArtifactEvidence(
            artifact=artifact,
            available=result.canonical_bars >= DEFAULT_POLICY.min_required_bars,
            row_count=result.canonical_bars,
            observed_as_of_date=resolved_date if result.canonical_bars else None,
            freshness="ready" if result.canonical_bars else "missing",
            quality_status=result.quality_status or "unknown",
        )
    if artifact is DataArtifact.BENCHMARK_OHLCV:
        return ArtifactEvidence(
            artifact=artifact,
            available=result.benchmark_bars is None
            or result.benchmark_bars >= DEFAULT_POLICY.min_required_bars,
            row_count=result.benchmark_bars,
            observed_as_of_date=resolved_date if result.benchmark_bars else None,
            freshness="ready" if result.benchmark_bars else "missing",
            quality_status=result.quality_status or "unknown",
        )
    if artifact is DataArtifact.FEATURE_SNAPSHOT:
        return ArtifactEvidence(
            artifact=artifact,
            available=result.feature_snapshot_exists,
            observed_as_of_date=resolved_date
            if result.feature_snapshot_exists
            else None,
            freshness="ready" if result.feature_snapshot_exists else "missing",
        )
    return ArtifactEvidence(
        artifact=artifact,
        available=result.candidate_score_exists,
        observed_as_of_date=result.candidate_score_as_of_date,
        freshness="ready" if result.candidate_score_exists else "missing",
        quality_status=result.quality_status or "unknown",
        lineage_status="complete" if result.lineage_fields else "unknown",
        lineage_fields=result.lineage_fields,
    )


def _unknown_evidence(artifact: DataArtifact) -> ArtifactEvidence:
    return ArtifactEvidence(
        artifact=artifact,
        available=False,
        freshness="unknown",
        quality_status="unknown",
        lineage_status="unknown",
    )


def _status(failed: bool, actions: tuple[str, ...]) -> ReadinessArtifactStatus:
    if failed:
        return ReadinessArtifactStatus.FAILED
    return (
        ReadinessArtifactStatus.PROVISIONED
        if actions
        else ReadinessArtifactStatus.READY
    )


def _error_code(evidence: ArtifactEvidence, result: EnsureDataResult) -> str:
    if evidence.issues:
        return evidence.issues[0].value.upper()
    if result.failure_code is not None:
        return result.failure_code
    return (
        "CORE_EVIDENCE_UNAVAILABLE"
        if not result.core_evidence_evaluated
        else "UNAVAILABLE"
    )


def _error(artifact: DataArtifact, result: EnsureDataResult, error_code: str) -> str:
    if result.errors:
        return result.errors[0]
    if error_code != "UNAVAILABLE":
        return f"{_label(artifact)} remains incomplete: {error_code.lower()}."
    return f"Required {artifact.value} is unavailable."


def _label(artifact: DataArtifact) -> str:
    return artifact.value.replace("_", " ").capitalize()
