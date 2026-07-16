"""Policy-aware market breadth calculations for one research as-of date."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from statistics import median, pstdev
from types import MappingProxyType

import duckdb

from vnalpha.research_intelligence.policy import (
    LEGACY_MARKET_REGIME_POLICY,
    MarketRegimePolicy,
)

MINIMUM_BREADTH_ROWS = 5


@dataclass(frozen=True, slots=True)
class BreadthContext:
    active_count: int
    eligible_count: int
    excluded_count: int
    coverage: float | None
    exchange_coverage: float | None
    exchange_metadata_coverage: float | None
    liquidity_candidate_count: int
    liquidity_coverage: float | None
    pct_above_ma20: float | None
    pct_above_ma50: float | None
    pct_positive_return20: float | None
    advancers: int | None
    decliners: int | None
    unchanged: int | None
    near_52w_high_count: int | None
    median_return20: float | None
    return20_dispersion: float | None
    excluded_symbols: tuple[str, ...]
    security_type_excluded_symbols: tuple[str, ...]
    exclusion_counts: Mapping[str, int]
    membership_basis: str = "symbol_master"
    membership_resolver_version: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "excluded_symbols", tuple(self.excluded_symbols))
        object.__setattr__(
            self,
            "security_type_excluded_symbols",
            tuple(self.security_type_excluded_symbols),
        )
        object.__setattr__(
            self, "exclusion_counts", MappingProxyType(dict(self.exclusion_counts))
        )

    @property
    def available(self) -> bool:
        """Legacy compatibility check; production callers use ``available_for``."""
        return self.available_for(LEGACY_MARKET_REGIME_POLICY)

    def available_for(self, policy: MarketRegimePolicy) -> bool:
        """Whether the context satisfies every hard gate in ``policy``."""
        return (
            self.eligible_count >= policy.minimum_eligible_symbols
            and self.coverage is not None
            and self.coverage >= policy.minimum_breadth_coverage
            and self.exchange_coverage is not None
            and self.exchange_coverage >= policy.minimum_exchange_coverage
            and self.liquidity_coverage is not None
            and self.liquidity_coverage >= policy.minimum_liquidity_coverage
        )


def _as_date(value: date | datetime) -> date:
    return value.date() if isinstance(value, datetime) else value


def _security_type_allowed(
    security_type: str | None, policy: MarketRegimePolicy
) -> bool:
    normalized = (security_type or "").strip().upper()
    if not normalized:
        return policy.allow_missing_security_type
    return normalized in policy.allowed_security_types


def _empty_context(
    *,
    active_count: int,
    excluded_symbols: list[str],
    security_type_excluded_symbols: list[str],
    exclusion_counts: Counter[str],
    liquidity_candidate_count: int,
    coverage: float | None,
    exchange_coverage: float | None,
    exchange_metadata_coverage: float | None,
    liquidity_coverage: float | None,
    membership_basis: str = "symbol_master",
    membership_resolver_version: str | None = None,
) -> BreadthContext:
    return BreadthContext(
        active_count=active_count,
        eligible_count=0,
        excluded_count=len(excluded_symbols),
        coverage=coverage,
        exchange_coverage=exchange_coverage,
        exchange_metadata_coverage=exchange_metadata_coverage,
        liquidity_candidate_count=liquidity_candidate_count,
        liquidity_coverage=liquidity_coverage,
        pct_above_ma20=None,
        pct_above_ma50=None,
        pct_positive_return20=None,
        advancers=None,
        decliners=None,
        unchanged=None,
        near_52w_high_count=None,
        median_return20=None,
        return20_dispersion=None,
        excluded_symbols=tuple(excluded_symbols),
        security_type_excluded_symbols=tuple(security_type_excluded_symbols),
        exclusion_counts=dict(exclusion_counts),
        membership_basis=membership_basis,
        membership_resolver_version=membership_resolver_version,
    )


def _load_pit_membership(
    conn: duckdb.DuckDBPyConnection,
    as_of_date: date,
) -> tuple[list[tuple[str, str | None, str | None]], str, str | None]:
    """Return (rows, membership_basis, resolver_version).

    Rows are (symbol, exchange, security_type) for the as-of active universe.
    Uses the point-in-time classification history when available; otherwise
    falls back to the current ``symbol_master`` active projection.
    """
    from vnalpha.warehouse.point_in_time import history_is_available, resolve_universe

    if history_is_available(conn):
        universe = resolve_universe(conn, as_of_date)
        rows: list[tuple[str, str | None, str | None]] = []
        for symbol in universe.symbols:
            classification = universe.get(symbol)
            if classification is None:
                continue
            if (classification.lifecycle_status or "ACTIVE").upper() != "ACTIVE":
                continue
            rows.append(
                (symbol, classification.exchange, classification.security_type)
            )
        return rows, "symbol_classification_history", universe.resolver_version

    fallback = conn.execute(
        """
        SELECT symbol, exchange, security_type
        FROM symbol_master
        WHERE is_active = TRUE
          AND COALESCE(lifecycle_status, 'ACTIVE') = 'ACTIVE'
        ORDER BY symbol
        """
    ).fetchall()
    return fallback, "symbol_master", None


def load_breadth_context(
    conn: duckdb.DuckDBPyConnection,
    as_of_date: date,
    benchmark_symbol: str,
    *,
    policy: MarketRegimePolicy = LEGACY_MARKET_REGIME_POLICY,
) -> BreadthContext:
    """Calculate breadth from policy-eligible active symbols and feature evidence.

    Membership, exchange and security type are resolved point-in-time from
    ``symbol_classification_history`` for the requested ``as_of_date`` when that
    history exists, so a symbol listed after the date is excluded and one
    delisted on/before it is dropped. When no classification history exists the
    loader falls back to the current ``symbol_master`` projection (compat path
    for legacy/current-only warehouses).
    """
    membership_rows, membership_basis, membership_resolver_version = (
        _load_pit_membership(conn, as_of_date)
    )

    active_rows: list[tuple[str, str | None]] = []
    security_type_excluded_symbols: list[str] = []
    for symbol, exchange, security_type in membership_rows:
        if symbol == benchmark_symbol:
            continue
        if not _security_type_allowed(security_type, policy):
            security_type_excluded_symbols.append(symbol)
            continue
        active_rows.append((symbol, exchange.strip() if exchange else None))

    feature_rows = {
        row[0]: row[1:]
        for row in conn.execute(
            """
            SELECT symbol, close, ma20, ma50, return_20d, volume_ma20,
                   distance_to_52w_high, as_of_bar_date, feature_data_status,
                   feature_profile, neutral_completeness
            FROM feature_snapshot
            WHERE date = ?
            ORDER BY symbol
            """,
            [as_of_date],
        ).fetchall()
    }

    usable_rows: list[tuple[float, float, float, float, float | None]] = []
    eligible_exchanges: set[str] = set()
    active_exchanges = {exchange for _, exchange in active_rows if exchange}
    eligible_with_exchange = 0
    exclusions: list[str] = []
    exclusion_counts: Counter[str] = Counter()
    liquidity_candidate_count = 0

    for symbol, exchange in active_rows:
        row = feature_rows.get(symbol)
        if row is None:
            exclusions.append(symbol)
            exclusion_counts["MISSING_FEATURE"] += 1
            continue
        (
            close,
            ma20,
            ma50,
            return20,
            volume_ma20,
            distance_to_52w_high,
            bar_date,
            feature_status,
            feature_profile,
            neutral_completeness,
        ) = row
        if feature_profile not in policy.allowed_feature_profiles:
            exclusions.append(symbol)
            exclusion_counts["PROFILE_NOT_ALLOWED"] += 1
            continue
        if neutral_completeness != "COMPLETE":
            exclusions.append(symbol)
            exclusion_counts["INCOMPLETE_FEATURE_PROFILE"] += 1
            continue
        if bar_date is None:
            exclusions.append(symbol)
            exclusion_counts["MISSING_BAR_DATE"] += 1
            continue
        staleness_days = (as_of_date - _as_date(bar_date)).days
        if staleness_days < 0 or staleness_days > policy.maximum_staleness_days:
            exclusions.append(symbol)
            exclusion_counts["STALE_FEATURE"] += 1
            continue
        if feature_status not in {"EXACT_DATE", "STALE_DATE"}:
            exclusions.append(symbol)
            exclusion_counts["UNUSABLE_FEATURE_STATUS"] += 1
            continue
        if any(value is None for value in (close, ma20, ma50, return20)):
            exclusions.append(symbol)
            exclusion_counts["MISSING_REQUIRED_VALUE"] += 1
            continue

        liquidity_candidate_count += 1
        average_traded_value = (
            float(close) * float(volume_ma20) if volume_ma20 is not None else None
        )
        if policy.minimum_average_traded_value > 0 and (
            average_traded_value is None
            or average_traded_value < policy.minimum_average_traded_value
        ):
            exclusions.append(symbol)
            exclusion_counts["LOW_LIQUIDITY"] += 1
            continue

        usable_rows.append(
            (
                float(close),
                float(ma20),
                float(ma50),
                float(return20),
                None if distance_to_52w_high is None else float(distance_to_52w_high),
            )
        )
        if exchange:
            eligible_exchanges.add(exchange)
            eligible_with_exchange += 1

    active_count = len(active_rows)
    eligible_count = len(usable_rows)
    coverage = eligible_count / active_count if active_count else None
    represented_exchange_coverage = (
        len(eligible_exchanges) / len(active_exchanges) if active_exchanges else 0.0
    )
    exchange_metadata_coverage = (
        eligible_with_exchange / eligible_count if eligible_count else 0.0
    )
    exchange_coverage = min(represented_exchange_coverage, exchange_metadata_coverage)
    liquidity_coverage = (
        eligible_count / liquidity_candidate_count if liquidity_candidate_count else 0.0
    )

    if not usable_rows:
        return _empty_context(
            active_count=active_count,
            excluded_symbols=exclusions,
            security_type_excluded_symbols=security_type_excluded_symbols,
            exclusion_counts=exclusion_counts,
            liquidity_candidate_count=liquidity_candidate_count,
            coverage=coverage,
            exchange_coverage=exchange_coverage,
            exchange_metadata_coverage=exchange_metadata_coverage,
            liquidity_coverage=liquidity_coverage,
            membership_basis=membership_basis,
            membership_resolver_version=membership_resolver_version,
        )

    returns = [row[3] for row in usable_rows]
    context = BreadthContext(
        active_count=active_count,
        eligible_count=eligible_count,
        excluded_count=len(exclusions),
        coverage=coverage,
        exchange_coverage=exchange_coverage,
        exchange_metadata_coverage=exchange_metadata_coverage,
        liquidity_candidate_count=liquidity_candidate_count,
        liquidity_coverage=liquidity_coverage,
        pct_above_ma20=sum(close > ma20 for close, ma20, _, _, _ in usable_rows)
        / eligible_count,
        pct_above_ma50=sum(close > ma50 for close, _, ma50, _, _ in usable_rows)
        / eligible_count,
        pct_positive_return20=sum(value > 0 for value in returns) / eligible_count,
        advancers=sum(value > 0 for value in returns),
        decliners=sum(value < 0 for value in returns),
        unchanged=sum(value == 0 for value in returns),
        near_52w_high_count=sum(
            distance is not None and distance >= -0.005 for *_, distance in usable_rows
        ),
        median_return20=median(returns),
        return20_dispersion=pstdev(returns) if len(returns) > 1 else 0.0,
        excluded_symbols=tuple(exclusions),
        security_type_excluded_symbols=tuple(security_type_excluded_symbols),
        exclusion_counts=dict(exclusion_counts),
        membership_basis=membership_basis,
        membership_resolver_version=membership_resolver_version,
    )
    if context.available_for(policy):
        return context
    return BreadthContext(
        active_count=context.active_count,
        eligible_count=context.eligible_count,
        excluded_count=context.excluded_count,
        coverage=context.coverage,
        exchange_coverage=context.exchange_coverage,
        exchange_metadata_coverage=context.exchange_metadata_coverage,
        liquidity_candidate_count=context.liquidity_candidate_count,
        liquidity_coverage=context.liquidity_coverage,
        pct_above_ma20=None,
        pct_above_ma50=None,
        pct_positive_return20=None,
        advancers=None,
        decliners=None,
        unchanged=None,
        near_52w_high_count=None,
        median_return20=None,
        return20_dispersion=None,
        excluded_symbols=context.excluded_symbols,
        security_type_excluded_symbols=context.security_type_excluded_symbols,
        exclusion_counts=context.exclusion_counts,
        membership_basis=context.membership_basis,
        membership_resolver_version=context.membership_resolver_version,
    )
