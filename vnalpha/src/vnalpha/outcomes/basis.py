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
    adjustment_version: str
    action_overlap_status: ActionOverlapStatus
    invalidation_reason: str | None
    overlapping_action_types: tuple[str, ...]
    corporate_action_lineage: tuple[str, ...]


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
        """
        SELECT action_type, action_id, revision_id, canonical_status
        FROM corporate_action
        WHERE symbol=? AND canonical_status <> 'SUPERSEDED'
          AND COALESCE(ex_date, effective_date, record_date, affected_from_date)
              BETWEEN ? AND ?
        UNION
        SELECT COALESCE(ca.action_type, 'AFFECTED_RANGE'), ar.action_id,
               ar.revision_id, COALESCE(ca.canonical_status, 'AFFECTED_RANGE')
        FROM corporate_action_affected_range ar
        LEFT JOIN corporate_action ca ON ca.revision_id = ar.revision_id
        WHERE ar.symbol=?
          AND ar.affected_from_date <= ?
          AND COALESCE(ar.affected_to_date, ar.affected_from_date) >= ?
        ORDER BY action_type, action_id, revision_id
        """,
        [symbol, start_date, end_date, symbol, end_date, start_date],
    ).fetchall()
    action_types = tuple(sorted({str(row[0]) for row in actions}))
    action_lineage = tuple(sorted(f"{row[1]}:{row[2]}:{row[3]}" for row in actions))
    if action_types:
        return ObservationLineage(
            price_basis=price_basis,
            adjustment_methodology="NONE",
            adjustment_version="raw-unadjusted-v1",
            action_overlap_status=ActionOverlapStatus.INVALID,
            invalidation_reason="RAW_SERIES_CORPORATE_ACTION_OVERLAP",
            overlapping_action_types=action_types,
            corporate_action_lineage=action_lineage,
        )
    return ObservationLineage(
        price_basis=price_basis,
        adjustment_methodology="NONE",
        adjustment_version="raw-unadjusted-v1",
        action_overlap_status=ActionOverlapStatus.CLEAR,
        invalidation_reason=None,
        overlapping_action_types=(),
        corporate_action_lineage=(),
    )


__all__ = [
    "ActionOverlapStatus",
    "BasisValidationError",
    "ObservationLineage",
    "assess_observation_lineage",
]
