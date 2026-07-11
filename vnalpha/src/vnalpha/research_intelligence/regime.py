"""Deterministic persisted market-regime snapshots."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Final

import duckdb

from vnalpha.observability.domain import log_market_regime_built
from vnalpha.research_intelligence.benchmark import (
    BenchmarkContext,
    load_benchmark_context,
)
from vnalpha.research_intelligence.breadth import (
    MINIMUM_BREADTH_ROWS,
    BreadthContext,
    load_breadth_context,
)
from vnalpha.research_intelligence.models import MarketRegimeSnapshot
from vnalpha.warehouse.repositories import upsert_market_regime_snapshot

METHODOLOGY_VERSION: Final = "market-regime-v1"
DEFAULT_BENCHMARK: Final = "VNINDEX"


def _classify_regime(
    benchmark: BenchmarkContext,
    breadth: BreadthContext,
) -> str:
    if not benchmark.available or not breadth.available:
        return "INSUFFICIENT_DATA"
    match benchmark.volatility:
        case "INSUFFICIENT_DATA":
            return "INSUFFICIENT_DATA"
        case "HIGH" | "NORMAL":
            pass
    match benchmark.trend:
        case "UPTREND":
            if (
                benchmark.volatility == "NORMAL"
                and breadth.pct_above_ma20 is not None
                and breadth.pct_above_ma50 is not None
                and breadth.pct_above_ma20 >= 0.60
                and breadth.pct_above_ma50 >= 0.50
            ):
                return "RISK_ON"
            if benchmark.volatility == "NORMAL":
                return "CONSTRUCTIVE"
            return "MIXED"
        case "DOWNTREND":
            if (
                benchmark.volatility == "HIGH"
                or breadth.pct_above_ma20 is not None
                and breadth.pct_above_ma20 < 0.40
            ):
                return "RISK_OFF"
            return "MIXED"
        case "MIXED":
            return "MIXED"
        case "INSUFFICIENT_DATA":
            return "INSUFFICIENT_DATA"


def build_market_regime(
    conn: duckdb.DuckDBPyConnection,
    as_of_date: date,
    *,
    benchmark_symbol: str = DEFAULT_BENCHMARK,
    generated_at: datetime | None = None,
) -> MarketRegimeSnapshot:
    """Build and persist a deterministic market-regime snapshot for one date."""
    benchmark = load_benchmark_context(conn, as_of_date, benchmark_symbol)
    breadth = load_breadth_context(conn, as_of_date, benchmark_symbol)
    caveats = list(benchmark.caveats)
    if not breadth.available:
        caveats.append(
            f"Breadth eligible rows: {breadth.eligible_count}; {MINIMUM_BREADTH_ROWS} required."
        )
    if breadth.excluded_symbols:
        caveats.append("Breadth excludes nonexact or unusable feature rows.")
    snapshot = MarketRegimeSnapshot(
        as_of_date=as_of_date,
        benchmark_symbol=benchmark_symbol,
        benchmark_bar_date=benchmark.bar_date,
        close=benchmark.close,
        ma20=benchmark.ma20,
        ma50=benchmark.ma50,
        ma50_slope=benchmark.ma50_slope,
        return20=benchmark.return20,
        return60=benchmark.return60,
        volatility20=benchmark.volatility20,
        breadth_active_count=breadth.active_count,
        breadth_eligible_count=breadth.eligible_count,
        breadth_excluded_count=breadth.excluded_count,
        breadth_coverage=breadth.coverage,
        pct_above_ma20=breadth.pct_above_ma20,
        pct_above_ma50=breadth.pct_above_ma50,
        pct_positive_return20=breadth.pct_positive_return20,
        regime=_classify_regime(benchmark, breadth),
        trend=benchmark.trend,
        volatility=benchmark.volatility,
        quality="COMPLETE" if not caveats else "INCOMPLETE",
        caveats=tuple(caveats),
        lineage={
            "benchmark_input": "canonical_ohlcv",
            "benchmark_row_count": str(benchmark.row_count),
            "benchmark_bar_date": benchmark.bar_date.isoformat(),
            "benchmark_freshness": benchmark.freshness,
            "breadth_input": "feature_snapshot",
            "breadth_active_count": str(breadth.active_count),
            "breadth_eligible_count": str(breadth.eligible_count),
            "breadth_excluded_count": str(breadth.excluded_count),
            "breadth_coverage": ""
            if breadth.coverage is None
            else str(breadth.coverage),
            "excluded_symbols": ",".join(breadth.excluded_symbols),
        },
        methodology_version=METHODOLOGY_VERSION,
        generated_at=generated_at or datetime.now(timezone.utc),
    )
    upsert_market_regime_snapshot(conn, snapshot)
    log_market_regime_built(
        snapshot.as_of_date.isoformat(),
        snapshot.regime,
        snapshot.quality,
        snapshot.breadth_eligible_count,
        len(snapshot.caveats),
        snapshot.methodology_version,
    )
    return snapshot
