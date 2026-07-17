from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import duckdb

from vnalpha.warehouse.point_in_time import resolve_universe

ContextValue = str | int | list[str]


@dataclass(frozen=True, slots=True)
class SymbolIdentitySnapshot:
    symbol: str
    exchange: str
    security_type: str
    classification_source: str | None
    source_snapshot_id: str | None
    effective_from: str | None


@dataclass(frozen=True, slots=True)
class CanonicalOhlcvBasisSnapshot:
    symbol: str
    requested_as_of_date: str
    resolved_as_of_date: str
    first_bar_date: str
    last_bar_date: str
    usable_row_count: int
    providers: tuple[str, ...]
    ingestion_run_ids: tuple[str, ...]
    price_basis: str
    quality_status: str
    corporate_action_overlap: bool


def load_symbol_identity(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    as_of_date: date,
) -> SymbolIdentitySnapshot | None:
    universe = resolve_universe(conn, as_of_date)
    classification = universe.get(symbol)
    if universe.is_ambiguous(symbol):
        return None
    if classification is not None:
        source = conn.execute(
            "SELECT classification_source "
            "FROM symbol_classification_history "
            "WHERE symbol = ? AND source_snapshot_id = ? AND effective_from = ? "
            "LIMIT 1",
            [symbol, classification.source_snapshot_id, classification.effective_from],
        ).fetchone()
        if not classification.exchange or not classification.security_type:
            return None
        return SymbolIdentitySnapshot(
            symbol=symbol,
            exchange=classification.exchange,
            security_type=classification.security_type,
            classification_source=(
                None if source is None or source[0] is None else str(source[0])
            ),
            source_snapshot_id=classification.source_snapshot_id,
            effective_from=_iso_temporal(classification.effective_from),
        )

    history_exists = conn.execute(
        "SELECT 1 FROM symbol_classification_history WHERE symbol = ? LIMIT 1",
        [symbol],
    ).fetchone()
    if history_exists is not None:
        return None
    row = conn.execute(
        "SELECT exchange, security_type, classification_source, "
        "last_seen_source_snapshot_id, classification_effective_from "
        "FROM symbol_master WHERE symbol = ? AND is_active = TRUE "
        "AND (classification_effective_from IS NULL "
        "OR CAST(classification_effective_from AS DATE) <= ?) "
        "AND (listing_date IS NULL OR listing_date <= ?) "
        "AND (delisting_date IS NULL OR delisting_date > ?)",
        [symbol, as_of_date, as_of_date, as_of_date],
    ).fetchone()
    if row is None or not row[0] or not row[1]:
        return None
    return SymbolIdentitySnapshot(
        symbol=symbol,
        exchange=str(row[0]),
        security_type=str(row[1]),
        classification_source=None if row[2] is None else str(row[2]),
        source_snapshot_id=None if row[3] is None else str(row[3]),
        effective_from=_iso_temporal(row[4]),
    )


def load_canonical_ohlcv_basis(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    requested_as_of_date: str,
    resolved_as_of_date: date,
) -> CanonicalOhlcvBasisSnapshot | None:
    feature_row = conn.execute(
        "SELECT COALESCE(observed_bar_count, source_row_count, required_bar_count) "
        "FROM feature_snapshot WHERE symbol = ? AND date = ?",
        [symbol, resolved_as_of_date],
    ).fetchone()
    requested_count = (
        int(feature_row[0])
        if feature_row is not None and feature_row[0] is not None
        else None
    )
    if requested_count is None or requested_count <= 0:
        count_row = conn.execute(
            "SELECT COUNT(*) FROM canonical_ohlcv "
            "WHERE symbol = ? AND interval = '1D' AND CAST(time AS DATE) <= ?",
            [symbol, resolved_as_of_date],
        ).fetchone()
        requested_count = 0 if count_row is None else int(count_row[0])
    if requested_count <= 0:
        return None
    rows = conn.execute(
        "SELECT CAST(time AS DATE), selected_provider, ingestion_run_id, "
        "quality_status, price_basis FROM canonical_ohlcv "
        "WHERE symbol = ? AND interval = '1D' AND CAST(time AS DATE) <= ? "
        "ORDER BY time DESC LIMIT ?",
        [symbol, resolved_as_of_date, requested_count],
    ).fetchall()
    if not rows:
        return None
    first_bar_date = min(row[0] for row in rows)
    last_bar_date = max(row[0] for row in rows)
    providers = tuple(sorted({str(row[1]) for row in rows if row[1]}))
    ingestion_run_ids = tuple(sorted({str(row[2]) for row in rows if row[2]}))
    quality_values = tuple(sorted({str(row[3]) for row in rows if row[3]}))
    price_bases = {None if row[4] is None else str(row[4]) for row in rows}
    if price_bases != {"RAW_UNADJUSTED"}:
        return None
    quality_status = (
        quality_values[0]
        if len(quality_values) == 1
        else "mixed:" + ",".join(quality_values)
        if quality_values
        else "unknown"
    )
    overlap = conn.execute(
        "SELECT 1 FROM corporate_action_affected_range "
        "WHERE symbol = ? AND affected_from_date <= ? "
        "AND (affected_to_date IS NULL OR affected_to_date >= ?) LIMIT 1",
        [symbol, last_bar_date, first_bar_date],
    ).fetchone()
    return CanonicalOhlcvBasisSnapshot(
        symbol=symbol,
        requested_as_of_date=requested_as_of_date,
        resolved_as_of_date=resolved_as_of_date.isoformat(),
        first_bar_date=first_bar_date.isoformat(),
        last_bar_date=last_bar_date.isoformat(),
        usable_row_count=len(rows),
        providers=providers,
        ingestion_run_ids=ingestion_run_ids,
        price_basis="RAW_UNADJUSTED",
        quality_status=quality_status,
        corporate_action_overlap=overlap is not None,
    )


def symbol_identity_value(snapshot: SymbolIdentitySnapshot) -> dict[str, ContextValue]:
    value: dict[str, ContextValue] = {
        "symbol": snapshot.symbol,
        "exchange": snapshot.exchange,
        "security_type": snapshot.security_type,
    }
    if snapshot.classification_source:
        value["classification_source"] = snapshot.classification_source
    if snapshot.source_snapshot_id:
        value["source_snapshot_id"] = snapshot.source_snapshot_id
    if snapshot.effective_from:
        value["effective_from"] = snapshot.effective_from
    if not snapshot.classification_source or not snapshot.source_snapshot_id:
        value["source_caveat"] = "Optional identity source metadata is missing."
    return value


def canonical_ohlcv_basis_value(
    snapshot: CanonicalOhlcvBasisSnapshot,
) -> dict[str, ContextValue]:
    value: dict[str, ContextValue] = {
        "requested_as_of_date": snapshot.requested_as_of_date,
        "resolved_as_of_date": snapshot.resolved_as_of_date,
        "first_bar_date": snapshot.first_bar_date,
        "last_bar_date": snapshot.last_bar_date,
        "value": snapshot.usable_row_count,
        "unit": "bars",
        "meaning": "accepted canonical OHLCV rows used by analysis",
        "providers": list(snapshot.providers),
        "ingestion_run_ids": list(snapshot.ingestion_run_ids),
        "quality_status": snapshot.quality_status,
        "price_basis": snapshot.price_basis,
    }
    if not snapshot.providers or not snapshot.ingestion_run_ids:
        value["lineage_caveat"] = (
            "Optional provider or ingestion-run lineage is missing."
        )
    if snapshot.corporate_action_overlap:
        value["corporate_action_caveat"] = (
            "Known corporate-action evidence overlaps this raw-unadjusted OHLCV window."
        )
    return value


def _iso_temporal(value: object) -> str | None:
    if isinstance(value, date | datetime):
        return value.isoformat()
    return None if value is None else str(value)


__all__ = [
    "CanonicalOhlcvBasisSnapshot",
    "SymbolIdentitySnapshot",
    "canonical_ohlcv_basis_value",
    "load_canonical_ohlcv_basis",
    "load_symbol_identity",
    "symbol_identity_value",
]
