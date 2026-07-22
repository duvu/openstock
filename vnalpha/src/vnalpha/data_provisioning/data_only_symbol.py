from __future__ import annotations

from datetime import date, timedelta

import duckdb

from vnalpha.core.dates import resolve_date
from vnalpha.data_availability.checks import compute_lookback_start
from vnalpha.data_availability.policy import DEFAULT_POLICY
from vnalpha.data_provisioning.ensure_current_symbol import (
    CurrentSymbolReadyResult,
    ProvisioningAction,
    ProvisioningOutcome,
)
from vnalpha.data_provisioning.service import (
    DataProvisioningRequest,
    DataProvisioningResult,
    DataProvisioningService,
    ProvisioningStatus,
)
from vnalpha.ingestion.build_canonical import build_canonical_ohlcv
from vnalpha.ingestion.trading_calendar import SessionRange, VietnamSessionCalendar


def provision_data_only_symbol(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    requested_date: str | None,
    *,
    refresh: bool,
    correlation_id: str,
) -> CurrentSymbolReadyResult:
    resolved_date = resolve_date(requested_date)
    lookback_start = compute_lookback_start(resolved_date, DEFAULT_POLICY.lookback_days)
    service = DataProvisioningService(conn)
    raw_tail_start = _tail_start(
        conn, "market_ohlcv_raw", symbol, resolved_date, lookback_start
    )
    canonical_tail_start = _tail_start(
        conn, "canonical_ohlcv", symbol, resolved_date, lookback_start
    )
    actions: list[ProvisioningAction] = []
    warnings: list[str] = []
    if raw_tail_start is not None:
        download = service.execute(
            DataProvisioningRequest(
                operation="download",
                artifact="ohlcv",
                symbol=symbol,
                symbols=(symbol,),
                start=raw_tail_start or lookback_start,
                end=resolved_date,
                date=resolved_date,
                requested_date=requested_date,
                source=DEFAULT_POLICY.source,
            )
        )
        actions.append(ProvisioningAction("sync_ohlcv", download.status.value))
        warnings.extend(download.warnings)
        if download.status is not ProvisioningStatus.SUCCESS:
            return _failed_result(
                symbol,
                requested_date,
                resolved_date,
                correlation_id,
                actions,
                warnings,
                download,
                "Bounded OHLCV download did not complete.",
            )
    if canonical_tail_start is None:
        actions.append(ProvisioningAction("reuse_fresh", "SUCCESS"))
        return CurrentSymbolReadyResult(
            symbol=symbol,
            outcome=ProvisioningOutcome.REUSED,
            correlation_id=correlation_id,
            requested_date=requested_date,
            resolved_date=resolved_date,
            actions=tuple(actions),
            reused_fresh_data=True,
            refreshed=False,
            warnings=tuple(warnings),
            errors=(),
            remediation=(),
        )
    try:
        canonical = build_canonical_ohlcv(
            conn,
            symbol=symbol,
            start=canonical_tail_start,
            end=resolved_date,
        )
    except (duckdb.Error, ValueError) as error:
        actions.append(ProvisioningAction("build_canonical", "FAILED"))
        return CurrentSymbolReadyResult(
            symbol=symbol,
            outcome=ProvisioningOutcome.FAILED,
            correlation_id=correlation_id,
            requested_date=requested_date,
            resolved_date=resolved_date,
            actions=tuple(actions),
            reused_fresh_data=False,
            refreshed=False,
            warnings=tuple(warnings),
            errors=(str(error),),
            remediation=(),
        )
    actions.append(ProvisioningAction("build_canonical", "SUCCESS"))
    if canonical["upserted"] <= 0:
        return CurrentSymbolReadyResult(
            symbol=symbol,
            outcome=ProvisioningOutcome.FAILED,
            correlation_id=correlation_id,
            requested_date=requested_date,
            resolved_date=resolved_date,
            actions=tuple(actions),
            reused_fresh_data=False,
            refreshed=False,
            warnings=tuple(warnings),
            errors=("Canonical OHLCV build did not produce persisted rows.",),
            remediation=(),
        )

    return CurrentSymbolReadyResult(
        symbol=symbol,
        outcome=(
            ProvisioningOutcome.REFRESHED if refresh else ProvisioningOutcome.READY
        ),
        correlation_id=correlation_id,
        requested_date=requested_date,
        resolved_date=resolved_date,
        actions=tuple(actions),
        reused_fresh_data=False,
        refreshed=refresh,
        warnings=tuple(warnings),
        errors=(),
        remediation=(),
    )


def _tail_start(
    conn: duckdb.DuckDBPyConnection,
    table: str,
    symbol: str,
    resolved_date: str,
    initial_start: str,
) -> str | None:
    latest = conn.execute(
        f"SELECT MAX(CAST(time AS DATE))::VARCHAR FROM {table} "
        "WHERE symbol = ? AND interval = '1D'",
        [symbol],
    ).fetchone()
    if latest is None or latest[0] is None:
        return initial_start
    if str(latest[0]) >= resolved_date:
        return None
    next_sessions = VietnamSessionCalendar().sessions(
        SessionRange(
            start=date.fromisoformat(str(latest[0])) + timedelta(days=1),
            end=date.fromisoformat(resolved_date),
        )
    )
    return next_sessions[0].isoformat() if next_sessions else None


def _failed_result(
    symbol: str,
    requested_date: str | None,
    resolved_date: str,
    correlation_id: str,
    actions: list[ProvisioningAction],
    warnings: list[str],
    stage: DataProvisioningResult,
    fallback_error: str,
) -> CurrentSymbolReadyResult:
    return CurrentSymbolReadyResult(
        symbol=symbol,
        outcome=ProvisioningOutcome.FAILED,
        correlation_id=correlation_id,
        requested_date=requested_date,
        resolved_date=resolved_date,
        actions=tuple(actions),
        reused_fresh_data=False,
        refreshed=False,
        warnings=tuple(warnings),
        errors=(stage.error or fallback_error,),
        remediation=((stage.follow_up,) if stage.follow_up else ()),
    )


__all__ = ["provision_data_only_symbol"]
