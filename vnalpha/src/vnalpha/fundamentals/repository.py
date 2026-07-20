"""Persistence and publication-aware as-of queries for fundamentals."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

from vnalpha.fundamentals.models import (
    FUNDAMENTALS_CONTRACT_VERSION,
    AuditStatus,
    FundamentalFact,
    StatementScope,
    compute_debt_to_equity,
    compute_roe,
    fact_content_hash,
)

if TYPE_CHECKING:
    import duckdb


@dataclass(frozen=True, slots=True)
class AsOfFact:
    symbol: str
    fiscal_year: int
    fiscal_period: str
    statement_scope: str
    published_at: str
    available_from: str
    period_end_date: str
    audit_status: str
    currency: str
    unit: str
    revenue: float | None
    net_income: float | None
    eps: float | None
    total_assets: float | None
    total_equity: float | None
    total_liabilities: float | None
    operating_cash_flow: float | None
    roe: float | None
    debt_to_equity: float | None
    revision_id: str
    revision_number: int
    source_reference: str
    content_hash: str
    is_stale: bool
    caveats: tuple[str, ...]


def upsert_fundamental_fact(
    conn: duckdb.DuckDBPyConnection,
    fact: FundamentalFact,
) -> str:
    """Persist one immutable fact revision idempotently."""
    content_hash = fact_content_hash(fact)
    available_from = fact.available_from or f"{fact.published_at}T00:00:00+07:00"
    existing = conn.execute(
        """
        SELECT revision_id, content_hash
        FROM fundamental_fact
        WHERE fact_id = ? AND revision_number = ?
        """,
        [fact.fact_id, fact.revision_number],
    ).fetchone()
    if existing is not None:
        if existing[1] != content_hash:
            raise ValueError(
                f"revision {fact.fact_id}#{fact.revision_number} already exists "
                "with different content; restatements require a new revision_number"
            )
        return str(existing[0])

    revision_id = f"fund_{uuid4().hex[:16]}"
    prior = conn.execute(
        """
        SELECT revision_id FROM fundamental_fact
        WHERE fact_id = ? AND canonical_status = 'CURRENT'
        ORDER BY revision_number DESC LIMIT 1
        """,
        [fact.fact_id],
    ).fetchone()
    conn.execute(
        """
        INSERT INTO fundamental_fact (
            revision_id, fact_id, revision_number, symbol, fiscal_year,
            fiscal_period, statement_scope, published_at, available_from,
            period_end_date, audit_status, currency, unit,
            revenue, net_income, eps, total_assets, total_equity,
            total_liabilities, operating_cash_flow,
            source_reference, source_authority, content_hash, revision_hash,
            canonical_status, supersedes_revision_id, contract_version,
            diagnostics_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                  ?, ?, ?, ?, 'CURRENT', ?, ?, ?)
        """,
        [
            revision_id,
            fact.fact_id,
            fact.revision_number,
            fact.symbol,
            fact.fiscal_year,
            fact.fiscal_period,
            fact.statement_scope.value,
            fact.published_at,
            available_from,
            fact.period_end_date,
            fact.audit_status.value,
            fact.currency,
            fact.unit,
            fact.revenue,
            fact.net_income,
            fact.eps,
            fact.total_assets,
            fact.total_equity,
            fact.total_liabilities,
            fact.operating_cash_flow,
            fact.source_reference,
            fact.source_authority,
            content_hash,
            content_hash,
            prior[0] if prior else None,
            FUNDAMENTALS_CONTRACT_VERSION,
            json.dumps({}),
        ],
    )
    if prior is not None:
        conn.execute(
            """
            UPDATE fundamental_fact
            SET canonical_status = 'SUPERSEDED', superseded_by_revision_id = ?
            WHERE revision_id = ?
            """,
            [revision_id, prior[0]],
        )
    conn.commit()
    return revision_id


def get_fact_revisions(
    conn: duckdb.DuckDBPyConnection,
    fact_id: str,
) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT revision_id, revision_number, canonical_status, published_at,
               available_from, content_hash, supersedes_revision_id,
               superseded_by_revision_id
        FROM fundamental_fact
        WHERE fact_id = ?
        ORDER BY revision_number
        """,
        [fact_id],
    ).fetchall()
    return [
        {
            "revision_id": row[0],
            "revision_number": row[1],
            "canonical_status": row[2],
            "published_at": str(row[3]),
            "available_from": str(row[4]),
            "content_hash": row[5],
            "supersedes_revision_id": row[6],
            "superseded_by_revision_id": row[7],
        }
        for row in rows
    ]


def as_of_snapshot(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    as_of_date: str,
    *,
    statement_scope: StatementScope = StatementScope.CONSOLIDATED,
    stale_after_days: int = 400,
) -> list[AsOfFact]:
    """Return the latest revision whose evidence was available by the as-of day.

    ``available_from`` rather than fiscal period end or publication label controls
    visibility. The end of the requested calendar day is used for date-only
    callers; later revisions cannot erase the revision visible on an earlier day.
    """
    rows = conn.execute(
        """
        WITH visible AS (
            SELECT *,
                   ROW_NUMBER() OVER (
                       PARTITION BY fiscal_year, fiscal_period
                       ORDER BY available_from DESC, revision_number DESC
                   ) AS rn
            FROM fundamental_fact
            WHERE symbol = ?
              AND statement_scope = ?
              AND available_from < CAST(? AS DATE) + INTERVAL 1 DAY
        )
        SELECT symbol, fiscal_year, fiscal_period, statement_scope,
               published_at, available_from, period_end_date, audit_status,
               currency, unit, revenue, net_income, eps, total_assets,
               total_equity, total_liabilities, operating_cash_flow,
               revision_id, revision_number, source_reference, content_hash
        FROM visible
        WHERE rn = 1
        ORDER BY fiscal_year DESC, fiscal_period DESC
        """,
        [symbol.upper(), statement_scope.value, as_of_date],
    ).fetchall()

    snapshot: list[AsOfFact] = []
    for row in rows:
        (
            sym,
            fiscal_year,
            fiscal_period,
            scope,
            published_at,
            available_from,
            period_end_date,
            audit_status,
            currency,
            unit,
            revenue,
            net_income,
            eps,
            total_assets,
            total_equity,
            total_liabilities,
            operating_cash_flow,
            revision_id,
            revision_number,
            source_reference,
            content_hash,
        ) = row
        caveats: list[str] = []
        is_stale = _days_between(str(period_end_date), as_of_date) > stale_after_days
        if is_stale:
            caveats.append(
                f"latest available period ends {period_end_date}, older than "
                f"{stale_after_days} days before as-of {as_of_date}"
            )
        if audit_status != AuditStatus.AUDITED.value:
            caveats.append(f"audit_status={audit_status}")
        snapshot.append(
            AsOfFact(
                symbol=sym,
                fiscal_year=fiscal_year,
                fiscal_period=fiscal_period,
                statement_scope=scope,
                published_at=str(published_at),
                available_from=str(available_from),
                period_end_date=str(period_end_date),
                audit_status=audit_status,
                currency=currency,
                unit=unit,
                revenue=revenue,
                net_income=net_income,
                eps=eps,
                total_assets=total_assets,
                total_equity=total_equity,
                total_liabilities=total_liabilities,
                operating_cash_flow=operating_cash_flow,
                roe=compute_roe(net_income, total_equity),
                debt_to_equity=compute_debt_to_equity(
                    total_liabilities, total_equity
                ),
                revision_id=str(revision_id),
                revision_number=revision_number,
                source_reference=str(source_reference),
                content_hash=str(content_hash),
                is_stale=is_stale,
                caveats=tuple(caveats),
            )
        )
    return snapshot


def _days_between(start_iso: str, end_iso: str) -> int:
    from datetime import date

    start = date.fromisoformat(start_iso[:10])
    end = date.fromisoformat(end_iso[:10])
    return (end - start).days


__all__ = [
    "AsOfFact",
    "as_of_snapshot",
    "get_fact_revisions",
    "upsert_fundamental_fact",
]
