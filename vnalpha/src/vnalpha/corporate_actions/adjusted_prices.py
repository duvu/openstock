from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from vnalpha.corporate_actions.adjustment_factors import (
    AdjustmentFactor,
    AdjustmentType,
)

if TYPE_CHECKING:
    import duckdb

ADJUSTED_PRICE_BASIS = "BACKWARD_ADJUSTED"
ADJUSTED_PRICE_VERSION = "backward-adjusted-v1"


class UnsupportedAdjustmentAction(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AdjustedPriceBuildResult:
    symbol: str
    rows_written: int
    factors_used: int
    from_date: str | None
    to_date: str | None
    adjustment_version: str = ADJUSTED_PRICE_VERSION


def derive_factor_for_revision(
    conn: duckdb.DuckDBPyConnection,
    revision_id: str,
) -> AdjustmentFactor:
    row = conn.execute(
        """
        SELECT symbol, action_type, COALESCE(ex_date, effective_date, record_date),
               cash_amount, ratio, subscription_price, reference_price
        FROM corporate_action
        WHERE revision_id = ? AND canonical_status = 'CURRENT'
        """,
        [revision_id],
    ).fetchone()
    if row is None:
        raise ValueError(f"No current corporate-action revision {revision_id!r}")

    symbol, raw_type, effective_date, cash_amount, ratio, subscription, reference = row
    if effective_date is None:
        raise ValueError(f"Corporate action {revision_id!r} has no effective/ex date")
    action_type = str(raw_type).upper()
    ratio_value = Decimal(str(ratio)) if ratio is not None else None

    if action_type == "SPLIT":
        if ratio_value is None or ratio_value <= 0:
            raise ValueError("Split requires a positive new/old share ratio")
        adjustment_type = AdjustmentType.SPLIT
        price_multiplier = Decimal(1) / ratio_value
    elif action_type == "CONSOLIDATION":
        if ratio_value is None or ratio_value <= 0:
            raise ValueError("Consolidation requires a positive new/old share ratio")
        adjustment_type = AdjustmentType.REVERSE_SPLIT
        price_multiplier = Decimal(1) / ratio_value
    elif action_type in {"STOCK_DIVIDEND", "STOCK_BONUS"}:
        if ratio_value is None or ratio_value <= 0:
            raise ValueError("Stock distribution requires a positive new/old ratio")
        adjustment_type = (
            AdjustmentType.STOCK_DIVIDEND
            if action_type == "STOCK_DIVIDEND"
            else AdjustmentType.BONUS_SHARES
        )
        price_multiplier = Decimal(1) / (Decimal(1) + ratio_value)
    elif action_type == "CASH_DIVIDEND":
        if cash_amount is None or reference is None:
            raise ValueError("Cash dividend requires cash_amount and reference_price")
        reference_value = Decimal(str(reference))
        cash_value = Decimal(str(cash_amount))
        if reference_value <= 0 or cash_value < 0 or cash_value >= reference_value:
            raise ValueError("Invalid cash-dividend reference values")
        adjustment_type = AdjustmentType.CASH_DIVIDEND
        price_multiplier = (reference_value - cash_value) / reference_value
    elif action_type == "RIGHTS_ISSUE":
        if ratio_value is None or ratio_value <= 0:
            raise ValueError("Rights issue requires a positive new/old ratio")
        if subscription is None or reference is None:
            raise ValueError("Rights issue requires subscription and reference prices")
        subscription_value = Decimal(str(subscription))
        reference_value = Decimal(str(reference))
        if subscription_value <= 0 or reference_value <= 0:
            raise ValueError("Rights-issue prices must be positive")
        adjustment_type = AdjustmentType.RIGHTS_ISSUE
        theoretical_ex_price = (reference_value + ratio_value * subscription_value) / (
            Decimal(1) + ratio_value
        )
        price_multiplier = theoretical_ex_price / reference_value
    else:
        raise UnsupportedAdjustmentAction(
            f"Corporate action type {action_type!r} has no verified adjustment method"
        )

    volume_multiplier = (
        Decimal(1)
        if adjustment_type is AdjustmentType.CASH_DIVIDEND
        else Decimal(1) / price_multiplier
    )
    return AdjustmentFactor(
        symbol=str(symbol).upper(),
        action_date=effective_date,
        adjustment_type=adjustment_type,
        price_multiplier=price_multiplier,
        volume_multiplier=volume_multiplier,
    )


def persist_adjustment_factor(
    conn: duckdb.DuckDBPyConnection,
    *,
    action_id: str,
    action_revision_id: str,
    factor: AdjustmentFactor,
) -> str:
    """Persist a factor immutably and supersede the prior action factor."""
    content_hash = factor.content_hash()
    existing = conn.execute(
        """
        SELECT factor_id, content_hash
        FROM adjustment_factor
        WHERE action_revision_id = ? AND methodology_version = ?
        """,
        [action_revision_id, factor.version],
    ).fetchone()
    if existing is not None:
        if existing[1] != content_hash:
            raise ValueError(
                "An immutable factor revision exists with different content"
            )
        return str(existing[0])

    prior = conn.execute(
        """
        SELECT factor_id FROM adjustment_factor
        WHERE action_id = ? AND canonical_status = 'CURRENT'
        ORDER BY created_at DESC LIMIT 1
        """,
        [action_id],
    ).fetchone()
    factor_id = f"adjf_{content_hash[:20]}"
    conn.execute(
        """
        INSERT INTO adjustment_factor (
            factor_id, symbol, action_id, action_revision_id, action_type,
            effective_date, price_multiplier, volume_multiplier,
            methodology_version, content_hash, canonical_status,
            supersedes_factor_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CURRENT', ?)
        """,
        [
            factor_id,
            factor.symbol,
            action_id,
            action_revision_id,
            factor.adjustment_type.value,
            factor.action_date,
            float(factor.price_multiplier),
            float(factor.volume_multiplier),
            factor.version,
            content_hash,
            prior[0] if prior else None,
        ],
    )
    if prior is not None:
        conn.execute(
            """
            UPDATE adjustment_factor
            SET canonical_status = 'SUPERSEDED', superseded_by_factor_id = ?
            WHERE factor_id = ?
            """,
            [factor_id, prior[0]],
        )
    return factor_id


def derive_and_persist_factor(
    conn: duckdb.DuckDBPyConnection,
    revision_id: str,
) -> str:
    identity = conn.execute(
        "SELECT action_id FROM corporate_action WHERE revision_id = ?",
        [revision_id],
    ).fetchone()
    if identity is None:
        raise ValueError(f"Unknown corporate-action revision {revision_id!r}")
    factor = derive_factor_for_revision(conn, revision_id)
    return persist_adjustment_factor(
        conn,
        action_id=str(identity[0]),
        action_revision_id=revision_id,
        factor=factor,
    )


def build_adjusted_ohlcv(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    adjustment_version: str = ADJUSTED_PRICE_VERSION,
) -> AdjustedPriceBuildResult:
    """Rebuild a bounded backward-adjusted series from raw canonical bars."""
    symbol = symbol.strip().upper()
    factors = conn.execute(
        """
        SELECT factor_id, effective_date, price_multiplier, volume_multiplier,
               content_hash
        FROM adjustment_factor
        WHERE symbol = ? AND canonical_status = 'CURRENT'
        ORDER BY effective_date, factor_id
        """,
        [symbol],
    ).fetchall()

    conditions = ["symbol = ?", "interval = '1D'", "price_basis = 'RAW_UNADJUSTED'"]
    params: list[object] = [symbol]
    if from_date is not None:
        conditions.append("CAST(time AS DATE) >= ?")
        params.append(from_date)
    if to_date is not None:
        conditions.append("CAST(time AS DATE) <= ?")
        params.append(to_date)
    bars = conn.execute(
        f"""
        SELECT time, open, high, low, close, volume,
               ingestion_run_id, selected_provider
        FROM canonical_ohlcv
        WHERE {" AND ".join(conditions)}
        ORDER BY time
        """,
        params,
    ).fetchall()

    delete_conditions = [
        "symbol = ?",
        "interval = '1D'",
        "price_basis = ?",
        "adjustment_version = ?",
    ]
    delete_params: list[object] = [
        symbol,
        ADJUSTED_PRICE_BASIS,
        adjustment_version,
    ]
    if from_date is not None:
        delete_conditions.append("CAST(time AS DATE) >= ?")
        delete_params.append(from_date)
    if to_date is not None:
        delete_conditions.append("CAST(time AS DATE) <= ?")
        delete_params.append(to_date)
    conn.execute(
        f"DELETE FROM adjusted_ohlcv WHERE {' AND '.join(delete_conditions)}",
        delete_params,
    )

    rows_written = 0
    for bar in bars:
        bar_date = bar[0].date()
        applicable = [factor for factor in factors if bar_date < factor[1]]
        price_multiplier = Decimal(1)
        volume_multiplier = Decimal(1)
        factor_hashes: list[str] = []
        for factor in applicable:
            price_multiplier *= Decimal(str(factor[2]))
            volume_multiplier *= Decimal(str(factor[3]))
            factor_hashes.append(str(factor[4]))
        chain_hash = hashlib.sha256("|".join(factor_hashes).encode("utf-8")).hexdigest()

        def _price(
            value: object, multiplier: Decimal = price_multiplier
        ) -> float | None:
            return None if value is None else float(Decimal(str(value)) * multiplier)

        adjusted_volume = (
            None if bar[5] is None else float(Decimal(str(bar[5])) * volume_multiplier)
        )
        conn.execute(
            """
            INSERT INTO adjusted_ohlcv (
                symbol, time, interval, open, high, low, close, volume,
                price_basis, adjustment_version, factor_chain_hash,
                source_ingestion_run_id, source_provider
            ) VALUES (?, ?, '1D', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                symbol,
                bar[0],
                _price(bar[1]),
                _price(bar[2]),
                _price(bar[3]),
                _price(bar[4]),
                adjusted_volume,
                ADJUSTED_PRICE_BASIS,
                adjustment_version,
                chain_hash,
                bar[6],
                bar[7],
            ],
        )
        rows_written += 1
    return AdjustedPriceBuildResult(
        symbol=symbol,
        rows_written=rows_written,
        factors_used=len(factors),
        from_date=from_date,
        to_date=to_date,
        adjustment_version=adjustment_version,
    )


def rebuild_pending_adjusted_ranges(
    conn: duckdb.DuckDBPyConnection,
    *,
    limit: int = 100,
) -> list[AdjustedPriceBuildResult]:
    """Resolve bounded affected-range signals after action revisions."""
    signals = conn.execute(
        """
        SELECT signal_id, revision_id, symbol, affected_from_date, affected_to_date
        FROM corporate_action_affected_range
        WHERE resolved_at IS NULL
        ORDER BY created_at
        LIMIT ?
        """,
        [limit],
    ).fetchall()
    results: list[AdjustedPriceBuildResult] = []
    for signal_id, revision_id, symbol, start, end in signals:
        factor_id = derive_and_persist_factor(conn, str(revision_id))
        result = build_adjusted_ohlcv(
            conn,
            str(symbol),
            from_date=str(start) if start is not None else None,
            to_date=str(end) if end is not None else None,
        )
        resolution_ref = f"{factor_id}:{result.adjustment_version}"
        conn.execute(
            """
            UPDATE corporate_action_affected_range
            SET resolved_at = current_timestamp, resolution_ref = ?
            WHERE signal_id = ?
            """,
            [resolution_ref, signal_id],
        )
        results.append(result)
    return results


__all__ = [
    "ADJUSTED_PRICE_BASIS",
    "ADJUSTED_PRICE_VERSION",
    "AdjustedPriceBuildResult",
    "UnsupportedAdjustmentAction",
    "build_adjusted_ohlcv",
    "derive_and_persist_factor",
    "derive_factor_for_revision",
    "persist_adjustment_factor",
    "rebuild_pending_adjusted_ranges",
]
