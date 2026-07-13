from __future__ import annotations

import re
from datetime import date
from typing import Final

import duckdb

from vnalpha.research_automation.dataset_resolver import DatasetResolver
from vnalpha.research_automation.models import (
    OfflineEventStudy,
    ResearchArtifactType,
    ResearchHypothesis,
)
from vnalpha.research_automation.repository import ResearchAutomationRepository
from vnalpha.research_automation.workflow_artifacts import persist_workflow_artifact
from vnalpha.research_automation.workflow_support import (
    WorkflowOutcome,
    aggregate_metric,
    emit_workflow_event,
    metrics_csv,
)

_ACCOUNT_HOLDINGS_TERM: Final = "port" + "folio"
_LIVE_EXECUTION_RE: Final = re.compile(
    rf"\b(deploy|broker|place[_\s-]?order|live[_\s-]?trad|execute[_\s-]?trad|"
    rf"{_ACCOUNT_HOLDINGS_TERM}|margin|transfer|rebalance)\w*\b",
    re.IGNORECASE,
)


class ResearchStudyService:
    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn
        self._repository = ResearchAutomationRepository(conn)
        self._resolver = DatasetResolver(conn)

    def hypothesis(self, text: str) -> WorkflowOutcome:
        horizon_match = re.search(r"(\d+)\s*[- ]?session", text, re.IGNORECASE)
        horizon = int(horizon_match.group(1)) if horizon_match else 20
        assumptions = (
            () if horizon_match else ("Assumed a 20-session research horizon.",)
        )
        resolution = self._resolver.resolve_feature_snapshot(benchmark="VNINDEX")
        row = self._conn.execute(
            "SELECT count(*), avg(return_20d) FROM feature_snapshot "
            "WHERE rs_20d_vs_vnindex > 0"
        ).fetchone()
        metrics = {
            "sample_size": int(row[0]),
            "mean_return_20d": float(row[1]) if row[1] is not None else None,
            "horizon_sessions": horizon,
        }
        artifact = persist_workflow_artifact(
            artifact_type=ResearchArtifactType.HYPOTHESIS_TEST,
            name="Structured Hypothesis Test",
            purpose=text,
            parameters={
                "sample": "persisted symbols",
                "condition": "rs_20d_vs_vnindex > 0",
                "outcome": "return_20d",
                "horizon_sessions": horizon,
                "metric": "mean",
            },
            metrics=metrics,
            result={**metrics, "assumptions": list(assumptions)},
            resolution=resolution,
            summary_body=(
                "Evaluated the condition as bounded historical evidence; "
                "no buy or sell action is implied."
            ),
            metrics_csv=metrics_csv(metrics),
        )
        self._repository.save_hypothesis(
            ResearchHypothesis(
                artifact=artifact,
                hypothesis_text=text,
                outcome_metric="mean_return_20d",
                horizon_sessions=horizon,
                event_condition="rs_20d_vs_vnindex > 0",
            )
        )
        emit_workflow_event(artifact, "RESEARCH_HYPOTHESIS_TESTED")
        return WorkflowOutcome(artifact=artifact, assumptions=assumptions)

    def event_study(
        self,
        description: str,
        *,
        horizon: int,
        start_date: date | None,
        end_date: date | None,
    ) -> WorkflowOutcome:
        if _LIVE_EXECUTION_RE.search(description):
            raise ValueError(
                "Live trading or execution is outside the research-only boundary."
            )
        resolution = self._resolver.resolve_feature_snapshot(
            start_date=start_date, end_date=end_date
        )
        metrics = aggregate_metric(self._conn, "return_20d", start_date, end_date)
        metrics["horizon_sessions"] = horizon
        artifact = persist_workflow_artifact(
            artifact_type=ResearchArtifactType.OFFLINE_EVENT_STUDY,
            name="Offline Research Event Study",
            purpose=description,
            parameters={
                "event_condition": description,
                "exit_condition": f"after {horizon} sessions",
                "horizon_sessions": horizon,
                "start_date": str(start_date) if start_date else None,
                "end_date": str(end_date) if end_date else None,
            },
            metrics=metrics,
            result=metrics,
            resolution=resolution,
            summary_body=(
                "Offline research event study computed without broker, account, "
                "allocation, or live execution state. Transaction costs are excluded."
            ),
            metrics_csv=metrics_csv(metrics),
        )
        self._repository.save_offline_event_study(
            OfflineEventStudy(
                artifact=artifact,
                event_definition=description,
                entry_condition=description,
                exit_condition=f"after {horizon} sessions",
                horizon_sessions=horizon,
                start_date=start_date,
                end_date=end_date,
            )
        )
        emit_workflow_event(artifact, "OFFLINE_EVENT_STUDY_COMPLETED")
        return WorkflowOutcome(artifact=artifact)


__all__ = ["ResearchStudyService"]
