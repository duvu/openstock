"""Deterministic, versioned market-regime snapshots."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Final

import duckdb

from vnalpha.observability.domain import log_market_regime_built
from vnalpha.research_intelligence.benchmark import (
    BenchmarkContext,
    load_benchmark_context,
)
from vnalpha.research_intelligence.breadth import BreadthContext, load_breadth_context
from vnalpha.research_intelligence.models import MarketRegimeSnapshot
from vnalpha.research_intelligence.policy import (
    LEGACY_MARKET_REGIME_POLICY,
    PRODUCTION_MARKET_REGIME_POLICY,
    MarketRegimePolicy,
)
from vnalpha.warehouse.repositories import upsert_market_regime_snapshot

LEGACY_METHODOLOGY_VERSION: Final = LEGACY_MARKET_REGIME_POLICY.methodology_version
METHODOLOGY_VERSION: Final = PRODUCTION_MARKET_REGIME_POLICY.methodology_version
DEFAULT_BENCHMARK: Final = "VNINDEX"


def _benchmark_is_available(
    benchmark: BenchmarkContext,
    as_of_date: date,
    policy: MarketRegimePolicy,
) -> bool:
    staleness_days = (as_of_date - benchmark.bar_date).days
    return benchmark.available and 0 <= staleness_days <= policy.maximum_staleness_days


def _classify_regime(
    benchmark: BenchmarkContext,
    breadth: BreadthContext,
    as_of_date: date,
    policy: MarketRegimePolicy,
) -> str:
    if not _benchmark_is_available(benchmark, as_of_date, policy):
        return "INSUFFICIENT_DATA"
    if not breadth.available_for(policy):
        return "INSUFFICIENT_DATA"
    if benchmark.volatility == "INSUFFICIENT_DATA":
        return "INSUFFICIENT_DATA"

    match benchmark.trend:
        case "UPTREND":
            if (
                benchmark.volatility == "NORMAL"
                and breadth.pct_above_ma20 is not None
                and breadth.pct_above_ma50 is not None
                and breadth.pct_positive_return20 is not None
                and breadth.pct_above_ma20 >= policy.risk_on_pct_above_ma20
                and breadth.pct_above_ma50 >= policy.risk_on_pct_above_ma50
                and breadth.pct_positive_return20
                >= policy.risk_on_pct_positive_return20
            ):
                return "RISK_ON"
            if benchmark.volatility == "NORMAL":
                return "CONSTRUCTIVE"
            return "MIXED"
        case "DOWNTREND":
            if (
                benchmark.volatility == "HIGH"
                or breadth.pct_above_ma20 is not None
                and breadth.pct_above_ma20 < policy.risk_off_pct_above_ma20
            ):
                return "RISK_OFF"
            return "MIXED"
        case "MIXED":
            return "MIXED"
        case "INSUFFICIENT_DATA":
            return "INSUFFICIENT_DATA"
    return "INSUFFICIENT_DATA"


def _coverage_caveats(breadth: BreadthContext, policy: MarketRegimePolicy) -> list[str]:
    caveats: list[str] = []
    if breadth.eligible_count < policy.minimum_eligible_symbols:
        caveats.append(
            "Breadth eligible rows: "
            f"{breadth.eligible_count}; {policy.minimum_eligible_symbols} required."
        )
    if breadth.coverage is None or breadth.coverage < policy.minimum_breadth_coverage:
        caveats.append(
            "Breadth coverage is below policy: "
            f"{breadth.coverage if breadth.coverage is not None else 'missing'}; "
            f"{policy.minimum_breadth_coverage} required."
        )
    if (
        breadth.exchange_coverage is None
        or breadth.exchange_coverage < policy.minimum_exchange_coverage
    ):
        caveats.append(
            "Exchange coverage is below policy: "
            f"{breadth.exchange_coverage if breadth.exchange_coverage is not None else 'missing'}; "
            f"{policy.minimum_exchange_coverage} required."
        )
    if (
        breadth.liquidity_coverage is None
        or breadth.liquidity_coverage < policy.minimum_liquidity_coverage
    ):
        caveats.append(
            "Liquidity coverage is below policy: "
            f"{breadth.liquidity_coverage if breadth.liquidity_coverage is not None else 'missing'}; "
            f"{policy.minimum_liquidity_coverage} required."
        )
    return caveats


def _lineage(
    benchmark: BenchmarkContext,
    breadth: BreadthContext,
    policy: MarketRegimePolicy,
) -> dict[str, str]:
    return {
        "benchmark_input": "canonical_ohlcv",
        "benchmark_row_count": str(benchmark.row_count),
        "benchmark_bar_date": benchmark.bar_date.isoformat(),
        "benchmark_freshness": benchmark.freshness,
        "breadth_input": f"{breadth.membership_basis},feature_snapshot",
        "breadth_membership_basis": breadth.membership_basis,
        "breadth_membership_resolver_version": (
            breadth.membership_resolver_version or ""
        ),
        "breadth_active_count": str(breadth.active_count),
        "breadth_eligible_count": str(breadth.eligible_count),
        "breadth_excluded_count": str(breadth.excluded_count),
        "breadth_coverage": "" if breadth.coverage is None else str(breadth.coverage),
        "exchange_coverage": ""
        if breadth.exchange_coverage is None
        else str(breadth.exchange_coverage),
        "exchange_metadata_coverage": ""
        if breadth.exchange_metadata_coverage is None
        else str(breadth.exchange_metadata_coverage),
        "liquidity_candidate_count": str(breadth.liquidity_candidate_count),
        "liquidity_coverage": ""
        if breadth.liquidity_coverage is None
        else str(breadth.liquidity_coverage),
        "advancers": "" if breadth.advancers is None else str(breadth.advancers),
        "decliners": "" if breadth.decliners is None else str(breadth.decliners),
        "unchanged": "" if breadth.unchanged is None else str(breadth.unchanged),
        "near_52w_high_count": ""
        if breadth.near_52w_high_count is None
        else str(breadth.near_52w_high_count),
        "median_return20": ""
        if breadth.median_return20 is None
        else str(breadth.median_return20),
        "return20_dispersion": ""
        if breadth.return20_dispersion is None
        else str(breadth.return20_dispersion),
        "excluded_symbols": ",".join(breadth.excluded_symbols),
        "security_type_excluded_symbols": ",".join(
            breadth.security_type_excluded_symbols
        ),
        "exclusion_counts": ",".join(
            f"{reason}:{count}"
            for reason, count in sorted(breadth.exclusion_counts.items())
        ),
        "policy_minimum_eligible_symbols": str(policy.minimum_eligible_symbols),
        "policy_minimum_breadth_coverage": str(policy.minimum_breadth_coverage),
        "policy_minimum_exchange_coverage": str(policy.minimum_exchange_coverage),
        "policy_minimum_liquidity_coverage": str(policy.minimum_liquidity_coverage),
        "policy_minimum_average_traded_value": str(policy.minimum_average_traded_value),
        "policy_allowed_feature_profiles": ",".join(policy.allowed_feature_profiles),
        "policy_allowed_security_types": ",".join(policy.allowed_security_types),
        "methodology_version": policy.methodology_version,
    }


def build_market_regime(
    conn: duckdb.DuckDBPyConnection,
    as_of_date: date,
    *,
    benchmark_symbol: str = DEFAULT_BENCHMARK,
    generated_at: datetime | None = None,
    policy: MarketRegimePolicy = PRODUCTION_MARKET_REGIME_POLICY,
) -> MarketRegimeSnapshot:
    """Build and persist one deterministic snapshot under a versioned policy."""
    benchmark = load_benchmark_context(
        conn,
        as_of_date,
        benchmark_symbol,
        minimum_ma50_slope=policy.minimum_ma50_slope,
        high_volatility_threshold=policy.high_volatility_threshold,
    )
    breadth = load_breadth_context(conn, as_of_date, benchmark_symbol, policy=policy)
    caveats = list(benchmark.caveats)
    if (as_of_date - benchmark.bar_date).days > policy.maximum_staleness_days:
        caveats.append(
            f"Benchmark exceeds maximum staleness of {policy.maximum_staleness_days} days."
        )
    caveats.extend(_coverage_caveats(breadth, policy))
    regime = _classify_regime(benchmark, breadth, as_of_date, policy)
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
        regime=regime,
        trend=benchmark.trend,
        volatility=benchmark.volatility,
        quality=(
            "COMPLETE"
            if regime != "INSUFFICIENT_DATA" and not caveats
            else "INCOMPLETE"
        ),
        caveats=tuple(caveats),
        lineage=_lineage(benchmark, breadth, policy),
        methodology_version=policy.methodology_version,
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
