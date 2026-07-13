from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import duckdb

from vnalpha.research_automation.events import emit_research_event
from vnalpha.research_automation.models import ResearchArtifact


@dataclass(frozen=True, slots=True)
class WorkflowOutcome:
    artifact: ResearchArtifact
    rows: tuple[tuple[Any, ...], ...] = ()
    assumptions: tuple[str, ...] = ()


def aggregate_metric(
    conn: duckdb.DuckDBPyConnection,
    column: str,
    start_date: date | None,
    end_date: date | None,
) -> dict[str, Any]:
    clauses = ["1 = 1"]
    parameters: list[object] = []
    if start_date is not None:
        clauses.append("date >= ?")
        parameters.append(start_date)
    if end_date is not None:
        clauses.append("date <= ?")
        parameters.append(end_date)
    row = conn.execute(
        f'SELECT count("{column}"), avg("{column}"), min("{column}"), '
        f'max("{column}") FROM feature_snapshot WHERE {" AND ".join(clauses)}',
        parameters,
    ).fetchone()
    return {
        "sample_size": int(row[0]),
        "mean": float(row[1]) if row[1] is not None else None,
        "minimum": float(row[2]) if row[2] is not None else None,
        "maximum": float(row[3]) if row[3] is not None else None,
    }


def metrics_csv(metrics: dict[str, Any]) -> str:
    return "metric,value\n" + "".join(
        f"{key},{value}\n" for key, value in metrics.items()
    )


def candidate_csv(rows: tuple[tuple[Any, ...], ...]) -> str:
    body = "".join(",".join(str(value) for value in row) + "\n" for row in rows)
    return "symbol,base_range_30d,volatility_20d,volume_ratio\n" + body


def emit_workflow_event(artifact: ResearchArtifact, event_type: str) -> None:
    emit_research_event(
        event_type,
        artifact_id=artifact.artifact_id,
        correlation_id=artifact.correlation_id,
        status="OK" if artifact.status.value == "succeeded" else "REJECTED",
        extra={"sandbox_job_id": artifact.sandbox_job_id},
    )


__all__ = [
    "WorkflowOutcome",
    "aggregate_metric",
    "candidate_csv",
    "emit_workflow_event",
    "metrics_csv",
]
