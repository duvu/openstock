"""Read-only tools exposing persisted market and sector research context."""

from __future__ import annotations

from typing import Any

import duckdb

from vnalpha.commands.errors import CommandValidationError
from vnalpha.commands.normalizers import normalize_date, normalize_symbol
from vnalpha.research_intelligence.models import SymbolSectorAlignment
from vnalpha.tools.errors import ToolExecutionError
from vnalpha.tools.models import ToolOutput
from vnalpha.tools.research_context_serialization import (
    market_payload,
    missing_payload,
    sector_collection_payload,
    sector_snapshot_data,
)
from vnalpha.warehouse.repositories import (
    get_latest_market_regime,
    get_latest_sector_strength,
    get_market_regime_as_of,
    get_sector_strength_as_of,
    get_symbol_sector_alignment,
)


def get_market_regime(
    conn: duckdb.DuckDBPyConnection, date: str | None = None
) -> ToolOutput:
    """Return one exact or latest persisted market-regime snapshot."""
    requested_date = _normalize_date(date)
    snapshot = (
        get_latest_market_regime(conn)
        if requested_date is None
        else get_market_regime_as_of(conn, requested_date)
    )
    lookup = "latest" if requested_date is None else "exact"
    if snapshot is None:
        caveat = _missing_caveat("market regime snapshot", requested_date)
        return ToolOutput(
            data=missing_payload(requested_date, lookup, caveat),
            summary="No persisted market regime research context is available.",
            warnings=[caveat],
        )
    payload = market_payload(snapshot, requested_date, lookup)
    return ToolOutput(
        data=payload,
        summary="Persisted market regime research context; no live calculation was performed.",
        warnings=list(snapshot.caveats),
    )


def get_sector_strength(
    conn: duckdb.DuckDBPyConnection,
    date: str | None = None,
    top: int | None = None,
) -> ToolOutput:
    """Return exact or latest persisted sector-strength snapshots in repository order."""
    requested_date = _normalize_date(date)
    limit = _normalize_top(top)
    snapshots = (
        get_latest_sector_strength(conn, limit=limit)
        if requested_date is None
        else get_sector_strength_as_of(conn, requested_date, limit=limit)
    )
    lookup = "latest" if requested_date is None else "exact"
    if not snapshots:
        caveat = _missing_caveat("sector strength snapshot", requested_date)
        payload = missing_payload(requested_date, lookup, caveat)
        payload["snapshots"] = []
        return ToolOutput(
            data=payload,
            summary="No persisted sector strength research context is available.",
            warnings=[caveat],
        )
    payload = sector_collection_payload(snapshots, requested_date, lookup)
    return ToolOutput(
        data=payload,
        summary="Persisted sector strength research context; no live calculation was performed.",
        warnings=list(payload["caveats"]),
    )


def get_symbol_alignment(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    date: str | None = None,
) -> ToolOutput:
    """Return persisted symbol-sector alignment without inferring absent metadata."""
    normalized_symbol = normalize_symbol(symbol)
    if not normalized_symbol:
        raise ToolExecutionError(
            "sector.get_symbol_alignment requires a nonblank symbol."
        )
    requested_date = _normalize_date(date)
    alignment = get_symbol_sector_alignment(conn, normalized_symbol, requested_date)
    lookup = "latest" if requested_date is None else "exact"
    if alignment is None:
        caveat = "No persisted symbol metadata is available; no sector was inferred."
        return ToolOutput(
            data=_alignment_missing_payload(
                normalized_symbol, requested_date, lookup, None, caveat
            ),
            summary="No persisted symbol-sector research context is available.",
            warnings=[caveat],
        )
    return _alignment_output(alignment, requested_date, lookup)


def _normalize_date(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return normalize_date(value)
    except CommandValidationError as exc:
        raise ToolExecutionError(str(exc)) from exc


def _normalize_top(value: int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ToolExecutionError("top must be a positive integer.")
    if isinstance(value, int):
        top = value
    elif isinstance(value, str) and value.isdecimal():
        top = int(value)
    else:
        raise ToolExecutionError("top must be a positive integer.")
    if top <= 0:
        raise ToolExecutionError("top must be a positive integer.")
    return top


def _alignment_output(
    alignment: SymbolSectorAlignment, requested_date: str | None, lookup: str
) -> ToolOutput:
    if alignment.sector is None:
        caveat = "Persisted research context has no sector metadata for this symbol."
        return ToolOutput(
            data=_alignment_missing_payload(
                alignment.symbol, requested_date, lookup, None, caveat
            ),
            summary="Persisted symbol-sector metadata is incomplete.",
            warnings=[caveat],
        )
    if alignment.snapshot is None:
        caveat = "No sector snapshot is available for the persisted source sector."
        return ToolOutput(
            data=_alignment_missing_payload(
                alignment.symbol, requested_date, lookup, alignment.sector, caveat
            ),
            summary="No persisted sector snapshot matches this symbol's source sector.",
            warnings=[caveat],
        )
    payload = _market_alignment_payload(alignment, requested_date, lookup)
    return ToolOutput(
        data=payload,
        summary="Persisted symbol-sector research context; no live calculation was performed.",
        warnings=list(alignment.snapshot.caveats),
    )


def _market_alignment_payload(
    alignment: SymbolSectorAlignment, requested_date: str | None, lookup: str
) -> dict[str, Any]:
    snapshot = alignment.snapshot
    if snapshot is None:
        raise ToolExecutionError(
            "A sector snapshot is required for an alignment payload."
        )
    return {
        "symbol": alignment.symbol,
        "sector": alignment.sector,
        "requested_date": requested_date,
        "lookup": lookup,
        "snapshot": sector_snapshot_data(snapshot),
        "as_of_date": snapshot.as_of_date.isoformat(),
        "methodology_version": snapshot.methodology_version,
        "freshness": {"generated_at": snapshot.generated_at.isoformat()},
        "lineage": dict(snapshot.lineage),
        "quality": snapshot.quality,
        "caveats": list(snapshot.caveats),
    }


def _alignment_missing_payload(
    symbol: str,
    requested_date: str | None,
    lookup: str,
    sector: str | None,
    caveat: str,
) -> dict[str, Any]:
    payload = missing_payload(requested_date, lookup, caveat)
    payload["symbol"] = symbol
    payload["sector"] = sector
    return payload


def _missing_caveat(kind: str, requested_date: str | None) -> str:
    date_context = f" for {requested_date}" if requested_date else ""
    return f"No persisted {kind} is available{date_context}; no live calculation was performed."
