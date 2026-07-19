from __future__ import annotations

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
    download = service.execute(
        DataProvisioningRequest(
            operation="download",
            artifact="ohlcv",
            symbol=symbol,
            symbols=(symbol,),
            start=lookback_start,
            end=resolved_date,
            date=resolved_date,
            requested_date=requested_date,
            source=DEFAULT_POLICY.source,
        )
    )
    actions = [ProvisioningAction("sync_ohlcv", download.status.value)]
    warnings = list(download.warnings)
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

    canonical = service.execute(
        DataProvisioningRequest(
            operation="build",
            artifact="canonical",
            symbol=symbol,
            date=resolved_date,
            requested_date=requested_date,
        )
    )
    actions.append(ProvisioningAction("build_canonical", canonical.status.value))
    warnings.extend(canonical.warnings)
    if (
        canonical.status is not ProvisioningStatus.SUCCESS
        or canonical.counts.get("upserted", 0) <= 0
    ):
        return _failed_result(
            symbol,
            requested_date,
            resolved_date,
            correlation_id,
            actions,
            warnings,
            canonical,
            "Canonical OHLCV build did not produce persisted rows.",
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
