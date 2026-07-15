"""Persistence for source-backed symbol lifecycle and taxonomy snapshots."""

from __future__ import annotations

from dataclasses import dataclass

import duckdb

from vnalpha.ingestion.symbol_taxonomy import SymbolTaxonomy


@dataclass(frozen=True, slots=True)
class SymbolTaxonomyAsOf:
    """A historical taxonomy classification selected for one as-of instant."""

    symbol: str
    security_type: str
    lifecycle_status: str
    sector_code: str | None
    sector_name: str | None
    industry_code: str | None
    industry_name: str | None
    taxonomy_name: str
    taxonomy_version: str


def start_symbol_source_snapshot(
    conn: duckdb.DuckDBPyConnection,
    snapshot_id: str,
    source: str,
    authoritative: bool,
    correlation_id: str,
) -> None:
    """Create the auditable source snapshot before its records are processed."""

    conn.execute(
        """
        INSERT INTO symbol_source_snapshot
            (snapshot_id, ingestion_run_id, source, is_authoritative,
             snapshot_status, correlation_id)
        VALUES (?, ?, ?, ?, 'RUNNING', ?)
        """,
        [snapshot_id, snapshot_id, source, authoritative, correlation_id],
    )


def persist_symbol_taxonomy(
    conn: duckdb.DuckDBPyConnection,
    snapshot_id: str,
    taxonomy: SymbolTaxonomy,
) -> None:
    """Update the current projection and retain a changed classification history."""

    _upsert_current_symbol(conn, snapshot_id, taxonomy)
    _record_classification_revision(conn, snapshot_id, taxonomy)
    conn.execute(
        """
        INSERT INTO symbol_source_membership (source_snapshot_id, symbol, source)
        VALUES (?, ?, ?)
        ON CONFLICT (source_snapshot_id, symbol) DO NOTHING
        """,
        [snapshot_id, taxonomy.symbol, taxonomy.classification_source],
    )


def complete_symbol_source_snapshot(
    conn: duckdb.DuckDBPyConnection,
    snapshot_id: str,
    status: str,
    observed_count: int,
    synced_count: int,
    error_count: int,
    deactivated_count: int,
) -> None:
    """Persist terminal snapshot counts only after reconciliation decisions finish."""

    conn.execute(
        """
        UPDATE symbol_source_snapshot
        SET snapshot_status = ?, observed_count = ?, synced_count = ?,
            error_count = ?, deactivated_count = ?, completed_at = current_timestamp
        WHERE snapshot_id = ?
        """,
        [
            status,
            observed_count,
            synced_count,
            error_count,
            deactivated_count,
            snapshot_id,
        ],
    )


def deactivate_unseen_symbols(
    conn: duckdb.DuckDBPyConnection,
    snapshot_id: str,
    source: str,
) -> int:
    """Deactivate only source-owned symbols absent from a completed snapshot."""

    rows = conn.execute(
        """
        SELECT symbol
        FROM symbol_master
        WHERE classification_source = ? AND is_active = TRUE
          AND NOT EXISTS (
              SELECT 1
              FROM symbol_source_membership membership
              WHERE membership.source_snapshot_id = ?
                AND membership.symbol = symbol_master.symbol
          )
        """,
        [source, snapshot_id],
    ).fetchall()
    if rows:
        conn.execute(
            """
            UPDATE symbol_master
            SET is_active = FALSE, lifecycle_status = 'INACTIVE'
            WHERE classification_source = ? AND is_active = TRUE
              AND NOT EXISTS (
                  SELECT 1
                  FROM symbol_source_membership membership
                  WHERE membership.source_snapshot_id = ?
                    AND membership.symbol = symbol_master.symbol
              )
            """,
            [source, snapshot_id],
        )
    return len(rows)


def get_symbol_taxonomy_as_of(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    as_of: object,
) -> SymbolTaxonomyAsOf | None:
    """Return the latest effective taxonomy row for a symbol at an as-of date."""

    row = conn.execute(
        """
        SELECT symbol, security_type, lifecycle_status, sector_code, sector_name,
               industry_code, industry_name, taxonomy_name, taxonomy_version
        FROM symbol_classification_history
        WHERE symbol = ? AND effective_from <= ?
          AND (effective_to IS NULL OR effective_to > ?)
        ORDER BY effective_from DESC, source_snapshot_id DESC
        LIMIT 1
        """,
        [symbol, as_of, as_of],
    ).fetchone()
    return SymbolTaxonomyAsOf(*row) if row is not None else None


def _upsert_current_symbol(
    conn: duckdb.DuckDBPyConnection,
    snapshot_id: str,
    taxonomy: SymbolTaxonomy,
) -> None:
    conn.execute(
        """
        INSERT INTO symbol_master (
            symbol, exchange, name, sector, industry, is_active, last_seen_at,
            security_type, listing_date, delisting_date, lifecycle_status,
            sector_code, sector_name, industry_code, industry_name, taxonomy_name,
            taxonomy_version, classification_source,
            classification_effective_from, last_seen_source_snapshot_id
        )
        VALUES (?, ?, ?, ?, ?, ?, current_timestamp, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                COALESCE(CAST(? AS TIMESTAMPTZ), current_timestamp), ?)
        ON CONFLICT (symbol) DO UPDATE SET
            exchange = excluded.exchange,
            name = excluded.name,
            sector = excluded.sector,
            industry = excluded.industry,
            is_active = excluded.is_active,
            last_seen_at = excluded.last_seen_at,
            security_type = excluded.security_type,
            listing_date = excluded.listing_date,
            delisting_date = excluded.delisting_date,
            lifecycle_status = excluded.lifecycle_status,
            sector_code = excluded.sector_code,
            sector_name = excluded.sector_name,
            industry_code = excluded.industry_code,
            industry_name = excluded.industry_name,
            taxonomy_name = excluded.taxonomy_name,
            taxonomy_version = excluded.taxonomy_version,
            classification_source = excluded.classification_source,
            classification_effective_from = excluded.classification_effective_from,
            last_seen_source_snapshot_id = excluded.last_seen_source_snapshot_id
        """,
        [
            taxonomy.symbol,
            taxonomy.exchange,
            taxonomy.name,
            taxonomy.sector_name,
            taxonomy.industry_name,
            taxonomy.is_active_common_equity,
            taxonomy.security_type,
            taxonomy.listing_date,
            taxonomy.delisting_date,
            taxonomy.lifecycle_status,
            taxonomy.sector_code,
            taxonomy.sector_name,
            taxonomy.industry_code,
            taxonomy.industry_name,
            taxonomy.taxonomy_name,
            taxonomy.taxonomy_version,
            taxonomy.classification_source,
            taxonomy.effective_from,
            snapshot_id,
        ],
    )


def _record_classification_revision(
    conn: duckdb.DuckDBPyConnection,
    snapshot_id: str,
    taxonomy: SymbolTaxonomy,
) -> None:
    current = conn.execute(
        """
        SELECT security_type, lifecycle_status, listing_date, delisting_date,
               sector_code, sector_name, industry_code, industry_name,
               taxonomy_name, taxonomy_version, classification_source
        FROM symbol_classification_history
        WHERE symbol = ? AND effective_to IS NULL
        ORDER BY effective_from DESC
        LIMIT 1
        """,
        [taxonomy.symbol],
    ).fetchone()
    if current == _classification_values(taxonomy):
        return
    conn.execute(
        """
        UPDATE symbol_classification_history
        SET effective_to = COALESCE(CAST(? AS TIMESTAMPTZ), current_timestamp)
        WHERE symbol = ? AND effective_to IS NULL
        """,
        [taxonomy.effective_from, taxonomy.symbol],
    )
    conn.execute(
        """
        INSERT INTO symbol_classification_history (
            symbol, effective_from, source_snapshot_id, classification_source,
            security_type, lifecycle_status, listing_date, delisting_date,
            sector_code, sector_name, industry_code, industry_name, taxonomy_name,
            taxonomy_version
        )
        VALUES (?, COALESCE(CAST(? AS TIMESTAMPTZ), current_timestamp), ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?)
        """,
        [
            taxonomy.symbol,
            taxonomy.effective_from,
            snapshot_id,
            taxonomy.classification_source,
            *_classification_values(taxonomy)[:-1],
        ],
    )


def _classification_values(taxonomy: SymbolTaxonomy) -> tuple[object, ...]:
    return (
        taxonomy.security_type,
        taxonomy.lifecycle_status,
        taxonomy.listing_date,
        taxonomy.delisting_date,
        taxonomy.sector_code,
        taxonomy.sector_name,
        taxonomy.industry_code,
        taxonomy.industry_name,
        taxonomy.taxonomy_name,
        taxonomy.taxonomy_version,
        taxonomy.classification_source,
    )
