from __future__ import annotations

from datetime import date

import duckdb

from vnalpha.research_automation.dataset_resolver import DatasetResolver
from vnalpha.research_automation.models import (
    PatternScan,
    ResearchArtifact,
    ResearchArtifactType,
    ResearchExperiment,
)
from vnalpha.research_automation.repository import ResearchAutomationRepository
from vnalpha.research_automation.workflow_artifacts import persist_workflow_artifact
from vnalpha.research_automation.workflow_support import (
    WorkflowOutcome,
    aggregate_metric,
    candidate_csv,
    emit_workflow_event,
    metrics_csv,
)


class ResearchWorkflowService:
    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn
        self._repository = ResearchAutomationRepository(conn)
        self._resolver = DatasetResolver(conn)

    def indicator(
        self,
        description: str,
        *,
        universe: str | None,
        start_date: date | None,
        end_date: date | None,
    ) -> WorkflowOutcome:
        if (
            "relative strength" not in description.lower()
            and "rs_" not in description.lower()
        ):
            raise ValueError("MVP indicator supports relative strength versus VNINDEX.")
        resolution = self._resolver.resolve_feature_snapshot(
            universe=universe,
            start_date=start_date,
            end_date=end_date,
            benchmark="VNINDEX",
        )
        metrics = aggregate_metric(
            self._conn, "rs_20d_vs_vnindex", start_date, end_date
        )
        artifact = persist_workflow_artifact(
            artifact_type=ResearchArtifactType.INDICATOR_EXPERIMENT,
            name="Relative Strength vs VNINDEX",
            purpose=description,
            parameters={
                "description": description,
                "universe": universe,
                "start_date": str(start_date) if start_date else None,
                "end_date": str(end_date) if end_date else None,
                "benchmark": "VNINDEX",
            },
            metrics=metrics,
            result=metrics,
            resolution=resolution,
            summary_body="Computed persisted 20-session relative strength evidence versus VNINDEX.",
            metrics_csv=metrics_csv(metrics),
        )
        self._repository.save_experiment(
            ResearchExperiment(
                artifact=artifact,
                definition=description,
                universe=universe,
                start_date=start_date,
                end_date=end_date,
            )
        )
        self._emit_experiment(artifact)
        return WorkflowOutcome(artifact=artifact)

    def pattern(
        self,
        description: str,
        *,
        universe: str | None,
        scan_date: date | None,
    ) -> WorkflowOutcome:
        supported = ("accumulation", "volatility contraction", "volume dry-up")
        if not any(item in description.lower() for item in supported):
            raise ValueError(
                "Unsupported pattern. Use accumulation base, volatility contraction, or volume dry-up."
            )
        resolution = self._resolver.resolve_feature_snapshot(
            universe=universe,
            start_date=scan_date,
            end_date=scan_date,
        )
        clauses = [
            "base_range_30d <= 0.15",
            "volatility_20d <= 0.03",
            "volume_ratio <= 0.8",
        ]
        parameters: list[object] = []
        if scan_date is not None:
            clauses.append("date = ?")
            parameters.append(scan_date)
        rows = tuple(
            self._conn.execute(
                "SELECT symbol, base_range_30d, volatility_20d, volume_ratio "
                f"FROM feature_snapshot WHERE {' AND '.join(clauses)} ORDER BY symbol",
                parameters,
            ).fetchall()
        )
        metrics = {"candidate_count": len(rows)}
        artifact = persist_workflow_artifact(
            artifact_type=ResearchArtifactType.PATTERN_SCAN,
            name="Accumulation Pattern Scan",
            purpose=description,
            parameters={
                "description": description,
                "universe": universe,
                "scan_date": str(scan_date) if scan_date else None,
            },
            metrics=metrics,
            result={
                "candidate_count": len(rows),
                "candidates": [row[0] for row in rows],
            },
            resolution=resolution,
            summary_body=f"Found {len(rows)} historical candidates using bounded accumulation, contraction, and volume thresholds.",
            candidates_csv=candidate_csv(rows),
        )
        self._repository.save_pattern_scan(
            PatternScan(
                artifact=artifact,
                pattern_description=description,
                universe=universe,
                scan_date=scan_date,
            )
        )
        emit_workflow_event(artifact, "PATTERN_SCAN_COMPLETED")
        return WorkflowOutcome(artifact=artifact, rows=rows)

    def _emit_experiment(self, artifact: ResearchArtifact) -> None:
        emit_workflow_event(artifact, "RESEARCH_EXPERIMENT_CREATED")
        event = (
            "RESEARCH_EXPERIMENT_SUCCEEDED"
            if artifact.status.value == "succeeded"
            else "RESEARCH_EXPERIMENT_FAILED"
        )
        emit_workflow_event(artifact, event)


__all__ = ["ResearchWorkflowService", "WorkflowOutcome"]
