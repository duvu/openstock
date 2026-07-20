from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any, Mapping

from vnalpha.symbol_memory.ingestion import MemoryEvidence
from vnalpha.symbol_memory.paths import normalize_symbol

if TYPE_CHECKING:
    import duckdb


def material_research_evidence(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    *,
    as_of_date: date,
    correlation_id: str,
) -> tuple[MemoryEvidence, ...]:
    """Return one bounded material claim per supported research evidence family."""
    canonical_symbol = normalize_symbol(symbol)
    observed_at = datetime.now(UTC)
    evidence: list[MemoryEvidence] = []

    fundamental = _latest_fundamental(conn, canonical_symbol, as_of_date)
    if fundamental is not None:
        value = _fundamental_value(fundamental)
        evidence.append(
            MemoryEvidence(
                symbol=canonical_symbol,
                claim_type="fundamental_state",
                predicate="latest_published_fundamentals",
                value=value,
                source_ref=f"fundamental_fact:{fundamental['revision_id']}",
                observed_at=observed_at,
                as_of_date=as_of_date,
                confidence=1.0,
                correlation_id=correlation_id,
                source_published_at=date.fromisoformat(
                    str(fundamental["published_at"])[:10]
                ),
            )
        )

    valuation = _latest_valuation(conn, canonical_symbol, as_of_date)
    if valuation is not None and any(
        valuation[key] is not None
        for key in ("pe_ratio", "pb_ratio", "historical_pe_percentile", "sector_pe_percentile")
    ):
        evidence.append(
            MemoryEvidence(
                symbol=canonical_symbol,
                claim_type="valuation_state",
                predicate="latest_valuation_context",
                value=_valuation_value(valuation),
                source_ref=f"valuation_snapshot:{valuation['snapshot_id']}",
                observed_at=observed_at,
                as_of_date=as_of_date,
                confidence=1.0,
                correlation_id=correlation_id,
            )
        )

    verified_event = _latest_verified_event(conn, canonical_symbol, as_of_date)
    if verified_event is not None:
        evidence.append(
            MemoryEvidence(
                symbol=canonical_symbol,
                claim_type="verified_event",
                predicate="latest_material_official_event",
                value=_event_value(verified_event),
                source_ref=f"symbol_event:{verified_event['revision_id']}",
                observed_at=observed_at,
                as_of_date=as_of_date,
                confidence=1.0,
                correlation_id=correlation_id,
                source_published_at=date.fromisoformat(
                    str(verified_event["published_at"])[:10]
                ),
            )
        )

    outcome = _latest_material_outcome(conn, canonical_symbol, as_of_date)
    if outcome is not None:
        evidence.append(
            MemoryEvidence(
                symbol=canonical_symbol,
                claim_type="observed_outcome",
                predicate="latest_t20_candidate_outcome",
                value=_outcome_value(outcome),
                source_ref=(
                    f"candidate_outcome:{canonical_symbol}:"
                    f"{outcome['watchlist_date']}:20"
                ),
                observed_at=observed_at,
                as_of_date=as_of_date,
                confidence=1.0,
                correlation_id=correlation_id,
            )
        )
    return tuple(evidence)


def matches_persisted_research_evidence(
    conn: duckdb.DuckDBPyConnection,
    source_ref: str,
    symbol: str,
    as_of_date: date,
    claim_type: str,
    predicate: str,
    value: Mapping[str, Any],
) -> bool:
    """Validate material memory claims against exact persisted source identity."""
    source_kind, separator, identifier = source_ref.partition(":")
    if not separator:
        return False
    canonical_symbol = normalize_symbol(symbol)
    if source_kind == "fundamental_fact":
        row = _fundamental_by_revision(conn, identifier)
        return (
            row is not None
            and row["symbol"] == canonical_symbol
            and row["available_from"][:10] <= as_of_date.isoformat()
            and claim_type == "fundamental_state"
            and predicate == "latest_published_fundamentals"
            and value == _fundamental_value(row)
        )
    if source_kind == "valuation_snapshot":
        row = _valuation_by_id(conn, identifier)
        return (
            row is not None
            and row["symbol"] == canonical_symbol
            and row["as_of_date"] <= as_of_date.isoformat()
            and claim_type == "valuation_state"
            and predicate == "latest_valuation_context"
            and value == _valuation_value(row)
        )
    if source_kind == "symbol_event":
        row = _event_by_revision(conn, identifier)
        return (
            row is not None
            and row["symbol"] == canonical_symbol
            and row["published_at"] <= as_of_date.isoformat()
            and row["verification_status"] == "VERIFIED"
            and claim_type == "verified_event"
            and predicate == "latest_material_official_event"
            and value == _event_value(row)
        )
    if source_kind == "candidate_outcome":
        parts = identifier.split(":")
        if len(parts) != 3 or normalize_symbol(parts[0]) != canonical_symbol:
            return False
        try:
            horizon = int(parts[2])
        except ValueError:
            return False
        row = _outcome_by_key(conn, canonical_symbol, parts[1], horizon)
        return (
            row is not None
            and row["outcome_status"] == "COMPLETE"
            and row["observation_end_date"] <= as_of_date.isoformat()
            and claim_type == "observed_outcome"
            and predicate == "latest_t20_candidate_outcome"
            and value == _outcome_value(row)
        )
    return False


def _latest_fundamental(conn, symbol: str, as_of_date: date):
    row = conn.execute(
        """
        SELECT revision_id, symbol, fiscal_year, fiscal_period, statement_scope,
               published_at, available_from, audit_status, revenue, net_income,
               eps, total_equity, total_liabilities, operating_cash_flow,
               currency, unit, content_hash
        FROM fundamental_fact
        WHERE symbol = ?
          AND available_from < CAST(? AS DATE) + INTERVAL 1 DAY
        ORDER BY available_from DESC, revision_number DESC
        LIMIT 1
        """,
        [symbol, as_of_date],
    ).fetchone()
    return None if row is None else _fundamental_row(row)


def _fundamental_by_revision(conn, revision_id: str):
    row = conn.execute(
        """
        SELECT revision_id, symbol, fiscal_year, fiscal_period, statement_scope,
               published_at, available_from, audit_status, revenue, net_income,
               eps, total_equity, total_liabilities, operating_cash_flow,
               currency, unit, content_hash
        FROM fundamental_fact WHERE revision_id = ?
        """,
        [revision_id],
    ).fetchone()
    return None if row is None else _fundamental_row(row)


def _fundamental_row(row) -> dict[str, Any]:
    keys = (
        "revision_id",
        "symbol",
        "fiscal_year",
        "fiscal_period",
        "statement_scope",
        "published_at",
        "available_from",
        "audit_status",
        "revenue",
        "net_income",
        "eps",
        "total_equity",
        "total_liabilities",
        "operating_cash_flow",
        "currency",
        "reported_unit",
        "content_hash",
    )
    result = dict(zip(keys, row, strict=True))
    for key in ("published_at", "available_from"):
        result[key] = str(result[key])
    result["symbol"] = normalize_symbol(str(result["symbol"]))
    return result


def _fundamental_value(row: Mapping[str, Any]) -> dict[str, Any]:
    equity = row.get("total_equity")
    net_income = row.get("net_income")
    liabilities = row.get("total_liabilities")
    roe = (
        float(net_income) / float(equity)
        if net_income is not None and equity not in (None, 0)
        else None
    )
    debt_to_equity = (
        float(liabilities) / float(equity)
        if liabilities is not None and equity not in (None, 0)
        else None
    )
    return {
        "period": (
            f"{row['fiscal_year']}:{row['fiscal_period']}:"
            f"{row['statement_scope']}"
        ),
        "available_from": str(row["available_from"]),
        "audit_status": row["audit_status"],
        "roe": roe,
        "debt_to_equity": debt_to_equity,
        "currency": row["currency"],
        "reported_unit": row["reported_unit"],
        "content_hash": row["content_hash"],
        "unit": "ratio",
        "meaning": "latest publication-aware fundamental state",
    }


def _latest_valuation(conn, symbol: str, as_of_date: date):
    row = conn.execute(
        """
        SELECT snapshot_id, symbol, as_of_date, pe_ratio, pb_ratio,
               historical_pe_percentile, sector_pe_percentile,
               lineage_json, contract_version
        FROM valuation_snapshot
        WHERE symbol = ? AND as_of_date <= ?
        ORDER BY as_of_date DESC LIMIT 1
        """,
        [symbol, as_of_date],
    ).fetchone()
    return None if row is None else _valuation_row(row)


def _valuation_by_id(conn, snapshot_id: str):
    row = conn.execute(
        """
        SELECT snapshot_id, symbol, as_of_date, pe_ratio, pb_ratio,
               historical_pe_percentile, sector_pe_percentile,
               lineage_json, contract_version
        FROM valuation_snapshot WHERE snapshot_id = ?
        """,
        [snapshot_id],
    ).fetchone()
    return None if row is None else _valuation_row(row)


def _valuation_row(row) -> dict[str, Any]:
    result = dict(
        zip(
            (
                "snapshot_id",
                "symbol",
                "as_of_date",
                "pe_ratio",
                "pb_ratio",
                "historical_pe_percentile",
                "sector_pe_percentile",
                "lineage_json",
                "contract_version",
            ),
            row,
            strict=True,
        )
    )
    result["symbol"] = normalize_symbol(str(result["symbol"]))
    result["as_of_date"] = str(result["as_of_date"])
    return result


def _valuation_value(row: Mapping[str, Any]) -> dict[str, Any]:
    try:
        lineage = json.loads(str(row.get("lineage_json") or "{}"))
    except json.JSONDecodeError:
        lineage = {}
    return {
        "pe_ratio": row.get("pe_ratio"),
        "pb_ratio": row.get("pb_ratio"),
        "historical_pe_percentile": row.get("historical_pe_percentile"),
        "sector_pe_percentile": row.get("sector_pe_percentile"),
        "price_basis": lineage.get("price_basis", "UNKNOWN"),
        "contract_version": row.get("contract_version"),
        "unit": "multiple_or_percentile",
        "meaning": "latest persisted valuation context",
    }


def _latest_verified_event(conn, symbol: str, as_of_date: date):
    row = conn.execute(
        """
        WITH visible AS (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY event_id
                ORDER BY published_at DESC, revision_number DESC
            ) AS rn
            FROM symbol_event
            WHERE symbol = ? AND published_at <= ?
              AND verification_status = 'VERIFIED'
        )
        SELECT revision_id, symbol, event_type, verification_status,
               published_at, event_date, issuer_reference, source_authority,
               content_hash, revision_number
        FROM visible WHERE rn = 1
        ORDER BY published_at DESC, event_id LIMIT 1
        """,
        [symbol, as_of_date],
    ).fetchone()
    return None if row is None else _event_row(row)


def _event_by_revision(conn, revision_id: str):
    row = conn.execute(
        """
        SELECT revision_id, symbol, event_type, verification_status,
               published_at, event_date, issuer_reference, source_authority,
               content_hash, revision_number
        FROM symbol_event WHERE revision_id = ?
        """,
        [revision_id],
    ).fetchone()
    return None if row is None else _event_row(row)


def _event_row(row) -> dict[str, Any]:
    result = dict(
        zip(
            (
                "revision_id",
                "symbol",
                "event_type",
                "verification_status",
                "published_at",
                "event_date",
                "issuer_reference",
                "source_authority",
                "content_hash",
                "revision_number",
            ),
            row,
            strict=True,
        )
    )
    result["symbol"] = normalize_symbol(str(result["symbol"]))
    result["published_at"] = str(result["published_at"])
    result["event_date"] = (
        str(result["event_date"]) if result["event_date"] is not None else None
    )
    return result


def _event_value(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "event_type": row["event_type"],
        "published_at": row["published_at"],
        "event_date": row["event_date"],
        "source_authority": row["source_authority"],
        "issuer_reference": row["issuer_reference"],
        "content_hash": row["content_hash"],
        "revision_number": row["revision_number"],
    }


def _latest_material_outcome(conn, symbol: str, as_of_date: date):
    row = conn.execute(
        """
        SELECT symbol, watchlist_date, horizon_sessions, observation_end_date,
               forward_return, excess_return_vs_vnindex, max_gain, max_drawdown,
               price_basis, adjustment_version, factor_chain_hash,
               scoring_policy_hash, ranking_run_ref, eligible_universe_hash,
               outcome_status
        FROM candidate_outcome
        WHERE symbol = ? AND horizon_sessions = 20
          AND outcome_status = 'COMPLETE'
          AND observation_end_date <= ?
        ORDER BY observation_end_date DESC, watchlist_date DESC LIMIT 1
        """,
        [symbol, as_of_date],
    ).fetchone()
    return None if row is None else _outcome_row(row)


def _outcome_by_key(conn, symbol: str, watchlist_date: str, horizon: int):
    row = conn.execute(
        """
        SELECT symbol, watchlist_date, horizon_sessions, observation_end_date,
               forward_return, excess_return_vs_vnindex, max_gain, max_drawdown,
               price_basis, adjustment_version, factor_chain_hash,
               scoring_policy_hash, ranking_run_ref, eligible_universe_hash,
               outcome_status
        FROM candidate_outcome
        WHERE symbol = ? AND watchlist_date = ? AND horizon_sessions = ?
        """,
        [symbol, watchlist_date, horizon],
    ).fetchone()
    return None if row is None else _outcome_row(row)


def _outcome_row(row) -> dict[str, Any]:
    result = dict(
        zip(
            (
                "symbol",
                "watchlist_date",
                "horizon_sessions",
                "observation_end_date",
                "forward_return",
                "excess_return_vs_vnindex",
                "max_gain",
                "max_drawdown",
                "price_basis",
                "adjustment_version",
                "factor_chain_hash",
                "scoring_policy_hash",
                "ranking_run_ref",
                "eligible_universe_hash",
                "outcome_status",
            ),
            row,
            strict=True,
        )
    )
    result["symbol"] = normalize_symbol(str(result["symbol"]))
    result["watchlist_date"] = str(result["watchlist_date"])
    result["observation_end_date"] = str(result["observation_end_date"])
    return result


def _outcome_value(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "watchlist_date": row["watchlist_date"],
        "horizon_sessions": row["horizon_sessions"],
        "observation_end_date": row["observation_end_date"],
        "forward_return": row["forward_return"],
        "excess_return_vs_vnindex": row["excess_return_vs_vnindex"],
        "max_favorable_excursion": row["max_gain"],
        "max_adverse_excursion": row["max_drawdown"],
        "price_basis": row["price_basis"],
        "adjustment_version": row["adjustment_version"],
        "factor_chain_hash": row["factor_chain_hash"],
        "scoring_policy_hash": row["scoring_policy_hash"],
        "ranking_run_ref": row["ranking_run_ref"],
        "eligible_universe_hash": row["eligible_universe_hash"],
        "unit": "decimal_return",
        "meaning": "latest complete deterministic T+20 candidate outcome",
    }


__all__ = [
    "matches_persisted_research_evidence",
    "material_research_evidence",
]
