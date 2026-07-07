"""lineage.get_symbol_lineage tool."""

from __future__ import annotations

import json

import duckdb

from vnalpha.tools.models import ToolOutput


def get_symbol_lineage(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    date: str,
) -> ToolOutput:
    """Return provider, ingestion run, feature date, and scoring version for a symbol."""
    # Get lineage from candidate_score
    row = conn.execute(
        """
        SELECT lineage_json, score, candidate_class
        FROM candidate_score
        WHERE symbol = ? AND date = ?
        """,
        [symbol, date],
    ).fetchone()
    if row is None:
        return ToolOutput(
            data=None,
            summary=f"No lineage found for {symbol} on {date}.",
            warnings=["Run 'vnalpha score' to generate candidate scores."],
        )
    lineage_raw, score, candidate_class = row
    lineage = (
        json.loads(lineage_raw) if isinstance(lineage_raw, str) else lineage_raw or {}
    )

    # Get latest ingestion run info
    ing_row = conn.execute(
        """
        SELECT ingestion_run_id, source_service, source_endpoint, started_at, status
        FROM ingestion_run
        WHERE ingestion_run_id = ?
        """,
        [lineage.get("ingestion_run_id", "")],
    ).fetchone()

    result = {
        "symbol": symbol,
        "date": date,
        "score": score,
        "candidate_class": candidate_class,
        "scoring_version": lineage.get("scoring_version"),
        "feature_date": lineage.get("feature_date"),
        "generated_at": lineage.get("generated_at"),
        "provider": lineage.get("provider"),
        "ingestion_run_id": lineage.get("ingestion_run_id"),
    }
    if ing_row:
        result["ingestion_source_service"] = ing_row[1]
        result["ingestion_source_endpoint"] = ing_row[2]
        result["ingestion_started_at"] = str(ing_row[3]) if ing_row[3] else None
        result["ingestion_status"] = ing_row[4]

    return ToolOutput(
        data=result,
        summary=(
            f"{symbol}: scoring_version={result['scoring_version']} "
            f"feature_date={result['feature_date']}"
        ),
    )
