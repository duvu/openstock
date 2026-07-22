from __future__ import annotations

import duckdb

from vnalpha.core.dates import resolve_date
from vnalpha.data_availability.checks import compute_lookback_start
from vnalpha.data_availability.policy import DEFAULT_POLICY
from vnalpha.data_provisioning.current_symbol_models import (
    CurrentSymbolReadyResult,
    ProvisioningAction,
    ProvisioningOutcome,
)
from vnalpha.data_provisioning.current_symbol_tail import canonical_lineage, tail_start
from vnalpha.data_provisioning.service import (
    DataProvisioningRequest,
    DataProvisioningResult,
    DataProvisioningService,
    ProvisioningStatus,
)
from vnalpha.ingestion.build_canonical import build_canonical_ohlcv


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
    if refresh:
        raw_tail_start = resolved_date
        canonical_tail_start = resolved_date
    else:
        raw_tail_start = tail_start(
            conn, "market_ohlcv_raw", symbol, resolved_date, lookback_start
        )
        canonical_tail_start = tail_start(
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
        actions.append(
            ProvisioningAction(
                "sync_ohlcv",
                download.status.value,
                dataset="equity.ohlcv",
                symbol=symbol,
                start_date=raw_tail_start,
                end_date=resolved_date,
                source=download.source,
                ingestion_run_id=download.lineage.get("ingestion_run_id"),
                failure_category=download.terminal_reason,
                root_cause=download.error,
            )
        )
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
        actions.append(
            ProvisioningAction(
                "build_canonical",
                "FAILED",
                dataset="equity.ohlcv",
                symbol=symbol,
                start_date=canonical_tail_start,
                end_date=resolved_date,
            )
        )
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
    provider, ingestion_run_id = canonical_lineage(
        conn, symbol, canonical_tail_start, resolved_date
    )
    if canonical["upserted"] <= 0:
        actions.append(
            ProvisioningAction(
                "build_canonical",
                "FAILED",
                dataset="equity.ohlcv",
                symbol=symbol,
                failure_category="CANONICAL_ROWS_MISSING",
                start_date=canonical_tail_start,
                end_date=resolved_date,
                source=provider,
                ingestion_run_id=ingestion_run_id,
            )
        )
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
    actions.append(
        ProvisioningAction(
            "build_canonical",
            "SUCCESS",
            dataset="equity.ohlcv",
            symbol=symbol,
            start_date=canonical_tail_start,
            end_date=resolved_date,
            source=provider,
            ingestion_run_id=ingestion_run_id,
        )
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
