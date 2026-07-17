from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import duckdb


class BasisValidationError(ValueError):
    pass


class ActionOverlapStatus(str, Enum):
    CLEAR = "CLEAR"
    INVALID = "INVALID"


@dataclass(frozen=True, slots=True)
class ObservationLineage:
    price_basis: str
    adjustment_methodology: str
    action_overlap_status: ActionOverlapStatus
    invalidation_reason: str | None
    overlapping_action_types: tuple[str, ...]


def assess_observation_lineage(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    start_date: str,
    end_date: str,
) -> ObservationLineage:
    rows = conn.execute(
        "SELECT DISTINCT price_basis FROM canonical_ohlcv "
        "WHERE symbol=? AND interval='1D' AND CAST(time AS DATE) BETWEEN ? AND ?",
        [symbol, start_date, end_date],
    ).fetchall()
    bases = {row[0] for row in rows}
    if not bases or None in bases or "" in bases:
        raise BasisValidationError(f"unknown price basis for {symbol}")
    if len(bases) != 1:
        raise BasisValidationError(f"mixed price basis for {symbol}: {sorted(bases)}")
    price_basis = str(next(iter(bases))).upper()
    if price_basis != "RAW_UNADJUSTED":
        raise BasisValidationError(f"unknown price basis for {symbol}: {price_basis}")

    actions = conn.execute(
        "SELECT DISTINCT action_type FROM corporate_action "
        "WHERE symbol=? AND canonical_status NOT IN ('SUPERSEDED', 'CONFLICT') "
        "AND COALESCE(ex_date, effective_date, record_date, affected_from_date) "
        "BETWEEN ? AND ? ORDER BY action_type",
        [symbol, start_date, end_date],
    ).fetchall()
    action_types = tuple(str(row[0]) for row in actions)
    if action_types:
        return ObservationLineage(
            price_basis=price_basis,
            adjustment_methodology="NONE",
            action_overlap_status=ActionOverlapStatus.INVALID,
            invalidation_reason="RAW_SERIES_CORPORATE_ACTION_OVERLAP",
            overlapping_action_types=action_types,
        )
    return ObservationLineage(
        price_basis=price_basis,
        adjustment_methodology="NONE",
        action_overlap_status=ActionOverlapStatus.CLEAR,
        invalidation_reason=None,
        overlapping_action_types=(),
    )


__all__ = [
    "ActionOverlapStatus",
    "BasisValidationError",
    "ObservationLineage",
    "assess_observation_lineage",
]
