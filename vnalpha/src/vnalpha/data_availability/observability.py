"""Data availability observability — structured events for ensure pipeline."""

from __future__ import annotations

from vnalpha.observability.audit import log_audit


def log_ensure_started(symbol: str, target_date: str) -> None:
    log_audit(
        "DATA_ENSURE_STARTED",
        f"Data provisioning started for {symbol} on {target_date}",
        extra={"symbol": symbol, "target_date": target_date},
    )


def log_ensure_cache_hit(symbol: str, target_date: str) -> None:
    log_audit(
        "DATA_ENSURE_CACHE_HIT",
        f"Cache hit: fresh candidate_score exists for {symbol} on {target_date}",
        status="OK",
        extra={"symbol": symbol, "target_date": target_date},
    )


def log_ensure_symbols_sync_started(symbol: str) -> None:
    log_audit(
        "DATA_ENSURE_SYMBOLS_SYNC_STARTED",
        f"Syncing symbol_master for {symbol}",
        extra={"symbol": symbol},
    )


def log_ensure_symbols_sync_succeeded(symbol: str) -> None:
    log_audit(
        "DATA_ENSURE_SYMBOLS_SYNC_SUCCEEDED",
        f"symbol_master sync succeeded for {symbol}",
        status="OK",
        extra={"symbol": symbol},
    )


def log_ensure_symbols_sync_failed(symbol: str, exc: BaseException) -> None:
    log_audit(
        "DATA_ENSURE_SYMBOLS_SYNC_FAILED",
        f"symbol_master sync failed for {symbol}: {exc}",
        status="FAILED",
        level="ERROR",
        extra={"symbol": symbol, "error": str(exc)},
    )


def log_ensure_ohlcv_sync_started(symbol: str) -> None:
    log_audit(
        "DATA_ENSURE_SYMBOL_OHLCV_SYNC_STARTED",
        f"Syncing OHLCV for {symbol}",
        extra={"symbol": symbol},
    )


def log_ensure_ohlcv_sync_succeeded(symbol: str, inserted: int) -> None:
    log_audit(
        "DATA_ENSURE_SYMBOL_OHLCV_SYNC_SUCCEEDED",
        f"OHLCV sync succeeded for {symbol}: {inserted} rows inserted",
        status="OK",
        extra={"symbol": symbol, "inserted": inserted},
    )


def log_ensure_ohlcv_sync_failed(symbol: str, exc: BaseException) -> None:
    log_audit(
        "DATA_ENSURE_SYMBOL_OHLCV_SYNC_FAILED",
        f"OHLCV sync failed for {symbol}: {exc}",
        status="FAILED",
        level="ERROR",
        extra={"symbol": symbol, "error": str(exc)},
    )


def log_ensure_canonical_build_started(symbol: str) -> None:
    log_audit(
        "DATA_ENSURE_CANONICAL_BUILD_STARTED",
        f"Building canonical OHLCV for {symbol}",
        extra={"symbol": symbol},
    )


def log_ensure_canonical_build_succeeded(symbol: str, upserted: int) -> None:
    log_audit(
        "DATA_ENSURE_CANONICAL_BUILD_SUCCEEDED",
        f"Canonical build succeeded for {symbol}: {upserted} rows upserted",
        status="OK",
        extra={"symbol": symbol, "upserted": upserted},
    )


def log_ensure_canonical_build_failed(symbol: str, exc: BaseException) -> None:
    log_audit(
        "DATA_ENSURE_CANONICAL_BUILD_FAILED",
        f"Canonical build failed for {symbol}: {exc}",
        status="FAILED",
        level="ERROR",
        extra={"symbol": symbol, "error": str(exc)},
    )


def log_ensure_benchmark_sync_started(benchmark: str) -> None:
    log_audit(
        "DATA_ENSURE_BENCHMARK_SYNC_STARTED",
        f"Syncing benchmark OHLCV for {benchmark}",
        extra={"benchmark": benchmark},
    )


def log_ensure_benchmark_sync_succeeded(benchmark: str, inserted: int) -> None:
    log_audit(
        "DATA_ENSURE_BENCHMARK_SYNC_SUCCEEDED",
        f"Benchmark sync succeeded for {benchmark}: {inserted} rows inserted",
        status="OK",
        extra={"benchmark": benchmark, "inserted": inserted},
    )


def log_ensure_benchmark_sync_failed(benchmark: str, exc: BaseException) -> None:
    log_audit(
        "DATA_ENSURE_BENCHMARK_SYNC_FAILED",
        f"Benchmark sync failed for {benchmark}: {exc}",
        status="FAILED",
        level="ERROR",
        extra={"benchmark": benchmark, "error": str(exc)},
    )


def log_ensure_feature_build_started(symbol: str) -> None:
    log_audit(
        "DATA_ENSURE_FEATURE_BUILD_STARTED",
        f"Building features for {symbol}",
        extra={"symbol": symbol},
    )


def log_ensure_feature_build_succeeded(symbol: str) -> None:
    log_audit(
        "DATA_ENSURE_FEATURE_BUILD_SUCCEEDED",
        f"Feature build succeeded for {symbol}",
        status="OK",
        extra={"symbol": symbol},
    )


def log_ensure_feature_build_failed(symbol: str, exc: BaseException) -> None:
    log_audit(
        "DATA_ENSURE_FEATURE_BUILD_FAILED",
        f"Feature build failed for {symbol}: {exc}",
        status="FAILED",
        level="ERROR",
        extra={"symbol": symbol, "error": str(exc)},
    )


def log_ensure_score_started(symbol: str) -> None:
    log_audit(
        "DATA_ENSURE_SCORE_STARTED",
        f"Scoring {symbol}",
        extra={"symbol": symbol},
    )


def log_ensure_score_succeeded(symbol: str) -> None:
    log_audit(
        "DATA_ENSURE_SCORE_SUCCEEDED",
        f"Scoring succeeded for {symbol}",
        status="OK",
        extra={"symbol": symbol},
    )


def log_ensure_score_failed(symbol: str, exc: BaseException) -> None:
    log_audit(
        "DATA_ENSURE_SCORE_FAILED",
        f"Scoring failed for {symbol}: {exc}",
        status="FAILED",
        level="ERROR",
        extra={"symbol": symbol, "error": str(exc)},
    )


def log_ensure_ready(symbol: str, target_date: str, actions: list[str]) -> None:
    log_audit(
        "DATA_ENSURE_READY",
        f"Data ready for {symbol} on {target_date}",
        status="OK",
        extra={"symbol": symbol, "target_date": target_date, "actions": actions},
    )


def log_ensure_partial(symbol: str, target_date: str, warnings: list[str]) -> None:
    log_audit(
        "DATA_ENSURE_PARTIAL",
        f"Data partially ready for {symbol} on {target_date}: {warnings}",
        status="WARN",
        level="WARNING",
        extra={"symbol": symbol, "target_date": target_date, "warnings": warnings},
    )


def log_ensure_failed(symbol: str, target_date: str, errors: list[str]) -> None:
    log_audit(
        "DATA_ENSURE_FAILED",
        f"Data provisioning failed for {symbol} on {target_date}: {errors}",
        status="FAILED",
        level="ERROR",
        extra={"symbol": symbol, "target_date": target_date, "errors": errors},
    )
