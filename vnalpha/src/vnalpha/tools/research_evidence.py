from __future__ import annotations

import duckdb

from vnalpha.commands.normalizers import normalize_date, normalize_setup_type, normalize_symbol
from vnalpha.tools.errors import ToolExecutionError
from vnalpha.tools.models import ToolOutput
from vnalpha.tools.research_intelligence_common import (
    RESEARCH_TOOL_VERSION,
    bounded_int,
    get_score,
    resolve_symbol_date,
)


def get_setup_history(
    conn: duckdb.DuckDBPyConnection,
    setup_type: str | None = None,
    symbol: str | None = None,
    date: str | None = None,
    horizon: int = 20,
) -> ToolOutput:
    """Return persisted historical setup evidence from outcome tables."""

    as_of_date = normalize_date(date)
    horizon_sessions = bounded_int(horizon, name="horizon", lower=1, upper=252)
    normalized_symbol = normalize_symbol(symbol) if symbol else None
    resolved_setup = normalize_setup_type(setup_type) if setup_type else None
    if resolved_setup is None and normalized_symbol:
        score_date = resolve_symbol_date(conn, normalized_symbol, as_of_date)
        score = get_score(conn, normalized_symbol, score_date)
        resolved_setup = (
            str(score.get("setup_type"))
            if score and score.get("setup_type")
            else None
        )
        as_of_date = score_date
    if not resolved_setup:
        raise ToolExecutionError(
            "evidence.get_setup_history requires a setup_type or a symbol "
            "with a persisted score."
        )

    row = conn.execute(
        """
        SELECT as_of_date, candidate_count, avg_forward_return,
               median_forward_return, avg_excess_return, hit_rate,
               failure_rate, avg_max_drawdown, evaluator_version,
               metric_policy_version
        FROM setup_type_performance
        WHERE setup_type = ? AND horizon_sessions = ? AND as_of_date <= ?
        ORDER BY as_of_date DESC
        LIMIT 1
        """,
        [resolved_setup, horizon_sessions, as_of_date],
    ).fetchone()
    source = "setup_type_performance"
    if row is None:
        row = conn.execute(
            """
            SELECT MAX(watchlist_date), COUNT(*), AVG(forward_return),
                   MEDIAN(forward_return), AVG(excess_return_vs_vnindex),
                   AVG(CASE WHEN hit THEN 1.0 ELSE 0.0 END),
                   AVG(CASE WHEN failure THEN 1.0 ELSE 0.0 END),
                   AVG(max_drawdown), MAX(evaluator_version),
                   MAX(metric_policy_version)
            FROM candidate_outcome
            WHERE setup_type = ? AND horizon_sessions = ?
              AND watchlist_date <= ? AND outcome_status = 'COMPLETE'
            """,
            [resolved_setup, horizon_sessions, as_of_date],
        ).fetchone()
        source = "candidate_outcome_aggregate"
        if row and not row[1]:
            row = None

    if row is None:
        caveats = [
            "No completed persisted outcome sample is available for this setup and horizon.",
            "Historical observations, when available, are descriptive and not predictive.",
        ]
        return ToolOutput(
            data={
                "status": "UNAVAILABLE",
                "setup_type": resolved_setup,
                "symbol": normalized_symbol,
                "as_of_date": as_of_date,
                "horizon_sessions": horizon_sessions,
                "sample_size": 0,
                "metrics": {},
                "methodology_version": None,
                "artifact_refs": [
                    f"setup_type_performance:{resolved_setup}:{horizon_sessions}"
                ],
                "caveats": caveats,
                "missing_data": ["completed setup outcomes"],
            },
            summary="No historical setup evidence is available.",
            warnings=caveats,
        )

    sample_size = int(row[1] or 0)
    caveats = [
        "Historical observations are descriptive and are not predictions.",
        "Outcome statistics depend on persisted evaluator and metric policy versions.",
    ]
    if sample_size < 20:
        caveats.append(
            "The persisted sample is small; interpret the aggregate with restraint."
        )
    data = {
        "status": "READY" if sample_size >= 20 else "PARTIAL",
        "setup_type": resolved_setup,
        "symbol": normalized_symbol,
        "as_of_date": str(row[0]) if row[0] is not None else as_of_date,
        "horizon_sessions": horizon_sessions,
        "sample_size": sample_size,
        "metrics": {
            "mean_forward_return": row[2],
            "median_forward_return": row[3],
            "mean_excess_return": row[4],
            "hit_rate": row[5],
            "failure_rate": row[6],
            "mean_max_drawdown": row[7],
        },
        "methodology_version": {
            "evaluator_version": row[8],
            "metric_policy_version": row[9],
            "assistant_tool_version": RESEARCH_TOOL_VERSION,
        },
        "source": source,
        "artifact_refs": [f"{source}:{resolved_setup}:{horizon_sessions}"],
        "freshness": {
            "evidence_as_of_date": str(row[0]) if row[0] is not None else None
        },
        "caveats": caveats,
        "missing_data": [],
    }
    return ToolOutput(
        data=data,
        summary=(
            f"Historical evidence for {resolved_setup} over "
            f"{horizon_sessions} sessions."
        ),
        warnings=caveats if sample_size < 20 else [],
    )


__all__ = ["get_setup_history"]
