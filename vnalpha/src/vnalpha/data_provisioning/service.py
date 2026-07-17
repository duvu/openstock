from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from math import isfinite
from typing import assert_never

import duckdb

from vnalpha.core.dates import resolve_date
from vnalpha.ingestion.models import (
    BatchIngestionStatus,
    JsonValue,
    OHLCVBatchResult,
    SymbolIngestionResult,
    SymbolIngestionStatus,
)
from vnalpha.observability.context import get_correlation_id, set_correlation_id

_APPROVED_SOURCES = frozenset({"KBS", "VCI", "MSN", "DNSE", "TCBS", "FMARKET", "FMP"})


class ProvisioningStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class DataProvisioningValidationError(ValueError):
    pass


class DataProvisioningAdapterError(TypeError):
    pass


@dataclass(frozen=True, slots=True)
class DataProvisioningRequest:
    operation: str
    artifact: str
    symbol: str | None = None
    symbols: tuple[str, ...] | None = None
    allow_all_symbols: bool = False
    start: str | None = None
    end: str | None = None
    date: str | None = None
    source: str | None = None
    interval: str = "1D"
    top_n: int = 30
    min_score: float = 0.40
    benchmark: str | None = None
    requested_date: str | None = None
    authoritative_snapshot: bool = False
    scoring_policy_id: str = "openstock-candidate-score"
    scoring_policy_version: str = "v1.0"
    rebuild_policy: bool = False


@dataclass(frozen=True, slots=True)
class DataProvisioningResult:
    status: ProvisioningStatus
    operation: str
    artifact: str
    correlation_id: str
    counts: dict[str, int] = field(default_factory=dict)
    resolved_date: str | None = None
    source: str | None = None
    symbol: str | None = None
    start: str | None = None
    end: str | None = None
    warnings: tuple[str, ...] = ()
    error: str | None = None
    follow_up: str | None = None
    requested_date: str | None = None
    freshness: str = "unknown"
    lineage: dict[str, str] = field(default_factory=dict)
    symbol_results: tuple[SymbolIngestionResult, ...] = ()
    terminal_reason: str | None = None


@dataclass(frozen=True, slots=True)
class DataProvisioningDependencies:
    sync_symbols: Callable[..., object] | None = None
    sync_ohlcv: Callable[..., object] | None = None
    sync_index: Callable[..., object] | None = None
    build_canonical: Callable[..., object] | None = None
    build_features: Callable[..., object] | None = None
    generate_watchlist: Callable[..., object] | None = None
    build_market_regime: Callable[..., object] | None = None
    build_sector_strength: Callable[..., object] | None = None
    sync_daily: Callable[..., object] | None = None
    scan_ohlcv_gaps: Callable[..., object] | None = None
    repair_ohlcv: Callable[..., object] | None = None


@dataclass(frozen=True, slots=True)
class _MaintenanceFields:
    operation: str
    artifact: str
    symbol: str | None
    symbols: tuple[str, ...] | None
    allow_all_symbols: bool
    start: str | None
    end: str | None
    resolved_date: str | None
    source: str | None
    date_conn: duckdb.DuckDBPyConnection | None


class DataProvisioningService:
    def __init__(
        self,
        conn: duckdb.DuckDBPyConnection,
        *,
        dependencies: DataProvisioningDependencies | None = None,
    ) -> None:
        self.conn = conn
        self._dependencies = dependencies or DataProvisioningDependencies()

    def execute(self, request: DataProvisioningRequest) -> DataProvisioningResult:
        normalized = self._validate(request)
        correlation_id = self._correlation_id()
        _audit_provisioning(
            "REQUESTED", normalized, "STARTED", correlation_id=correlation_id
        )
        try:
            result = self._execute(normalized, correlation_id)
        except Exception:  # noqa: BROAD_EXCEPT_OK
            _audit_provisioning(
                "FAILED", normalized, "FAILED", correlation_id=correlation_id
            )
            return DataProvisioningResult(
                status=ProvisioningStatus.FAILED,
                operation=normalized.operation,
                artifact=normalized.artifact,
                correlation_id=correlation_id,
                resolved_date=normalized.date,
                source=normalized.source,
                symbol=normalized.symbol,
                start=normalized.start,
                end=normalized.end,
                requested_date=normalized.requested_date,
                freshness="unknown",
                lineage={
                    "operation": normalized.operation,
                    "artifact": normalized.artifact,
                    "source": normalized.source or "warehouse",
                },
                error=(
                    "Data provisioning did not complete. "
                    "Review the correlated audit record."
                ),
                follow_up=(
                    "Review the correlated audit record and retry after correcting "
                    "the input or provider."
                ),
            )
        _audit_provisioning(
            result.status.value,
            normalized,
            result.status.value,
            correlation_id=correlation_id,
            counts=result.counts,
        )
        return result

    @classmethod
    def validate_request(cls, request: DataProvisioningRequest) -> None:
        cls._validate_fields(request, date_conn=None)

    def _validate(self, request: DataProvisioningRequest) -> DataProvisioningRequest:
        return self._validate_fields(request, date_conn=self.conn)

    @classmethod
    def _validate_fields(
        cls, request: DataProvisioningRequest, *, date_conn
    ) -> DataProvisioningRequest:
        operation = _normalize_required_text(request.operation, "Operation").lower()
        artifact = _normalize_required_text(request.artifact, "Artifact").lower()
        symbol = _normalize_symbol(request.symbol)
        symbols = _normalize_symbols(request.symbols)
        start = _normalize_date(request.start, "--start")
        end = _normalize_date(request.end, "--end")
        resolved_date = _resolve_request_date(request.date, date_conn)
        source = _normalize_source(request.source)
        interval = _normalize_interval(request.interval)

        if start and end and start > end:
            raise DataProvisioningValidationError("--start must not be after --end.")
        if operation not in {"download", "build", "sync", "gaps", "repair"}:
            raise DataProvisioningValidationError(
                "Operation must be download, build, sync, gaps, or repair."
            )
        if operation == "download":
            _validate_download(
                artifact,
                symbol,
                symbols,
                request.allow_all_symbols,
                start,
                end,
                resolved_date,
                request.authoritative_snapshot,
            )
        elif operation == "build":
            _validate_build(
                artifact,
                symbol,
                symbols,
                request.allow_all_symbols,
                start,
                end,
                source,
                resolved_date,
                request.top_n,
                request.min_score,
            )
        else:
            maintenance = _validate_maintenance(
                _MaintenanceFields(
                    operation=operation,
                    artifact=artifact,
                    symbol=symbol,
                    symbols=symbols,
                    allow_all_symbols=request.allow_all_symbols,
                    start=start,
                    end=end,
                    resolved_date=resolved_date,
                    source=source,
                    date_conn=date_conn,
                )
            )
            resolved_date, start, end = (
                maintenance.resolved_date,
                maintenance.start,
                maintenance.end,
            )

        return DataProvisioningRequest(
            operation=operation,
            artifact=artifact,
            symbol=symbol,
            symbols=symbols,
            allow_all_symbols=request.allow_all_symbols,
            authoritative_snapshot=request.authoritative_snapshot,
            start=start,
            end=end,
            date=resolved_date,
            source=source,
            interval=interval,
            top_n=request.top_n,
            min_score=request.min_score,
            benchmark=_normalize_symbol(request.benchmark),
            requested_date=request.requested_date or request.date,
            scoring_policy_id=request.scoring_policy_id,
            scoring_policy_version=request.scoring_policy_version,
            rebuild_policy=request.rebuild_policy,
        )

    def _execute(
        self, request: DataProvisioningRequest, correlation_id: str
    ) -> DataProvisioningResult:
        match request.operation, request.artifact:
            case "download", "symbols":
                sync_kwargs: dict[str, object] = {"source": request.source}
                if request.authoritative_snapshot:
                    sync_kwargs["authoritative_snapshot"] = True
                raw = _require_mapping(self._sync_symbols()(self.conn, **sync_kwargs))
                counts = _counts(raw, "synced", "errors")
                return _result(
                    request,
                    correlation_id,
                    counts=counts,
                    status=_partial_if_positive(counts, "errors"),
                    warnings=_count_warnings(counts, ("errors", "symbol errors")),
                    raw_result=raw,
                )
            case "download", "ohlcv":
                batch = _require_ohlcv_batch(
                    self._sync_ohlcv()(
                        self.conn,
                        universe=_requested_symbols(request),
                        start=request.start,
                        end=request.end,
                        source=request.source,
                        interval=request.interval,
                    )
                )
                counts = {
                    "total": batch.requested_count,
                    "requested": batch.requested_count,
                    "inserted": batch.rows_inserted,
                    "success": batch.count(SymbolIngestionStatus.SUCCESS),
                    "empty": batch.count(SymbolIngestionStatus.EMPTY),
                    "failed": batch.count(SymbolIngestionStatus.FAILED),
                    "invalid": batch.count(SymbolIngestionStatus.INVALID),
                    "skipped": batch.count(SymbolIngestionStatus.SKIPPED),
                }
                return _result(
                    request,
                    correlation_id,
                    counts=counts,
                    status=_provisioning_status(batch.status),
                    warnings=_ohlcv_warnings(batch),
                    raw_result=batch.to_payload(),
                    symbol_results=batch.symbol_results,
                    terminal_reason=batch.terminal_reason,
                    error=_ohlcv_terminal_error(batch),
                )
            case "download", "index":
                raw = _require_mapping(
                    self._sync_index()(
                        self.conn,
                        symbol=request.symbol or "VNINDEX",
                        start=request.start,
                        end=request.end,
                        source=request.source,
                        interval=request.interval,
                    )
                )
                counts = _counts(raw, "inserted", "skipped")
                return _result(
                    request,
                    correlation_id,
                    counts=counts,
                    status=_partial_if_positive(counts, "skipped"),
                    warnings=_count_warnings(
                        counts, ("skipped", "index requests skipped")
                    ),
                    raw_result=raw,
                )
            case "build", "canonical":
                raw = _require_mapping(
                    self._build_canonical()(
                        self.conn, symbol=request.symbol, interval=request.interval
                    )
                )
                counts = _counts(raw, "upserted", "rejected")
                return _result(
                    request,
                    correlation_id,
                    counts=counts,
                    status=_partial_if_positive(counts, "rejected"),
                    warnings=_count_warnings(counts, ("rejected", "symbols rejected")),
                    raw_result=raw,
                )
            case "build", "features":
                raw = _require_mapping(
                    self._build_features()(
                        self.conn,
                        target_date=_required_date(request.date),
                        universe=_requested_symbols(request),
                        benchmark_symbol=request.benchmark,
                    )
                )
                counts = _counts(raw, "built", "skipped")
                return _result(
                    request,
                    correlation_id,
                    counts=counts,
                    status=_partial_if_positive(counts, "skipped"),
                    warnings=_count_warnings(counts, ("skipped", "symbols skipped")),
                    raw_result=raw,
                )
            case "build", "score":
                raw = _require_mapping(
                    self._generate_watchlist()(
                        self.conn,
                        date=_required_date(request.date),
                        universe=_requested_symbols(request),
                        top_n=request.top_n,
                        min_score=request.min_score,
                        scoring_policy_id=request.scoring_policy_id,
                        scoring_policy_version=request.scoring_policy_version,
                        rebuild_policy=request.rebuild_policy,
                    )
                )
                return _result(
                    request,
                    correlation_id,
                    counts=_counts(raw, "scored", "saved"),
                    raw_result=raw,
                )
            case "build", "market-regime":
                snapshot = self._build_market_regime()(
                    self.conn, _required_date_value(request.date)
                )
                quality = str(getattr(snapshot, "quality", "INCOMPLETE"))
                status = _quality_status(quality, success_values={"COMPLETE"})
                return _result(
                    request,
                    correlation_id,
                    status=status,
                    warnings=(
                        ()
                        if status is ProvisioningStatus.SUCCESS
                        else (f"Market-regime quality is {quality}.",)
                    ),
                    lineage_extra=_object_lineage(snapshot),
                )
            case "build", "sector-strength":
                build_result = self._build_sector_strength()(
                    self.conn, _required_date_value(request.date)
                )
                quality = str(getattr(build_result, "quality", "INCOMPLETE"))
                snapshots = getattr(build_result, "snapshots", ()) or ()
                status = _quality_status(quality, success_values={"OK"})
                return _result(
                    request,
                    correlation_id,
                    status=status,
                    counts={"sectors": len(snapshots)},
                    warnings=(
                        ()
                        if status is ProvisioningStatus.SUCCESS
                        else (f"Sector-strength quality is {quality}.",)
                    ),
                    lineage_extra=_object_lineage(build_result),
                )
            case "sync", "daily":
                daily = self._sync_daily()(
                    self.conn,
                    _daily_sync_request(request),
                )
                return _daily_sync_result(request, correlation_id, daily)
            case "gaps", "ohlcv":
                gap_scan = self._scan_ohlcv_gaps()(
                    self.conn,
                    _gap_scan_request(request),
                )
                return _gap_scan_result(request, correlation_id, gap_scan)
            case "repair", "ohlcv":
                repair = self._repair_ohlcv()(
                    self.conn,
                    _repair_request(request),
                )
                return _repair_result(request, correlation_id, repair)
            case unreachable:
                raise DataProvisioningValidationError(
                    f"Unsupported data request: {unreachable[0]} {unreachable[1]}."
                )

    def _correlation_id(self) -> str:
        correlation_id = get_correlation_id()
        if correlation_id in {"", "unset"}:
            return set_correlation_id()
        return correlation_id

    def _sync_symbols(self) -> Callable[..., object]:
        if self._dependencies.sync_symbols is not None:
            return self._dependencies.sync_symbols
        from vnalpha.ingestion.sync_symbols import sync_symbols

        return sync_symbols

    def _sync_ohlcv(self) -> Callable[..., object]:
        if self._dependencies.sync_ohlcv is not None:
            return self._dependencies.sync_ohlcv
        from vnalpha.ingestion.sync_ohlcv import sync_ohlcv

        return sync_ohlcv

    def _sync_index(self) -> Callable[..., object]:
        if self._dependencies.sync_index is not None:
            return self._dependencies.sync_index
        from vnalpha.ingestion.sync_index import sync_index_ohlcv

        return sync_index_ohlcv

    def _build_canonical(self) -> Callable[..., object]:
        if self._dependencies.build_canonical is not None:
            return self._dependencies.build_canonical
        from vnalpha.ingestion.build_canonical import build_canonical_ohlcv

        return build_canonical_ohlcv

    def _build_features(self) -> Callable[..., object]:
        if self._dependencies.build_features is not None:
            return self._dependencies.build_features
        from vnalpha.features.build_features import build_features

        return build_features

    def _generate_watchlist(self) -> Callable[..., object]:
        if self._dependencies.generate_watchlist is not None:
            return self._dependencies.generate_watchlist
        from vnalpha.scoring.generate_watchlist import generate_watchlist

        return generate_watchlist

    def _build_market_regime(self) -> Callable[..., object]:
        if self._dependencies.build_market_regime is not None:
            return self._dependencies.build_market_regime
        from vnalpha.research_intelligence.regime import build_market_regime

        return build_market_regime

    def _build_sector_strength(self) -> Callable[..., object]:
        if self._dependencies.build_sector_strength is not None:
            return self._dependencies.build_sector_strength
        from vnalpha.research_intelligence.sector import build_sector_strength

        return build_sector_strength

    def _sync_daily(self) -> Callable[..., object]:
        if self._dependencies.sync_daily is not None:
            return self._dependencies.sync_daily
        from vnalpha.ingestion.ohlcv_maintenance import DailyOHLCVSyncService

        return DailyOHLCVSyncService().sync

    def _scan_ohlcv_gaps(self) -> Callable[..., object]:
        if self._dependencies.scan_ohlcv_gaps is not None:
            return self._dependencies.scan_ohlcv_gaps
        from vnalpha.ingestion.ohlcv_maintenance import OHLCVGapScanService

        return OHLCVGapScanService().scan

    def _repair_ohlcv(self) -> Callable[..., object]:
        if self._dependencies.repair_ohlcv is not None:
            return self._dependencies.repair_ohlcv
        from vnalpha.ingestion.ohlcv_repair import OHLCVRepairService

        return OHLCVRepairService().repair


def _validate_download(
    artifact: str,
    symbol: str | None,
    symbols: tuple[str, ...] | None,
    allow_all_symbols: bool,
    start: str | None,
    end: str | None,
    request_date: str | None,
    authoritative_snapshot: bool = False,
) -> None:
    if artifact not in {"symbols", "ohlcv", "index"}:
        raise DataProvisioningValidationError(
            "Supported downloads: symbols, ohlcv, index."
        )
    if request_date is not None:
        raise DataProvisioningValidationError("--date is only valid for data builds.")
    if artifact == "symbols" and (
        symbol is not None or symbols or allow_all_symbols or start or end
    ):
        raise DataProvisioningValidationError(
            "Data download symbols accepts only an optional --source."
        )
    if authoritative_snapshot and artifact != "symbols":
        raise DataProvisioningValidationError(
            "--authoritative is only valid for a symbol snapshot download."
        )
    if artifact == "ohlcv":
        selected = int(symbol is not None) + int(bool(symbols)) + int(allow_all_symbols)
        if selected != 1:
            raise DataProvisioningValidationError(
                "Data download ohlcv requires exactly one symbol selection or an explicit all-symbols policy."
            )
    if artifact == "index" and (symbols or allow_all_symbols):
        raise DataProvisioningValidationError(
            "Data download index accepts at most one index symbol."
        )


def _validate_build(
    artifact: str,
    symbol: str | None,
    symbols: tuple[str, ...] | None,
    allow_all_symbols: bool,
    start: str | None,
    end: str | None,
    source: str | None,
    request_date: str | None,
    top_n: int,
    min_score: float,
) -> None:
    if artifact not in {
        "canonical",
        "features",
        "score",
        "market-regime",
        "sector-strength",
    }:
        raise DataProvisioningValidationError(
            "Supported builds: canonical, features, score, market-regime, sector-strength."
        )
    if start is not None or end is not None or source is not None:
        raise DataProvisioningValidationError(
            "--start, --end, and --source are only valid for data downloads."
        )
    if (
        artifact in {"canonical", "features", "score"}
        and symbol is None
        and not symbols
        and not allow_all_symbols
    ):
        raise DataProvisioningValidationError(
            f"Data build {artifact} requires a symbol."
        )
    if (
        artifact in {"features", "score", "market-regime", "sector-strength"}
        and request_date is None
    ):
        raise DataProvisioningValidationError(f"Data build {artifact} requires --date.")
    if artifact == "canonical" and request_date is not None:
        raise DataProvisioningValidationError(
            "Data build canonical does not accept --date."
        )
    if artifact in {"market-regime", "sector-strength"} and (
        symbol is not None or symbols or allow_all_symbols
    ):
        raise DataProvisioningValidationError(
            f"Data build {artifact} does not accept a symbol."
        )
    if artifact == "score":
        if top_n <= 0:
            raise DataProvisioningValidationError("--top-n must be greater than zero.")
        if not isfinite(min_score) or not 0.0 <= min_score <= 1.0:
            raise DataProvisioningValidationError(
                "--min-score must be between 0 and 1."
            )


def _validate_maintenance(fields: _MaintenanceFields) -> _MaintenanceFields:
    resolved_date = (
        fields.resolved_date
        or fields.end
        or fields.start
        or resolve_date(None, conn=fields.date_conn)
    )
    if fields.operation == "sync":
        if fields.artifact != "daily":
            raise DataProvisioningValidationError("Supported sync: daily.")
        if (
            fields.symbol is not None
            or fields.symbols
            or fields.allow_all_symbols
            or fields.start is not None
            or fields.end is not None
            or fields.source is not None
        ):
            raise DataProvisioningValidationError(
                "Data sync daily accepts only an optional --date."
            )
        return _MaintenanceFields(
            operation=fields.operation,
            artifact=fields.artifact,
            symbol=fields.symbol,
            symbols=fields.symbols,
            allow_all_symbols=fields.allow_all_symbols,
            start=fields.start,
            end=fields.end,
            resolved_date=resolved_date,
            source=fields.source,
            date_conn=fields.date_conn,
        )
    if fields.artifact != "ohlcv" or fields.symbol is None:
        raise DataProvisioningValidationError(
            f"Data {fields.operation} ohlcv requires exactly one symbol."
        )
    if fields.symbols or fields.allow_all_symbols:
        raise DataProvisioningValidationError(
            f"Data {fields.operation} ohlcv requires exactly one symbol."
        )
    if fields.operation == "gaps" and fields.source is not None:
        raise DataProvisioningValidationError(
            "Data gaps ohlcv does not accept --source."
        )
    return _MaintenanceFields(
        operation=fields.operation,
        artifact=fields.artifact,
        symbol=fields.symbol,
        symbols=fields.symbols,
        allow_all_symbols=fields.allow_all_symbols,
        start=fields.start or resolved_date,
        end=fields.end or resolved_date,
        resolved_date=resolved_date,
        source=fields.source,
        date_conn=fields.date_conn,
    )


def _daily_sync_request(request: DataProvisioningRequest):
    from vnalpha.ingestion.ohlcv_maintenance import DailyOHLCVSyncRequest

    return DailyOHLCVSyncRequest(
        resolved_market_date=_required_date_value(request.date)
    )


def _gap_scan_request(request: DataProvisioningRequest):
    from vnalpha.ingestion.ohlcv_maintenance import OHLCVGapScanRequest
    from vnalpha.ingestion.trading_calendar import SessionRange

    return OHLCVGapScanRequest(
        symbol=_required_symbol(request.symbol),
        interval=request.interval,
        session_range=SessionRange(
            start=_required_date_value(request.start),
            end=_required_date_value(request.end),
        ),
    )


def _repair_request(request: DataProvisioningRequest):
    from vnalpha.ingestion.ohlcv_repair import OHLCVRepairRequest
    from vnalpha.ingestion.trading_calendar import SessionRange

    return OHLCVRepairRequest(
        symbol=_required_symbol(request.symbol),
        interval=request.interval,
        session_range=SessionRange(
            start=_required_date_value(request.start),
            end=_required_date_value(request.end),
        ),
        source=request.source,
    )


def _daily_sync_result(
    request: DataProvisioningRequest,
    correlation_id: str,
    raw: object,
) -> DataProvisioningResult:
    from vnalpha.ingestion.ohlcv_maintenance import DailyOHLCVSyncResult

    if not isinstance(raw, DailyOHLCVSyncResult):
        raise DataProvisioningAdapterError(
            "Daily sync adapter returned an invalid result."
        )
    counts = {
        "symbols": len(raw.batches),
        "inserted": raw.rows_inserted,
        "failed": sum(
            batch.status is BatchIngestionStatus.FAILED for batch in raw.batches
        ),
    }
    return _result(
        request,
        correlation_id,
        counts=counts,
        status=_provisioning_status(raw.status),
        warnings=_count_warnings(counts, ("failed", "symbols failed")),
    )


def _gap_scan_result(
    request: DataProvisioningRequest,
    correlation_id: str,
    raw: object,
) -> DataProvisioningResult:
    from vnalpha.ingestion.ohlcv_maintenance import OHLCVGapScanResult

    if not isinstance(raw, OHLCVGapScanResult):
        raise DataProvisioningAdapterError(
            "OHLCV gap adapter returned an invalid result."
        )
    true_gap_count = len(raw.report.true_gap_dates)
    counts = {
        "observed": len(raw.report.gaps),
        "true_gaps": true_gap_count,
        "persisted": raw.persisted_count,
    }
    return _result(
        request,
        correlation_id,
        counts=counts,
        status=(
            ProvisioningStatus.PARTIAL
            if true_gap_count > 0
            else ProvisioningStatus.SUCCESS
        ),
        warnings=(
            (f"{true_gap_count} unresolved true OHLCV gaps.",)
            if true_gap_count > 0
            else ()
        ),
    )


def _repair_result(
    request: DataProvisioningRequest,
    correlation_id: str,
    raw: object,
) -> DataProvisioningResult:
    from vnalpha.ingestion.ohlcv_repair import OHLCVRepairResult

    if not isinstance(raw, OHLCVRepairResult):
        raise DataProvisioningAdapterError(
            "OHLCV repair adapter returned an invalid result."
        )
    unresolved_count = len(raw.after.true_gap_dates)
    counts = {
        "before": len(raw.before.true_gap_dates),
        "fetched": len(raw.fetched_dates),
        "provider_empty": len(raw.provider_empty_dates),
        "unresolved": unresolved_count,
    }
    return _result(
        request,
        correlation_id,
        counts=counts,
        status=(
            ProvisioningStatus.PARTIAL
            if unresolved_count > 0
            else ProvisioningStatus.SUCCESS
        ),
        warnings=(
            (f"{unresolved_count} true OHLCV gaps remain unresolved.",)
            if unresolved_count > 0
            else ()
        ),
    )


def _normalize_required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DataProvisioningValidationError(f"{label} must not be empty.")
    return value.strip()


def _normalize_symbol(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    return normalized or None


def _normalize_symbols(values: tuple[str, ...] | None) -> tuple[str, ...] | None:
    if values is None:
        return None
    normalized = tuple(
        symbol for value in values if (symbol := _normalize_symbol(value))
    )
    return normalized or None


def _normalize_source(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    if not normalized:
        return None
    if normalized not in _APPROVED_SOURCES:
        approved = ", ".join(sorted(_APPROVED_SOURCES))
        raise DataProvisioningValidationError(
            f"--source must name an approved provider ({approved})."
        )
    return normalized


def _normalize_interval(value: str) -> str:
    normalized = value.strip().upper()
    if not normalized:
        raise DataProvisioningValidationError("--interval must not be empty.")
    return normalized


def _normalize_date(value: str | None, option: str) -> str | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value.strip()).isoformat()
    except (AttributeError, ValueError) as exc:
        raise DataProvisioningValidationError(
            f"{option} must use YYYY-MM-DD format."
        ) from exc


def _resolve_request_date(
    value: str | None, conn: duckdb.DuckDBPyConnection | None
) -> str | None:
    if value is None:
        return None
    try:
        return resolve_date(value, conn=conn)
    except (TypeError, ValueError, duckdb.Error) as exc:
        raise DataProvisioningValidationError(str(exc)) from exc


def _required_symbol(symbol: str | None) -> str:
    if symbol is None:
        raise DataProvisioningValidationError("Data request requires a symbol.")
    return symbol


def _requested_symbols(request: DataProvisioningRequest) -> list[str] | None:
    if request.symbols:
        return list(request.symbols)
    if request.allow_all_symbols:
        return None
    return [_required_symbol(request.symbol)]


def _required_date(value: str | None) -> str:
    if value is None:
        raise DataProvisioningValidationError("Data request requires --date.")
    return value


def _required_date_value(value: str | None) -> date:
    return date.fromisoformat(_required_date(value))


def _require_mapping(result: object) -> Mapping[str, object]:
    if not isinstance(result, Mapping):
        raise TypeError("Provisioning adapter returned an invalid result.")
    return result


def _require_ohlcv_batch(
    result: JsonValue | OHLCVBatchResult,
) -> OHLCVBatchResult:
    if not isinstance(result, OHLCVBatchResult):
        raise DataProvisioningAdapterError("OHLCV adapter returned an invalid result.")
    return result


def _provisioning_status(status: BatchIngestionStatus) -> ProvisioningStatus:
    match status:
        case BatchIngestionStatus.SUCCESS:
            return ProvisioningStatus.SUCCESS
        case BatchIngestionStatus.PARTIAL:
            return ProvisioningStatus.PARTIAL
        case BatchIngestionStatus.FAILED:
            return ProvisioningStatus.FAILED
        case unreachable:
            assert_never(unreachable)


def _ohlcv_warnings(batch: OHLCVBatchResult) -> tuple[str, ...]:
    return tuple(
        " - ".join(
            part
            for part in (
                f"{result.symbol}: {result.status.value}",
                result.message,
                result.remediation,
            )
            if part
        )
        for result in batch.symbol_results
        if result.status
        not in {SymbolIngestionStatus.SUCCESS, SymbolIngestionStatus.SKIPPED}
    )


def _ohlcv_terminal_error(batch: OHLCVBatchResult) -> str | None:
    if batch.status is BatchIngestionStatus.FAILED:
        return "No required OHLCV symbol completed."
    return None


def _counts(result: Mapping[str, object], *keys: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for key in keys:
        value = result.get(key, 0)
        try:
            counts[key] = int(value or 0)
        except (TypeError, ValueError) as exc:
            raise TypeError(f"Invalid count for {key}.") from exc
    return counts


def _partial_if_positive(
    counts: Mapping[str, int], *problem_keys: str
) -> ProvisioningStatus:
    return (
        ProvisioningStatus.PARTIAL
        if any(counts.get(key, 0) > 0 for key in problem_keys)
        else ProvisioningStatus.SUCCESS
    )


def _quality_status(quality: str, *, success_values: set[str]) -> ProvisioningStatus:
    return (
        ProvisioningStatus.SUCCESS
        if quality.upper() in success_values
        else ProvisioningStatus.PARTIAL
    )


def _count_warnings(
    counts: Mapping[str, int], *descriptions: tuple[str, str]
) -> tuple[str, ...]:
    return tuple(
        f"{counts[key]} {description}."
        for key, description in descriptions
        if counts.get(key, 0) > 0
    )


def _result(
    request: DataProvisioningRequest,
    correlation_id: str,
    *,
    status: ProvisioningStatus = ProvisioningStatus.SUCCESS,
    counts: dict[str, int] | None = None,
    warnings: tuple[str, ...] = (),
    raw_result: Mapping[str, object] | None = None,
    lineage_extra: Mapping[str, str] | None = None,
    symbol_results: tuple[SymbolIngestionResult, ...] = (),
    terminal_reason: str | None = None,
    error: str | None = None,
) -> DataProvisioningResult:
    lineage = {
        "operation": request.operation,
        "artifact": request.artifact,
        "source": request.source or "warehouse",
    }
    if raw_result is not None:
        run_id = raw_result.get("run_id") or raw_result.get("ingestion_run_id")
        if run_id:
            lineage["ingestion_run_id"] = str(run_id)
    if lineage_extra:
        lineage.update(
            {key: str(value) for key, value in lineage_extra.items() if value}
        )
    return DataProvisioningResult(
        status=status,
        operation=request.operation,
        artifact=request.artifact,
        correlation_id=correlation_id,
        counts=counts or {},
        resolved_date=request.date,
        source=request.source,
        symbol=request.symbol,
        start=request.start,
        end=request.end,
        warnings=warnings,
        requested_date=request.requested_date or request.date,
        freshness=_freshness_state(request),
        lineage=lineage,
        symbol_results=symbol_results,
        terminal_reason=terminal_reason,
        error=error,
        follow_up=(
            next(
                (
                    result.remediation
                    for result in symbol_results
                    if result.remediation is not None
                ),
                "Review warnings and rerun the bounded command if needed.",
            )
            if warnings or status is not ProvisioningStatus.SUCCESS
            else None
        ),
    )


def _freshness_state(request: DataProvisioningRequest) -> str:
    if request.operation == "build" and request.date:
        return "exact"
    if request.start or request.end:
        return "bounded_range"
    if request.operation == "build":
        return "warehouse_current"
    return "provider_default"


def _object_lineage(value: object) -> dict[str, str]:
    lineage: dict[str, str] = {}
    methodology = getattr(value, "methodology_version", None)
    if methodology:
        lineage["methodology_version"] = str(methodology)
    quality = getattr(value, "quality", None)
    if quality:
        lineage["quality"] = str(quality)
    generated_at = getattr(value, "generated_at", None)
    if generated_at:
        lineage["generated_at"] = str(generated_at)
    embedded = getattr(value, "lineage", None)
    if isinstance(embedded, Mapping):
        for key, item in embedded.items():
            if item not in (None, ""):
                lineage[str(key)] = str(item)
    return lineage


def _audit_provisioning(
    event_type: str,
    request: DataProvisioningRequest,
    status: str,
    *,
    correlation_id: str,
    counts: Mapping[str, int] | None = None,
) -> None:
    from vnalpha.observability.audit import log_audit

    log_audit(
        f"DATA_PROVISIONING_{event_type}",
        f"{request.operation} {request.artifact}",
        status=status,
        extra={
            "artifact": request.artifact,
            "operation": request.operation,
            "symbol": request.symbol,
            "correlation_id": correlation_id,
            "counts": dict(counts or {}),
        },
        object_type="data_provisioning",
        object_id=request.artifact,
    )
