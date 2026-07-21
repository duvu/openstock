"""Point-in-time, revisioned valuation snapshot builder and reader."""

from __future__ import annotations

import hashlib
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
from vnalpha.valuation.share_counts import resolve_share_count
from vnalpha.warehouse.point_in_time import (
    RESOLVER_VERSION,
    resolve_symbol_classification,
)

if TYPE_CHECKING:
    import duckdb

VALUATION_CONTRACT_VERSION = "valuation-v2-pit-revisioned"
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
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    as_of_date: str,
) -> tuple[float, str, str | None, str | None] | None:
    row = conn.execute(
        """
        SELECT close, CAST(time AS DATE), ingestion_run_id, selected_provider
        FROM canonical_ohlcv
        WHERE symbol = ? AND interval = '1D' AND price_basis = ?
          AND CAST(time AS DATE) <= ?
        ORDER BY time DESC LIMIT 1
        """,
        [symbol, _RAW_BASIS, as_of_date],
    ).fetchone()
    if row is None or row[0] is None:
        return None
    return float(row[0]), str(row[1]), row[2], row[3]


def _latest_fundamental(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    as_of_date: str,
):
    facts = as_of_snapshot(
        conn,
        symbol,
        as_of_date,
        statement_scope=StatementScope.CONSOLIDATED,
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
    """Build valuation only from evidence visible by ``as_of_date``.

    A verified ``share_count_fact`` is preferred. ``shares_outstanding`` remains
    as a compatibility escape hatch but is marked unverified in lineage/caveats.
    Sector identity and peers are resolved through historical classification.
    """
    symbol = symbol.strip().upper()
    caveats: list[str] = []

    price_row = _latest_close_on_or_before(conn, symbol, as_of_date)
    if price_row is None:
        price = None
        price_date = None
        price_run_id = None
        price_provider = None
        caveats.append("no_price_on_or_before_as_of")
    else:
        price, price_date, price_run_id, price_provider = price_row

    fact = _latest_fundamental(conn, symbol, as_of_date)
    if fact is None:
        eps = None
        equity = None
        fundamental_period = None
        fundamental_revision_id = None
        fundamental_available_from = None
        fundamental_content_hash = None
        caveats.append("no_fundamental_available_by_as_of")
    else:
        eps = fact.eps
        equity = fact.total_equity
        fundamental_period = (
            f"{fact.fiscal_year}:{fact.fiscal_period}:{fact.statement_scope}"
        )
        fundamental_revision_id = fact.revision_id
        fundamental_available_from = fact.available_from
        fundamental_content_hash = fact.content_hash
        caveats.extend(f"fundamental:{item}" for item in fact.caveats)

    share_fact = resolve_share_count(conn, symbol, as_of_date)
    if share_fact is not None:
        resolved_shares = share_fact.shares_outstanding
        share_revision_id = share_fact.revision_id
        share_available_from = share_fact.available_from
        share_content_hash = share_fact.content_hash
        share_source = share_fact.source_reference
        share_evidence_status = "VERIFIED_FACT"
        if shares_outstanding is not None and shares_outstanding != resolved_shares:
            caveats.append("caller_share_count_ignored_in_favor_of_verified_fact")
    elif shares_outstanding is not None:
        if shares_outstanding <= 0:
            raise ValueError("shares_outstanding must be positive")
        resolved_shares = shares_outstanding
        share_revision_id = None
        share_available_from = None
        share_content_hash = None
        share_source = None
        share_evidence_status = "UNVERIFIED_CALLER_INPUT"
        caveats.append("shares_outstanding_is_unverified_caller_input")
    else:
        resolved_shares = None
        share_revision_id = None
        share_available_from = None
        share_content_hash = None
        share_source = None
        share_evidence_status = "MISSING"
        caveats.append("share_count_not_available_by_as_of")

    bvps = book_value_per_share(equity, resolved_shares)
    metrics = compute_valuation_metrics(
        ValuationInputs(price=price, eps=eps, book_value_per_share=bvps)
    )

    classification = resolve_symbol_classification(conn, symbol, as_of_date)
    if classification is None:
        sector_code = None
        taxonomy_version = None
        classification_snapshot_id = None
        caveats.append("point_in_time_classification_missing")
    else:
        sector_code = classification.sector_code
        taxonomy_version = classification.taxonomy_version
        classification_snapshot_id = classification.source_snapshot_id

    historical_pe_pct = _historical_pe_percentile(
        conn,
        symbol,
        as_of_date,
        metrics.pe_ratio,
    )
    sector_pe_pct, peer_hash, peer_count = _sector_pe_percentile(
        conn,
        sector_code,
        as_of_date,
        symbol,
        metrics.pe_ratio,
    )

    lineage: dict[str, object] = {
        "price_basis": _RAW_BASIS,
        "price_date": price_date,
        "price_ingestion_run_id": price_run_id,
        "price_provider": price_provider,
        "fundamental_period": fundamental_period,
        "fundamental_revision_id": fundamental_revision_id,
        "fundamental_available_from": fundamental_available_from,
        "fundamental_content_hash": fundamental_content_hash,
        "shares_outstanding": resolved_shares,
        "share_count_revision_id": share_revision_id,
        "share_count_available_from": share_available_from,
        "share_count_content_hash": share_content_hash,
        "share_count_source": share_source,
        "share_count_evidence_status": share_evidence_status,
        "sector_code": sector_code,
        "taxonomy_version": taxonomy_version,
        "classification_source_snapshot_id": classification_snapshot_id,
        "classification_resolver_version": RESOLVER_VERSION,
        "sector_peer_set_hash": peer_hash,
        "sector_peer_count": peer_count,
    }

    snapshot = ValuationSnapshot(
        snapshot_id=f"val_{uuid4().hex[:16]}",
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
        caveats=tuple(sorted(set(caveats))),
        lineage=lineage,
    )
    if persist:
        snapshot = _persist(conn, snapshot)
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
    return percentile_rank(current_pe, [float(row[0]) for row in rows])


def _sector_pe_percentile(
    conn: duckdb.DuckDBPyConnection,
    sector_code: str | None,
    as_of_date: str,
    symbol: str,
    current_pe: float | None,
) -> tuple[float | None, str | None, int]:
    if current_pe is None or sector_code is None:
        return None, None, 0
    rows = conn.execute(
        """
        WITH peers AS (
            SELECT symbol, pe_ratio, as_of_date,
                   ROW_NUMBER() OVER (
                       PARTITION BY symbol ORDER BY as_of_date DESC
                   ) AS rn
            FROM valuation_snapshot
            WHERE as_of_date <= ? AND symbol <> ? AND pe_ratio IS NOT NULL
        )
        SELECT symbol, pe_ratio FROM peers WHERE rn = 1 ORDER BY symbol
        """,
        [as_of_date, symbol],
    ).fetchall()
    peers: list[tuple[str, float]] = []
    for peer_symbol, pe_ratio in rows:
        classification = resolve_symbol_classification(
            conn,
            str(peer_symbol),
            as_of_date,
        )
        if classification is not None and classification.sector_code == sector_code:
            peers.append((str(peer_symbol), float(pe_ratio)))
    peer_payload = json.dumps(peers, separators=(",", ":"))
    peer_hash = hashlib.sha256(peer_payload.encode("utf-8")).hexdigest()
    return (
        percentile_rank(current_pe, [value for _, value in peers]),
        peer_hash,
        len(peers),
    )


def _snapshot_payload(snapshot: ValuationSnapshot) -> dict[str, object]:
    return {
        "symbol": snapshot.symbol,
        "as_of_date": snapshot.as_of_date,
        "price": snapshot.price,
        "eps": snapshot.eps,
        "book_value_per_share": snapshot.book_value_per_share,
        "pe_ratio": snapshot.pe_ratio,
        "earnings_yield": snapshot.earnings_yield,
        "pb_ratio": snapshot.pb_ratio,
        "book_yield": snapshot.book_yield,
        "historical_pe_percentile": snapshot.historical_pe_percentile,
        "sector_pe_percentile": snapshot.sector_pe_percentile,
    }


def _persist(
    conn: duckdb.DuckDBPyConnection,
    snapshot: ValuationSnapshot,
) -> ValuationSnapshot:
    snapshot_key = f"{snapshot.symbol}|{snapshot.as_of_date}|{_RAW_BASIS}"
    payload = _snapshot_payload(snapshot)
    content_hash = hashlib.sha256(
        json.dumps(
            {
                "payload": payload,
                "lineage": snapshot.lineage,
                "caveats": list(snapshot.caveats),
                "contract_version": VALUATION_CONTRACT_VERSION,
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    prior = conn.execute(
        """
        SELECT revision_id, revision_number, content_hash
        FROM valuation_snapshot_revision
        WHERE snapshot_key = ? AND canonical_status = 'CURRENT'
        ORDER BY revision_number DESC LIMIT 1
        """,
        [snapshot_key],
    ).fetchone()
    if prior is not None and prior[2] == content_hash:
        revision_id = str(prior[0])
    else:
        revision_number = int(prior[1]) + 1 if prior else 1
        revision_id = f"valrev_{uuid4().hex[:16]}"
        conn.execute(
            """
            INSERT INTO valuation_snapshot_revision (
                revision_id, snapshot_key, revision_number, symbol, as_of_date,
                price_basis, content_hash, canonical_status,
                supersedes_revision_id, payload_json, lineage_json,
                caveats_json, contract_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'CURRENT', ?, ?, ?, ?, ?)
            """,
            [
                revision_id,
                snapshot_key,
                revision_number,
                snapshot.symbol,
                snapshot.as_of_date,
                _RAW_BASIS,
                content_hash,
                prior[0] if prior else None,
                json.dumps(payload, sort_keys=True, default=str),
                json.dumps(snapshot.lineage, sort_keys=True, default=str),
                json.dumps(list(snapshot.caveats)),
                VALUATION_CONTRACT_VERSION,
            ],
        )
        if prior is not None:
            conn.execute(
                """
                UPDATE valuation_snapshot_revision
                SET canonical_status = 'SUPERSEDED', superseded_by_revision_id = ?
                WHERE revision_id = ?
                """,
                [revision_id, prior[0]],
            )

    conn.execute(
        "DELETE FROM valuation_snapshot WHERE symbol = ? AND as_of_date = ? "
        "AND price_basis = ?",
        [snapshot.symbol, snapshot.as_of_date, _RAW_BASIS],
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
            revision_id,
            snapshot.symbol,
            snapshot.as_of_date,
            snapshot.price,
            _RAW_BASIS,
            snapshot.lineage.get("price_date"),
            snapshot.eps,
            snapshot.book_value_per_share,
            snapshot.lineage.get("shares_outstanding"),
            snapshot.lineage.get("fundamental_period"),
            snapshot.lineage.get("fundamental_available_from"),
            snapshot.lineage.get("sector_code"),
            snapshot.lineage.get("taxonomy_version"),
            snapshot.pe_ratio,
            snapshot.earnings_yield,
            snapshot.pb_ratio,
            snapshot.book_yield,
            snapshot.historical_pe_percentile,
            snapshot.sector_pe_percentile,
            json.dumps(list(snapshot.caveats)),
            json.dumps(snapshot.lineage, sort_keys=True, default=str),
            VALUATION_CONTRACT_VERSION,
        ],
    )
    return ValuationSnapshot(
        snapshot_id=revision_id,
        symbol=snapshot.symbol,
        as_of_date=snapshot.as_of_date,
        price=snapshot.price,
        eps=snapshot.eps,
        book_value_per_share=snapshot.book_value_per_share,
        pe_ratio=snapshot.pe_ratio,
        earnings_yield=snapshot.earnings_yield,
        pb_ratio=snapshot.pb_ratio,
        book_yield=snapshot.book_yield,
        historical_pe_percentile=snapshot.historical_pe_percentile,
        sector_pe_percentile=snapshot.sector_pe_percentile,
        caveats=snapshot.caveats,
        lineage=snapshot.lineage,
    )


def get_valuation_snapshot(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    as_of_date: str,
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
        snapshot_id=str(row[0]),
        symbol=str(row[1]),
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
    "VALUATION_CONTRACT_VERSION",
    "ValuationSnapshot",
    "build_valuation_snapshot",
    "get_valuation_snapshot",
]
