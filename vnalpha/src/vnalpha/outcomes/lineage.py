from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import TYPE_CHECKING

from vnalpha.warehouse.point_in_time import resolve_universe

if TYPE_CHECKING:
    import duckdb


def persist_outcome_lineage(
    conn: duckdb.DuckDBPyConnection,
    watchlist_date: str,
    horizon_sessions: int,
) -> int:
    """Persist exact RankingRun, universe and factor lineage for outcome rows."""
    rows = conn.execute(
        """
        SELECT symbol, scoring_policy_hash, corporate_action_lineage_json,
               price_basis, adjustment_version
        FROM candidate_outcome
        WHERE watchlist_date = ? AND horizon_sessions = ?
        ORDER BY symbol
        """,
        [watchlist_date, horizon_sessions],
    ).fetchall()
    if not rows:
        return 0

    universe = resolve_universe(conn, date.fromisoformat(watchlist_date))
    candidate_symbols = [str(row[0]) for row in rows]
    universe_payload = {
        "watchlist_date": watchlist_date,
        "resolver_version": universe.resolver_version,
        "symbols": {
            symbol: _classification_payload(universe.get(symbol))
            for symbol in sorted(candidate_symbols)
        },
    }
    eligible_universe_hash = _hash(universe_payload)

    updated = 0
    for symbol, policy_hash, action_lineage_json, price_basis, adjustment_version in rows:
        ranking_run_ref = (
            f"{watchlist_date}:{policy_hash}" if policy_hash else None
        )
        factor_chain_hash = _hash(
            {
                "corporate_action_lineage": _safe_json(action_lineage_json, []),
                "price_basis": price_basis or "UNKNOWN",
                "adjustment_version": adjustment_version or "UNKNOWN",
            }
        )
        conn.execute(
            """
            UPDATE candidate_outcome
            SET ranking_run_ref = ?, eligible_universe_hash = ?,
                factor_chain_hash = ?
            WHERE symbol = ? AND watchlist_date = ? AND horizon_sessions = ?
            """,
            [
                ranking_run_ref,
                eligible_universe_hash,
                factor_chain_hash,
                symbol,
                watchlist_date,
                horizon_sessions,
            ],
        )
        updated += 1
    conn.commit()
    return updated


def _classification_payload(classification) -> dict[str, object] | None:
    if classification is None:
        return None
    return {
        "source_snapshot_id": classification.source_snapshot_id,
        "exchange": classification.exchange,
        "security_type": classification.security_type,
        "lifecycle_status": classification.lifecycle_status,
        "sector_code": classification.sector_code,
        "industry_code": classification.industry_code,
        "taxonomy_version": classification.taxonomy_version,
        "ambiguous": classification.ambiguous,
    }


def _safe_json(value: object, default: object) -> object:
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value


def _hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = ["persist_outcome_lineage"]
