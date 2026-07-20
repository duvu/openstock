"""Valuation snapshot builder + reader (issue #258)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

from vnalpha.fundamentals import StatementScope, as_of_snapshot
from vnalpha.valuation.metrics import (
    ValuationInputs,
    book_value_per_share,
    compute_valuation_metrics,
    percentile_rank,
)

if TYPE_CHECKING:
    import duckdb

VALUATION_CONTRACT_VERSION = "valuation-v1"
_RAW_BASIS = "RAW_UNADJUSTED"


@dataclass(frozen=True, slots=True)
class ValuationSnapshot:
    snapshot_id: str
    symbol: str
    as_of_date: str
    price: float | None
    eps: float | None
    book_value_per_share: float | None
    pe_ratio: float | None
    earnings_yield: float | None
    pb_ratio: float | None
    book_yield: float | None
    historical_pe_percentile: float | None
    sector_pe_percentile: float | None
    caveats: tuple[str, ...]
    lineage: dict[str, object]


def _latest_close_on_or_before(
    conn: duckdb.DuckDBPyConnection, symbol: str, as_of_date: str
) -> tuple[float, str] | None:
    row = conn.execute(
        """
        SELECT close, CAST(time AS DATE)
        FROM canonical_ohlcv
        WHERE symbol = ? AND interval = '1D' AND price_basis = ?
          AND CAST(time AS DATE) <= ?
        ORDER BY time DESC LIMIT 1
        """,
        [symbol, _RAW_BASIS, as_of_date],
    ).fetchone()
    if row is None or row[0] is None:
        return None
    return float(row[0]), str(row[1])


def _sector_code(
    conn: duckdb.DuckDBPyConnection, symbol: str
) -> tuple[str | None, str | None]:
    row = conn.execute(
        "SELECT sector_code, taxonomy_version FROM symbol_master WHERE symbol = ?",
        [symbol],
    ).fetchone()
    if row is None:
        return None, None
    return row[0], row[1]


def _latest_fundamental(conn: duckdb.DuckDBPyConnection, symbol: str, as_of_date: str):
    facts = as_of_snapshot(
        conn, symbol, as_of_date, statement_scope=StatementScope.CONSOLIDATED
    )
    return facts[0] if facts else None


def build_valuation_snapshot(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    as_of_date: str,
    *,
    shares_outstanding: float | None = None,
    persist: bool = True,
) -> ValuationSnapshot:
    """Build (and optionally persist) a reproducible valuation snapshot.

    Uses only price bars and fundamentals available on or before ``as_of_date``
    (no future-publication or future-price leakage) and the symbol's current
    point-in-time sector for sector-relative ranking. Idempotent: rebuilding the
    same (symbol, as_of_date) replaces the snapshot deterministically.
    """
    symbol = symbol.upper()
    caveats: list[str] = []

    price_row = _latest_close_on_or_before(conn, symbol, as_of_date)
    if price_row is None:
        price, price_date = None, None
        caveats.append("no_price_on_or_before_as_of")
    else:
        price, price_date = price_row

    fact = _latest_fundamental(conn, symbol, as_of_date)
    if fact is None:
        eps = None
        equity = None
        fundamental_period = None
        fundamental_published_at = None
        caveats.append("no_fundamental_on_or_before_as_of")
    else:
        eps = fact.eps
        equity = fact.total_equity
        fundamental_period = (
            f"{fact.fiscal_year}:{fact.fiscal_period}:{fact.statement_scope}"
        )
        fundamental_published_at = fact.published_at
        for c in fact.caveats:
            caveats.append(f"fundamental:{c}")

    bvps = book_value_per_share(equity, shares_outstanding)
    if shares_outstanding is None:
        caveats.append("shares_outstanding_not_provided")

    metrics = compute_valuation_metrics(
        ValuationInputs(price=price, eps=eps, book_value_per_share=bvps)
    )

    sector_code, taxonomy_version = _sector_code(conn, symbol)

    historical_pe_pct = _historical_pe_percentile(
        conn, symbol, as_of_date, metrics.pe_ratio
    )
    sector_pe_pct = _sector_pe_percentile(
        conn, sector_code, as_of_date, symbol, metrics.pe_ratio
    )

    lineage = {
        "price_basis": _RAW_BASIS,
        "price_date": price_date,
        "fundamental_period": fundamental_period,
        "fundamental_published_at": fundamental_published_at,
        "shares_outstanding": shares_outstanding,
        "sector_code": sector_code,
        "taxonomy_version": taxonomy_version,
    }

    snapshot_id = f"val_{uuid4().hex[:16]}"
    snapshot = ValuationSnapshot(
        snapshot_id=snapshot_id,
        symbol=symbol,
        as_of_date=as_of_date,
        price=price,
        eps=eps,
        book_value_per_share=bvps,
        pe_ratio=metrics.pe_ratio,
        earnings_yield=metrics.earnings_yield,
        pb_ratio=metrics.pb_ratio,
        book_yield=metrics.book_yield,
        historical_pe_percentile=historical_pe_pct,
        sector_pe_percentile=sector_pe_pct,
        caveats=tuple(caveats),
        lineage=lineage,
    )

    if persist:
        _persist(conn, snapshot)
    return snapshot


def _historical_pe_percentile(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    as_of_date: str,
    current_pe: float | None,
) -> float | None:
    if current_pe is None:
        return None
    rows = conn.execute(
        """
        SELECT pe_ratio FROM valuation_snapshot
        WHERE symbol = ? AND as_of_date < ? AND pe_ratio IS NOT NULL
        """,
        [symbol, as_of_date],
    ).fetchall()
    population = [float(r[0]) for r in rows]
    return percentile_rank(current_pe, population)


def _sector_pe_percentile(
    conn: duckdb.DuckDBPyConnection,
    sector_code: str | None,
    as_of_date: str,
    symbol: str,
    current_pe: float | None,
) -> float | None:
    if current_pe is None or sector_code is None:
        return None
    # Point-in-time sector peers: the latest snapshot on or before as_of_date
    # for each other symbol currently classified in this sector.
    rows = conn.execute(
        """
        WITH peers AS (
            SELECT v.symbol, v.pe_ratio,
                   ROW_NUMBER() OVER (
                       PARTITION BY v.symbol ORDER BY v.as_of_date DESC
                   ) AS rn
            FROM valuation_snapshot v
            JOIN symbol_master m ON m.symbol = v.symbol
            WHERE m.sector_code = ? AND v.as_of_date <= ?
              AND v.symbol <> ? AND v.pe_ratio IS NOT NULL
        )
        SELECT pe_ratio FROM peers WHERE rn = 1
        """,
        [sector_code, as_of_date, symbol],
    ).fetchall()
    population = [float(r[0]) for r in rows]
    return percentile_rank(current_pe, population)


def _persist(conn: duckdb.DuckDBPyConnection, s: ValuationSnapshot) -> None:
    # Idempotent rebuild: remove any prior snapshot for this key first.
    conn.execute(
        "DELETE FROM valuation_snapshot WHERE symbol = ? AND as_of_date = ? AND price_basis = ?",
        [s.symbol, s.as_of_date, _RAW_BASIS],
    )
    conn.execute(
        """
        INSERT INTO valuation_snapshot (
            snapshot_id, symbol, as_of_date, price, price_basis, price_date,
            eps, book_value_per_share, shares_outstanding, fundamental_period,
            fundamental_published_at, sector_code, taxonomy_version,
            pe_ratio, earnings_yield, pb_ratio, book_yield,
            historical_pe_percentile, sector_pe_percentile,
            caveats_json, lineage_json, contract_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            s.snapshot_id,
            s.symbol,
            s.as_of_date,
            s.price,
            _RAW_BASIS,
            s.lineage.get("price_date"),
            s.eps,
            s.book_value_per_share,
            s.lineage.get("shares_outstanding"),
            s.lineage.get("fundamental_period"),
            s.lineage.get("fundamental_published_at"),
            s.lineage.get("sector_code"),
            s.lineage.get("taxonomy_version"),
            s.pe_ratio,
            s.earnings_yield,
            s.pb_ratio,
            s.book_yield,
            s.historical_pe_percentile,
            s.sector_pe_percentile,
            json.dumps(list(s.caveats)),
            json.dumps(s.lineage, sort_keys=True),
            VALUATION_CONTRACT_VERSION,
        ],
    )
    conn.commit()


def get_valuation_snapshot(
    conn: duckdb.DuckDBPyConnection, symbol: str, as_of_date: str
) -> ValuationSnapshot | None:
    row = conn.execute(
        """
        SELECT snapshot_id, symbol, as_of_date, price, eps, book_value_per_share,
               pe_ratio, earnings_yield, pb_ratio, book_yield,
               historical_pe_percentile, sector_pe_percentile,
               caveats_json, lineage_json
        FROM valuation_snapshot
        WHERE symbol = ? AND as_of_date = ? AND price_basis = ?
        """,
        [symbol.upper(), as_of_date, _RAW_BASIS],
    ).fetchone()
    if row is None:
        return None
    return ValuationSnapshot(
        snapshot_id=row[0],
        symbol=row[1],
        as_of_date=str(row[2]),
        price=row[3],
        eps=row[4],
        book_value_per_share=row[5],
        pe_ratio=row[6],
        earnings_yield=row[7],
        pb_ratio=row[8],
        book_yield=row[9],
        historical_pe_percentile=row[10],
        sector_pe_percentile=row[11],
        caveats=tuple(json.loads(row[12])) if row[12] else (),
        lineage=json.loads(row[13]) if row[13] else {},
    )


__all__ = [
    "ValuationSnapshot",
    "build_valuation_snapshot",
    "get_valuation_snapshot",
]
