"""Warehouse inspection for current-symbol readiness without side effects."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import assert_never

import duckdb

from vnalpha.clients.vnstock.source_policy import (
    approved_persistence_sources,
    validate_persistence_source,
)
from vnalpha.core.dates import resolve_market_session_date
from vnalpha.data_availability.artifact_readiness_models import (
    ArtifactReadiness,
    ArtifactReadinessReport,
    ArtifactReadinessRequest,
    ArtifactState,
    BoundedDateRange,
    ReadinessAction,
    ReadinessActionProposal,
    ReadinessCapability,
)
from vnalpha.data_availability.checks import (
    compute_lookback_start,
    get_candidate_score_evidence,
    get_feature_snapshot_evidence,
)
from vnalpha.data_availability.dataset_readiness import (
    check_dataset_readiness,
)
from vnalpha.data_availability.policy import DataAvailabilityPolicy
from vnalpha.data_availability.relative_strength_checks import (
    get_relative_strength_evidence,
)
from vnalpha.data_provisioning.source_policy import (
    InvalidSourceForDataset,
    SourcePolicyResolver,
    get_default_resolver,
)
from vnalpha.ingestion.trading_calendar import SessionRange, VietnamSessionCalendar
from vnalpha.warehouse.connection import read_connection


@dataclass(frozen=True, slots=True)
class ArtifactReadinessService:
    """Inspect persisted evidence and propose only bounded remediation."""

    warehouse_path: Path | str | None = None
    policy: DataAvailabilityPolicy = field(default_factory=DataAvailabilityPolicy)
    source_policy: SourcePolicyResolver = field(default_factory=get_default_resolver)

    def inspect(self, request: ArtifactReadinessRequest) -> ArtifactReadinessReport:
        """Return a readiness report using one short-lived read-only connection."""
        resolved_date = resolve_market_session_date(request.effective_date)
        with read_connection(self.warehouse_path) as connection:
            effective_date = _resolve_available_session_date(
                connection,
                request.symbol,
                request.effective_date,
                resolved_date,
                self.policy,
            )
            return _inspect_connection(
                connection=connection,
                request=request,
                effective_date=effective_date,
                policy=self.policy,
                source_policy=self.source_policy,
            )


def _resolve_available_session_date(
    connection: duckdb.DuckDBPyConnection,
    symbol: str,
    requested_date: str | None,
    resolved_date: str,
    policy: DataAvailabilityPolicy,
) -> str:
    if requested_date is not None and requested_date.strip().lower() != "today":
        return resolved_date
    minimum_date = (
        date.fromisoformat(resolved_date)
        - timedelta(days=policy.stale_after_calendar_days)
    ).isoformat()
    quality_placeholders = ", ".join("?" for _ in policy.acceptable_quality_statuses)
    try:
        row = connection.execute(
            f"""
            SELECT CAST(target.time AS DATE)::VARCHAR
            FROM canonical_ohlcv target
            WHERE target.symbol = ?
              AND target.interval = '1D'
              AND LOWER(COALESCE(target.quality_status, '')) IN ({quality_placeholders})
              AND CAST(target.time AS DATE) BETWEEN ? AND ?
              AND EXISTS (
                  SELECT 1
                  FROM canonical_ohlcv benchmark
                  WHERE benchmark.symbol = ?
                    AND benchmark.interval = '1D'
                    AND LOWER(COALESCE(benchmark.quality_status, '')) IN ({quality_placeholders})
                    AND CAST(benchmark.time AS DATE) = CAST(target.time AS DATE)
              )
              AND (
                  SELECT COUNT(*) FROM canonical_ohlcv price
                  WHERE price.symbol = target.symbol
                    AND price.interval = '1D'
                    AND LOWER(COALESCE(price.quality_status, '')) IN ({quality_placeholders})
                    AND CAST(price.time AS DATE) BETWEEN CAST(target.time AS DATE) - INTERVAL {policy.lookback_days} DAY AND CAST(target.time AS DATE)
              ) >= ?
              AND (
                  SELECT COUNT(*) FROM canonical_ohlcv benchmark
                  WHERE benchmark.symbol = ?
                    AND benchmark.interval = '1D'
                    AND LOWER(COALESCE(benchmark.quality_status, '')) IN ({quality_placeholders})
                    AND CAST(benchmark.time AS DATE) BETWEEN CAST(target.time AS DATE) - INTERVAL {policy.lookback_days} DAY AND CAST(target.time AS DATE)
              ) >= ?
            ORDER BY CAST(target.time AS DATE) DESC
            LIMIT 1
            """,
            [
                symbol.strip().upper(),
                *policy.acceptable_quality_statuses,
                minimum_date,
                resolved_date,
                policy.benchmark,
                *policy.acceptable_quality_statuses,
                *policy.acceptable_quality_statuses,
                policy.min_required_bars,
                policy.benchmark,
                *policy.acceptable_quality_statuses,
                policy.min_required_bars,
            ],
        ).fetchone()
    except duckdb.CatalogException:
        return resolved_date
    return str(row[0]) if row is not None and row[0] is not None else resolved_date


def _inspect_connection(
    *,
    connection: duckdb.DuckDBPyConnection,
    request: ArtifactReadinessRequest,
    effective_date: str,
    policy: DataAvailabilityPolicy,
    source_policy: SourcePolicyResolver,
) -> ArtifactReadinessReport:
    symbol = request.symbol.strip().upper()
    symbol_artifact = _symbol_artifact(
        connection,
        symbol,
        request.historical,
        source_policy,
        allow_actions=policy.auto_sync,
        requested_source=policy.source,
    )
    canonical_artifact = _ohlcv_artifact(
        connection=connection,
        symbol=symbol,
        effective_date=effective_date,
        required_rows=policy.min_required_bars,
        lookback_start=compute_lookback_start(effective_date, policy.lookback_days),
        acceptable_quality_statuses=policy.acceptable_quality_statuses,
        artifact_name="canonical_ohlcv",
        dataset="equity.ohlcv",
        sync_action=ReadinessAction.SYNC_TARGET_OHLCV,
        canonical_action=ReadinessAction.BUILD_TARGET_CANONICAL,
        historical=request.historical,
        source_policy=source_policy,
        allow_actions=policy.auto_sync,
        requested_source=policy.source,
    )
    artifacts = [symbol_artifact, canonical_artifact]
    artifacts.extend(
        _ranking_artifacts(
            connection=connection,
            symbol=symbol,
            target=canonical_artifact,
            benchmark_symbol=policy.benchmark,
            effective_date=effective_date,
            required_rows=policy.min_required_bars,
            lookback_start=compute_lookback_start(effective_date, policy.lookback_days),
            acceptable_quality_statuses=policy.acceptable_quality_statuses,
            required_lineage_fields=policy.required_lineage_fields,
            required=request.capability is ReadinessCapability.CANDIDATE_RANKING,
            historical=request.historical,
            source_policy=source_policy,
            allow_actions=policy.auto_sync,
            requested_source=policy.source,
        )
    )
    fallback = (
        ReadinessCapability.PRICE_ANALYSIS
        if request.capability is ReadinessCapability.CANDIDATE_RANKING
        else None
    )
    return ArtifactReadinessReport(
        symbol=symbol,
        requested_date=request.effective_date,
        effective_date=effective_date,
        requested_capability=request.capability,
        fallback_capability=fallback,
        artifacts=tuple(artifacts),
        should_enqueue=(
            policy.auto_sync
            and not request.historical
            and any(
                artifact.required and artifact.state is not ArtifactState.READY
                for artifact in artifacts
            )
            and all(
                artifact.repairable
                for artifact in artifacts
                if artifact.required and artifact.state is not ArtifactState.READY
            )
        ),
    )


def _symbol_artifact(
    connection: duckdb.DuckDBPyConnection,
    symbol: str,
    historical: bool,
    source_policy: SourcePolicyResolver,
    *,
    allow_actions: bool,
    requested_source: str | None,
) -> ArtifactReadiness:
    exists = connection.execute(
        "SELECT 1 FROM symbol_master WHERE symbol = ? LIMIT 1", [symbol]
    ).fetchone()
    if exists is not None:
        return ArtifactReadiness(
            name="symbol_master",
            state=ArtifactState.READY,
            required=True,
            repairable=False,
            reason_codes=(),
        )
    action = _provider_action(
        action=ReadinessAction.SYNC_SYMBOLS,
        artifact="symbol_master",
        dataset="reference.symbols",
        date_range=None,
        source_policy=source_policy,
        connection=connection,
        historical=historical or not allow_actions,
        requested_source=requested_source,
    )
    reasons = ["SYMBOL_MISSING"]
    if historical:
        reasons.append("HISTORICAL_REQUEST")
    elif action is None and allow_actions:
        reasons.append("NO_ELIGIBLE_SOURCE")
    return ArtifactReadiness(
        name="symbol_master",
        state=ArtifactState.MISSING,
        required=True,
        repairable=action is not None,
        reason_codes=tuple(reasons),
        actions=(action,) if action is not None else (),
    )


def _ohlcv_artifact(
    *,
    connection: duckdb.DuckDBPyConnection,
    symbol: str,
    effective_date: str,
    required_rows: int,
    lookback_start: str,
    acceptable_quality_statuses: tuple[str, ...],
    artifact_name: str,
    dataset: str,
    sync_action: ReadinessAction,
    canonical_action: ReadinessAction,
    historical: bool,
    source_policy: SourcePolicyResolver,
    required: bool = True,
    allow_actions: bool = True,
    requested_source: str | None = None,
) -> ArtifactReadiness:
    (
        row_count,
        latest_date,
        unacceptable_quality,
        unresolved_gap,
        missing_required_session,
    ) = _ohlcv_summary(
        connection,
        symbol,
        effective_date,
        lookback_start,
        required_rows,
        acceptable_quality_statuses,
    )
    state = _ohlcv_state(
        row_count,
        latest_date,
        effective_date,
        required_rows,
        unacceptable_quality,
        unresolved_gap,
        missing_required_session,
    )
    if state is ArtifactState.READY:
        return ArtifactReadiness(
            name=artifact_name,
            state=state,
            required=required,
            repairable=False,
            reason_codes=(),
            observed_date=latest_date,
            row_count=row_count,
        )
    actions = _ohlcv_actions(
        state=state,
        artifact_name=artifact_name,
        dataset=dataset,
        sync_action=sync_action,
        canonical_action=canonical_action,
        symbol=symbol,
        row_count=row_count,
        latest_date=latest_date,
        effective_date=effective_date,
        lookback_start=lookback_start,
        required_rows=required_rows,
        connection=connection,
        source_policy=source_policy,
        historical=historical or not allow_actions,
        requested_source=requested_source,
    )
    reasons = list(
        _ohlcv_reasons(
            state,
            row_count,
            required_rows,
            latest_date,
            effective_date,
            missing_required_session,
        )
    )
    if historical:
        reasons.append("HISTORICAL_REQUEST")
    elif (
        not actions
        and state is not ArtifactState.INVALID
        and required
        and allow_actions
    ):
        reasons.append("NO_ELIGIBLE_SOURCE")
    return ArtifactReadiness(
        name=artifact_name,
        state=state,
        required=required,
        repairable=bool(actions),
        reason_codes=tuple(reasons),
        observed_date=latest_date,
        row_count=row_count,
        actions=actions,
    )


def _ranking_artifacts(
    *,
    connection: duckdb.DuckDBPyConnection,
    symbol: str,
    target: ArtifactReadiness,
    benchmark_symbol: str,
    effective_date: str,
    required_rows: int,
    lookback_start: str,
    acceptable_quality_statuses: tuple[str, ...],
    required_lineage_fields: tuple[str, ...],
    required: bool,
    historical: bool,
    source_policy: SourcePolicyResolver,
    allow_actions: bool,
    requested_source: str | None,
) -> tuple[ArtifactReadiness, ...]:
    benchmark = _ohlcv_artifact(
        connection=connection,
        symbol=benchmark_symbol,
        effective_date=effective_date,
        required_rows=required_rows,
        lookback_start=lookback_start,
        acceptable_quality_statuses=acceptable_quality_statuses,
        artifact_name="benchmark_ohlcv",
        dataset="index.ohlcv",
        sync_action=ReadinessAction.SYNC_BENCHMARK_OHLCV,
        canonical_action=ReadinessAction.BUILD_BENCHMARK_CANONICAL,
        historical=historical,
        source_policy=source_policy,
        required=required,
        allow_actions=allow_actions and required,
        requested_source=requested_source,
    )
    feature_state = _feature_state(connection, symbol, effective_date, benchmark_symbol)
    feature_action = (
        ReadinessActionProposal(
            action=ReadinessAction.BUILD_FEATURES,
            artifact="feature_snapshot",
            dataset=None,
            date_range=None,
            reason_code=(
                "FEATURES_MISSING"
                if feature_state is ArtifactState.MISSING
                else "FEATURES_INVALID"
            ),
        )
        if allow_actions
        and required
        and not historical
        and feature_state is not ArtifactState.READY
        and (benchmark.state is ArtifactState.READY or benchmark.repairable)
        and (target.state is ArtifactState.READY or target.repairable)
        else None
    )
    feature = ArtifactReadiness(
        name="feature_snapshot",
        state=feature_state,
        required=required,
        repairable=feature_action is not None,
        reason_codes=(
            ()
            if feature_state is ArtifactState.READY
            else (
                "FEATURES_MISSING"
                if feature_state is ArtifactState.MISSING
                else "FEATURES_INVALID",
            )
        ),
        observed_date=(
            effective_date if feature_state is ArtifactState.READY else None
        ),
        actions=(feature_action,) if feature_action is not None else (),
    )
    score_state = _score_state(
        connection, symbol, effective_date, required_lineage_fields
    )
    score_action = (
        ReadinessActionProposal(
            action=ReadinessAction.SCORE_SYMBOL,
            artifact="candidate_score",
            dataset=None,
            date_range=None,
            reason_code=(
                "SCORE_MISSING"
                if score_state is ArtifactState.MISSING
                else "SCORE_INVALID"
            ),
        )
        if allow_actions
        and required
        and not historical
        and score_state is not ArtifactState.READY
        and (feature.state is ArtifactState.READY or feature.repairable)
        else None
    )
    score = ArtifactReadiness(
        name="candidate_score",
        state=score_state,
        required=required,
        repairable=score_action is not None,
        reason_codes=(
            ()
            if score_state is ArtifactState.READY
            else (
                "SCORE_MISSING"
                if score_state is ArtifactState.MISSING
                else "SCORE_INVALID",
            )
        ),
        observed_date=effective_date if score_state is ArtifactState.READY else None,
        actions=(score_action,) if score_action is not None else (),
    )
    return benchmark, feature, score


def _ohlcv_summary(
    connection: duckdb.DuckDBPyConnection,
    symbol: str,
    effective_date: str,
    lookback_start: str,
    required_rows: int,
    acceptable_quality_statuses: tuple[str, ...],
) -> tuple[int, str | None, bool, bool, bool]:
    quality_placeholders = ", ".join("?" for _ in acceptable_quality_statuses)
    row = connection.execute(
        f"""
        SELECT COUNT(*), MAX(CAST(time AS DATE))::VARCHAR,
               SUM(CASE WHEN LOWER(COALESCE(quality_status, '')) NOT IN ({quality_placeholders})
                        THEN 1 ELSE 0 END)
        FROM canonical_ohlcv
        WHERE symbol = ? AND interval = '1D'
          AND CAST(time AS DATE) BETWEEN ? AND ?
        """,
        [*acceptable_quality_statuses, symbol, lookback_start, effective_date],
    ).fetchone()
    gap_row = connection.execute(
        """
        SELECT COUNT(*) FROM ohlcv_gap_observation
        WHERE symbol = ? AND interval = '1D'
          AND session_date BETWEEN ? AND ?
          AND resolved_at IS NULL AND gap_kind = 'TRUE_GAP'
        """,
        [symbol, lookback_start, effective_date],
    ).fetchone()
    available_rows = connection.execute(
        """
        SELECT DISTINCT CAST(time AS DATE)::VARCHAR FROM canonical_ohlcv
        WHERE symbol = ? AND interval = '1D'
          AND CAST(time AS DATE) BETWEEN ? AND ?
        """,
        [symbol, lookback_start, effective_date],
    ).fetchall()
    calendar = VietnamSessionCalendar()
    required_start = calendar.rewind_sessions(
        date.fromisoformat(effective_date), required_rows
    )
    required_sessions = {
        session.isoformat()
        for session in calendar.sessions(
            SessionRange(start=required_start, end=date.fromisoformat(effective_date))
        )
    }
    available_sessions = {str(available_row[0]) for available_row in available_rows}
    return (
        int(row[0]) if row else 0,
        str(row[1]) if row and row[1] else None,
        bool(row and row[2]),
        bool(gap_row and gap_row[0]),
        not required_sessions.issubset(available_sessions),
    )


def _ohlcv_state(
    row_count: int,
    latest_date: str | None,
    effective_date: str,
    required_rows: int,
    unacceptable_quality: bool,
    unresolved_gap: bool,
    missing_required_session: bool,
) -> ArtifactState:
    if row_count == 0:
        return ArtifactState.MISSING
    if unacceptable_quality or unresolved_gap:
        return ArtifactState.INVALID
    if (
        row_count < required_rows
        or latest_date != effective_date
        or missing_required_session
    ):
        return ArtifactState.STALE
    return ArtifactState.READY


def _ohlcv_actions(
    *,
    state: ArtifactState,
    artifact_name: str,
    dataset: str,
    sync_action: ReadinessAction,
    canonical_action: ReadinessAction,
    symbol: str,
    row_count: int,
    latest_date: str | None,
    effective_date: str,
    lookback_start: str,
    required_rows: int,
    connection: duckdb.DuckDBPyConnection,
    source_policy: SourcePolicyResolver,
    historical: bool,
    requested_source: str | None,
) -> tuple[ReadinessActionProposal, ...]:
    if historical or state is ArtifactState.INVALID:
        return ()
    repair_ranges = _missing_ranges(
        connection,
        symbol,
        effective_date,
        lookback_start,
        required_rows,
    )
    if all(
        _raw_range_ready(connection, symbol, repair_range)
        for repair_range in repair_ranges
    ):
        return tuple(
            ReadinessActionProposal(
                action=canonical_action,
                artifact=artifact_name,
                dataset=None,
                date_range=repair_range,
                reason_code="RAW_READY_CANONICAL_STALE",
            )
            for repair_range in repair_ranges
        )
    actions = tuple(
        _provider_action(
            action=sync_action,
            artifact=artifact_name,
            dataset=dataset,
            date_range=repair_range,
            source_policy=source_policy,
            connection=connection,
            historical=False,
            requested_source=requested_source,
        )
        for repair_range in repair_ranges
    )
    return tuple(action for action in actions if action is not None)


def _provider_action(
    *,
    action: ReadinessAction,
    artifact: str,
    dataset: str,
    date_range: BoundedDateRange | None,
    source_policy: SourcePolicyResolver,
    connection: duckdb.DuckDBPyConnection,
    historical: bool,
    requested_source: str | None,
) -> ReadinessActionProposal | None:
    if historical:
        return None
    try:
        source = source_policy.resolve(dataset, requested_source=requested_source)
    except InvalidSourceForDataset:
        return None
    if source.source is not None:
        try:
            validate_persistence_source(source.source)
        except ValueError:
            return None
    if source.source == "fiinquantx":
        readiness = check_dataset_readiness(connection, dataset)
        if source.source not in readiness.explicit_providers:
            return None
    return ReadinessActionProposal(
        action=action,
        artifact=artifact,
        dataset=dataset,
        date_range=date_range,
        reason_code="SOURCE_POLICY_REPAIRABLE",
    )


def _missing_ranges(
    connection: duckdb.DuckDBPyConnection,
    symbol: str,
    effective_date: str,
    lookback_start: str,
    required_rows: int,
) -> tuple[BoundedDateRange, ...]:
    rows = connection.execute(
        """
        SELECT CAST(time AS DATE)::VARCHAR FROM canonical_ohlcv
        WHERE symbol = ? AND interval = '1D'
          AND CAST(time AS DATE) BETWEEN ? AND ?
        """,
        [symbol, lookback_start, effective_date],
    ).fetchall()
    available = {str(row[0]) for row in rows}
    calendar = VietnamSessionCalendar()
    target_date = date.fromisoformat(effective_date)
    coverage_start = calendar.rewind_sessions(target_date, required_rows)
    if not available:
        return (
            BoundedDateRange(
                coverage_start.isoformat(),
                effective_date,
            ),
        )
    sessions = calendar.sessions(SessionRange(start=coverage_start, end=target_date))
    missing = [session for session in sessions if session.isoformat() not in available]
    if not missing:
        return (BoundedDateRange(lookback_start, effective_date),)
    missing_indexes = [
        index for index, session in enumerate(sessions) if session in set(missing)
    ]
    ranges: list[BoundedDateRange] = []
    start_index = previous_index = missing_indexes[0]
    for index in missing_indexes[1:]:
        if index == previous_index + 1:
            previous_index = index
            continue
        ranges.append(
            BoundedDateRange(
                sessions[start_index].isoformat(), sessions[previous_index].isoformat()
            )
        )
        start_index = previous_index = index
    ranges.append(
        BoundedDateRange(
            sessions[start_index].isoformat(), sessions[previous_index].isoformat()
        )
    )
    return tuple(ranges)


def _raw_range_ready(
    connection: duckdb.DuckDBPyConnection,
    symbol: str,
    repair_range: BoundedDateRange,
) -> bool:
    sessions = VietnamSessionCalendar().sessions(
        SessionRange(
            start=date.fromisoformat(repair_range.start_date),
            end=date.fromisoformat(repair_range.end_date),
        )
    )
    approved = tuple(sorted(approved_persistence_sources()))
    placeholders = ", ".join("?" for _ in approved)
    rows = connection.execute(
        f"""
        SELECT DISTINCT CAST(time AS DATE)::VARCHAR FROM market_ohlcv_raw
        WHERE symbol = ? AND interval = '1D'
          AND CAST(time AS DATE) BETWEEN ? AND ?
          AND LOWER(TRIM(COALESCE(quality_status, ''))) IN ('pass', 'success')
          AND (UPPER(TRIM(COALESCE(provider, ''))) <> 'FIINQUANTX'
               OR UPPER(TRIM(COALESCE(price_basis, ''))) = 'RAW_UNADJUSTED')
          AND UPPER(TRIM(COALESCE(provider, ''))) IN ({placeholders})
        """,
        [
            symbol,
            repair_range.start_date,
            repair_range.end_date,
            *approved,
        ],
    ).fetchall()
    return {str(row[0]) for row in rows} == {
        session.isoformat() for session in sessions
    }


def _ohlcv_reasons(
    state: ArtifactState,
    row_count: int,
    required_rows: int,
    latest_date: str | None,
    effective_date: str,
    missing_required_session: bool,
) -> tuple[str, ...]:
    match state:
        case ArtifactState.MISSING:
            return ("OHLCV_MISSING",)
        case ArtifactState.STALE:
            reasons = []
            if row_count < required_rows:
                reasons.append("OHLCV_HISTORY_INSUFFICIENT")
            if latest_date != effective_date:
                reasons.append("OHLCV_EFFECTIVE_DATE_MISSING")
            if missing_required_session:
                reasons.append("OHLCV_SESSION_GAP")
            return tuple(reasons)
        case ArtifactState.INVALID:
            return ("OHLCV_INVALID",)
        case ArtifactState.READY:
            return ()
        case unreachable:
            assert_never(unreachable)


def _feature_state(
    connection: duckdb.DuckDBPyConnection,
    symbol: str,
    effective_date: str,
    benchmark_symbol: str,
) -> ArtifactState:
    feature = get_feature_snapshot_evidence(connection, symbol, effective_date)
    relative_strength = get_relative_strength_evidence(
        connection, symbol, effective_date
    )
    if (
        feature.available
        and relative_strength.available
        and (relative_strength.benchmark_symbol == benchmark_symbol)
    ):
        return ArtifactState.READY
    if not feature.available:
        feature_row = connection.execute(
            "SELECT 1 FROM feature_snapshot WHERE symbol = ? AND date = ? LIMIT 1",
            [symbol, effective_date],
        ).fetchone()
        if feature_row is None:
            return ArtifactState.MISSING
        return ArtifactState.INVALID
    return ArtifactState.INVALID


def _score_state(
    connection: duckdb.DuckDBPyConnection,
    symbol: str,
    effective_date: str,
    required_lineage_fields: tuple[str, ...],
) -> ArtifactState:
    score = get_candidate_score_evidence(connection, symbol, effective_date)
    if not score.exists:
        return ArtifactState.MISSING
    if score.as_of_bar_date == effective_date and set(required_lineage_fields).issubset(
        score.lineage_fields
    ):
        return ArtifactState.READY
    return ArtifactState.INVALID


__all__ = ["ArtifactReadinessService"]
