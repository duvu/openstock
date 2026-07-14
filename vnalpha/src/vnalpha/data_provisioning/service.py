from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Callable

import duckdb

from vnalpha.core.dates import resolve_date
from vnalpha.observability.context import get_correlation_id, set_correlation_id


class ProvisioningStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class DataProvisioningValidationError(ValueError):
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
    benchmark: str = "VNINDEX"
    requested_date: str | None = None


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


@dataclass(frozen=True, slots=True)
class DataProvisioningDependencies:
    sync_symbols: Callable[..., dict] | None = None
    sync_ohlcv: Callable[..., dict] | None = None
    sync_index: Callable[..., dict] | None = None
    build_canonical: Callable[..., dict] | None = None
    build_features: Callable[..., dict] | None = None
    generate_watchlist: Callable[..., dict] | None = None
    build_market_regime: Callable[..., object] | None = None
    build_sector_strength: Callable[..., object] | None = None


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
        _audit_provisioning("REQUESTED", normalized, "STARTED")
        try:
            result = self._execute(normalized, correlation_id)
            _audit_provisioning(result.status.value, normalized, result.status.value)
            return result
        except Exception:
            _audit_provisioning("FAILED", normalized, "FAILED")
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
                },
                error="Data provisioning did not complete. Review the correlated audit record.",
                follow_up="Review the correlated audit record and retry after correcting the input or provider.",
            )

    @classmethod
    def validate_request(cls, request: DataProvisioningRequest) -> None:
        cls._validate_fields(request, date_conn=None)

    def _validate(self, request: DataProvisioningRequest) -> DataProvisioningRequest:
        return self._validate_fields(request, date_conn=self.conn)

    @classmethod
    def _validate_fields(
        cls, request: DataProvisioningRequest, *, date_conn
    ) -> DataProvisioningRequest:
        operation = request.operation.strip().lower()
        artifact = request.artifact.strip().lower()
        symbol = _normalize_symbol(request.symbol)
        symbols = _normalize_symbols(request.symbols)
        start = _normalize_date(request.start, "--start")
        end = _normalize_date(request.end, "--end")
        resolved_date = _resolve_request_date(request.date, date_conn)
        source = _normalize_source(request.source)
        interval = _normalize_interval(request.interval)

        if start and end and start > end:
            raise DataProvisioningValidationError("--start must not be after --end.")
        if operation not in {"download", "build"}:
            raise DataProvisioningValidationError(
                "Operation must be 'download' or 'build'."
            )
        if operation == "download":
            _validate_download(artifact, symbol, symbols, resolved_date)
        else:
            _validate_build(
                artifact,
                symbol,
                symbols,
                request.allow_all_symbols,
                start,
                end,
                source,
                resolved_date,
            )

        return DataProvisioningRequest(
            operation=operation,
            artifact=artifact,
            symbol=symbol,
            symbols=symbols,
            allow_all_symbols=request.allow_all_symbols,
            start=start,
            end=end,
            date=resolved_date,
            source=source,
            interval=interval,
            top_n=request.top_n,
            min_score=request.min_score,
            benchmark=_normalize_symbol(request.benchmark) or "VNINDEX",
            requested_date=request.requested_date or request.date,
        )

    def _execute(
        self, request: DataProvisioningRequest, correlation_id: str
    ) -> DataProvisioningResult:
        match request.operation, request.artifact:
            case "download", "symbols":
                result = self._sync_symbols()(self.conn, source=request.source)
                return _result(
                    request,
                    correlation_id,
                    counts=_counts(result, "synced", "errors"),
                )
            case "download", "ohlcv":
                result = self._sync_ohlcv()(
                    self.conn,
                    universe=_requested_symbols(request),
                    start=request.start,
                    end=request.end,
                    source=request.source,
                    interval=request.interval,
                )
                return _result(
                    request,
                    correlation_id,
                    counts=_counts(result, "inserted", "skipped"),
                )
            case "download", "index":
                result = self._sync_index()(
                    self.conn,
                    symbol=request.symbol or "VNINDEX",
                    start=request.start,
                    end=request.end,
                    source=request.source,
                    interval=request.interval,
                )
                return _result(
                    request,
                    correlation_id,
                    counts=_counts(result, "inserted", "skipped"),
                )
            case "build", "canonical":
                result = self._build_canonical()(
                    self.conn, symbol=request.symbol, interval=request.interval
                )
                return _result(
                    request,
                    correlation_id,
                    counts=_counts(result, "upserted", "rejected"),
                )
            case "build", "features":
                result = self._build_features()(
                    self.conn,
                    target_date=_required_date(request.date),
                    universe=_requested_symbols(request),
                    benchmark_symbol=request.benchmark,
                )
                return _result(
                    request,
                    correlation_id,
                    counts=_counts(result, "built", "skipped"),
                )
            case "build", "score":
                result = self._generate_watchlist()(
                    self.conn,
                    date=_required_date(request.date),
                    universe=_requested_symbols(request),
                    top_n=request.top_n,
                    min_score=request.min_score,
                )
                return _result(
                    request,
                    correlation_id,
                    counts=_counts(result, "scored", "saved"),
                )
            case "build", "market-regime":
                snapshot = self._build_market_regime()(
                    self.conn, _required_date(request.date)
                )
                quality = str(getattr(snapshot, "quality", "PARTIAL"))
                return _result(
                    request,
                    correlation_id,
                    status=_quality_status(quality),
                    warnings=()
                    if quality == "COMPLETE"
                    else (f"Market-regime quality is {quality}.",),
                )
            case "build", "sector-strength":
                build_result = self._build_sector_strength()(
                    self.conn, _required_date(request.date)
                )
                quality = str(getattr(build_result, "quality", "PARTIAL"))
                snapshots = getattr(build_result, "snapshots", ())
                return _result(
                    request,
                    correlation_id,
                    status=_quality_status(quality),
                    counts={"sectors": len(snapshots)},
                    warnings=()
                    if quality == "COMPLETE"
                    else (f"Sector-strength quality is {quality}.",),
                )
            case unreachable:
                raise DataProvisioningValidationError(
                    f"Unsupported data request: {unreachable[0]} {unreachable[1]}."
                )

    def _correlation_id(self) -> str:
        correlation_id = get_correlation_id()
        if correlation_id in {"", "unset"}:
            return set_correlation_id()
        return correlation_id

    def _sync_symbols(self) -> Callable[..., dict]:
        if self._dependencies.sync_symbols is not None:
            return self._dependencies.sync_symbols
        from vnalpha.ingestion.sync_symbols import sync_symbols

        return sync_symbols

    def _sync_ohlcv(self) -> Callable[..., dict]:
        if self._dependencies.sync_ohlcv is not None:
            return self._dependencies.sync_ohlcv
        from vnalpha.ingestion.sync_ohlcv import sync_ohlcv

        return sync_ohlcv

    def _sync_index(self) -> Callable[..., dict]:
        if self._dependencies.sync_index is not None:
            return self._dependencies.sync_index
        from vnalpha.ingestion.sync_index import sync_index_ohlcv

        return sync_index_ohlcv

    def _build_canonical(self) -> Callable[..., dict]:
        if self._dependencies.build_canonical is not None:
            return self._dependencies.build_canonical
        from vnalpha.ingestion.build_canonical import build_canonical_ohlcv

        return build_canonical_ohlcv

    def _build_features(self) -> Callable[..., dict]:
        if self._dependencies.build_features is not None:
            return self._dependencies.build_features
        from vnalpha.features.build_features import build_features

        return build_features

    def _generate_watchlist(self) -> Callable[..., dict]:
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


def _validate_download(
    artifact: str,
    symbol: str | None,
    symbols: tuple[str, ...] | None,
    request_date: str | None,
) -> None:
    if artifact not in {"symbols", "ohlcv", "index"}:
        raise DataProvisioningValidationError(
            "Supported downloads: symbols, ohlcv, index."
        )
    if artifact == "ohlcv" and symbol is None and not symbols:
        raise DataProvisioningValidationError("Data download ohlcv requires a symbol.")
    if request_date is not None:
        raise DataProvisioningValidationError("--date is only valid for data builds.")


def _validate_build(
    artifact: str,
    symbol: str | None,
    symbols: tuple[str, ...] | None,
    allow_all_symbols: bool,
    start: str | None,
    end: str | None,
    source: str | None,
    request_date: str | None,
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
    if artifact in {"market-regime", "sector-strength"} and (
        symbol is not None or symbols
    ):
        raise DataProvisioningValidationError(
            f"Data build {artifact} does not accept a symbol."
        )


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
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.upper() not in {
        "KBS",
        "VCI",
        "MSN",
        "DNSE",
        "TCBS",
        "FMARKET",
        "FMP",
    }:
        raise DataProvisioningValidationError(
            "--source must name an approved provider (KBS, VCI, MSN, DNSE, or TCBS)."
        )
    return normalized.upper()


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
    except ValueError as exc:
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
    except (TypeError, ValueError) as exc:
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


def _counts(result: dict, *keys: str) -> dict[str, int]:
    return {key: int(result.get(key, 0)) for key in keys}


def _quality_status(quality: str) -> ProvisioningStatus:
    return (
        ProvisioningStatus.SUCCESS
        if quality == "COMPLETE"
        else ProvisioningStatus.PARTIAL
    )


def _result(
    request: DataProvisioningRequest,
    correlation_id: str,
    *,
    status: ProvisioningStatus = ProvisioningStatus.SUCCESS,
    counts: dict[str, int] | None = None,
    warnings: tuple[str, ...] = (),
) -> DataProvisioningResult:
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
        freshness=request.date or request.end or "unknown",
        lineage={
            "operation": request.operation,
            "artifact": request.artifact,
            "source": request.source or "warehouse",
        },
        follow_up=(
            "Review warnings and rerun the bounded command if needed."
            if warnings or status is not ProvisioningStatus.SUCCESS
            else None
        ),
    )


def _audit_provisioning(
    event_type: str, request: DataProvisioningRequest, status: str
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
        },
        object_type="data_provisioning",
        object_id=request.artifact,
    )
