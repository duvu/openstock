from __future__ import annotations

import re
from dataclasses import replace
from datetime import date
from statistics import fmean
from typing import Final

import duckdb

from vnalpha.features.status import (
    FEATURE_STATUS_CONTRACT_VERSION,
    FeatureDataStatus,
    feature_exclusion_reason_sql,
)
from vnalpha.outcomes.models import (
    FORWARD_OUTCOME_MEASUREMENT_CONTRACT_VERSION,
    OutcomeStatus,
)
from vnalpha.outcomes.repositories import summarize_hypothesis_outcomes
from vnalpha.research_automation.dataset_resolver import DatasetResolver
from vnalpha.research_automation.event_study_spec import parse_event_study_spec
from vnalpha.research_automation.models import (
    OfflineEventStudy,
    ResearchArtifactType,
    ResearchHypothesis,
)
from vnalpha.research_automation.repository import ResearchAutomationRepository
from vnalpha.research_automation.workflow_artifacts import persist_workflow_artifact
from vnalpha.research_automation.workflow_support import (
    WorkflowOutcome,
    emit_workflow_event,
    metrics_csv,
)

_ACCOUNT_HOLDINGS_TERM: Final = "port" + "folio"
_LIVE_EXECUTION_RE: Final = re.compile(
    rf"\b(deploy|broker|place[_\s-]?order|live[_\s-]?trad|execute[_\s-]?trad|"
    rf"{_ACCOUNT_HOLDINGS_TERM}|margin|transfer|rebalance)\w*\b",
    re.IGNORECASE,
)
_MIN_EVENT_OBSERVATIONS: Final = 2
_MAX_RECORDED_OBSERVATIONS: Final = 5_000


class ResearchStudyService:
    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn
        self._repository = ResearchAutomationRepository(conn)
        self._resolver = DatasetResolver(conn)

    def hypothesis(self, text: str) -> WorkflowOutcome:
        horizon_match = re.search(r"(\d+)\s*[- ]?session", text, re.IGNORECASE)
        horizon = int(horizon_match.group(1)) if horizon_match else 20
        if horizon != 20:
            raise ValueError(
                "The current hypothesis workflow supports only the verified "
                "20-session outcome. Use /experiment event-study for another horizon."
            )
        assumptions = (
            () if horizon_match else ("Assumed a 20-session research horizon.",)
        )
        resolution = self._resolver.resolve_feature_snapshot(benchmark="VNINDEX")
        observation_summary = summarize_hypothesis_outcomes(
            self._conn,
            horizon_sessions=horizon,
        )
        measurement_warnings: list[str] = []
        if observation_summary.missing_observation_rows:
            measurement_warnings.append(
                f"{observation_summary.missing_observation_rows} eligible feature rows "
                "have no complete later observation."
            )
        if observation_summary.complete_observation_rows < _MIN_EVENT_OBSERVATIONS:
            measurement_warnings.append(
                f"At least {_MIN_EVENT_OBSERVATIONS} complete later observations are required."
            )
        measurement_complete = (
            observation_summary.complete_observation_rows >= _MIN_EVENT_OBSERVATIONS
            and observation_summary.missing_observation_rows == 0
            and observation_summary.excluded_feature_rows == 0
        )
        successful = (
            resolution.sufficient and not resolution.warnings and measurement_complete
        )
        effective_warnings = tuple(
            dict.fromkeys((*resolution.warnings, *measurement_warnings))
        )
        quality_status = dict(resolution.dataset.quality_status)
        if effective_warnings:
            quality_status["status"] = "warning"
            quality_status["warnings"] = effective_warnings
        effective_resolution = replace(
            resolution,
            dataset=replace(resolution.dataset, quality_status=quality_status),
            sufficient=successful,
            warnings=effective_warnings,
        )
        measurement_status = (
            OutcomeStatus.COMPLETE.value
            if successful
            else (
                OutcomeStatus.PARTIAL.value
                if observation_summary.complete_observation_rows
                else OutcomeStatus.MISSING_DATA.value
            )
        )
        metrics = {
            "sample_size": observation_summary.complete_observation_rows,
            "selected_feature_rows": observation_summary.selected_feature_rows,
            "eligible_feature_rows": observation_summary.eligible_feature_rows,
            "excluded_feature_rows": observation_summary.excluded_feature_rows,
            "missing_observation_rows": observation_summary.missing_observation_rows,
            "mean_return_20d": observation_summary.mean_forward_return,
            "horizon_sessions": horizon,
        }
        artifact = persist_workflow_artifact(
            artifact_type=ResearchArtifactType.HYPOTHESIS_TEST,
            name="Structured Hypothesis Test",
            purpose=text,
            parameters={
                "sample": "persisted symbols",
                "condition": "rs_20d_vs_vnindex > 0",
                "outcome": "candidate_outcome.forward_return",
                "horizon_sessions": horizon,
                "metric": "mean",
            },
            metrics=metrics,
            result={**metrics, "assumptions": list(assumptions)},
            resolution=effective_resolution,
            summary_body=(
                "Evaluated the condition as bounded historical evidence; "
                "no buy or sell action is implied."
            ),
            metrics_csv=metrics_csv(metrics),
            lineage_extra={
                "feature_status_contract_version": FEATURE_STATUS_CONTRACT_VERSION,
                "measurement_contract_version": (
                    FORWARD_OUTCOME_MEASUREMENT_CONTRACT_VERSION
                ),
                "measurement_source": "candidate_outcome.forward_return",
                "measurement_status": measurement_status,
                "measurement_horizon_sessions": horizon,
                "measurement_join_keys": [
                    "symbol",
                    "watchlist_date",
                    "horizon_sessions",
                ],
            },
            validation_extra={
                "eligible_feature_rows": observation_summary.eligible_feature_rows,
                "excluded_feature_rows": observation_summary.excluded_feature_rows,
                "complete_observation_rows": (
                    observation_summary.complete_observation_rows
                ),
                "missing_observation_rows": (
                    observation_summary.missing_observation_rows
                ),
            },
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
        spec = parse_event_study_spec(description, horizon)
        resolution = self._resolver.resolve_feature_snapshot(
            start_date=start_date, end_date=end_date
        )
        predicate, predicate_params = spec.sql_predicate("f")
        observations = self._load_event_observations(
            predicate,
            predicate_params,
            horizon=horizon,
            start_date=start_date,
            end_date=end_date,
        )
        condition_matches = len(observations)
        included = [row for row in observations if row[7] == "included"]
        excluded = [row for row in observations if row[7] != "included"]
        returns = [float(row[6]) for row in included]

        rejection_reasons: list[str] = []
        if not resolution.sufficient:
            rejection_reasons.append("dataset coverage is insufficient")
        if resolution.warnings:
            rejection_reasons.extend(resolution.warnings)
        if condition_matches == 0:
            rejection_reasons.append("the executed condition selected no observations")
        if excluded:
            rejection_reasons.append(
                f"{len(excluded)} selected observations lacked trustworthy inputs or outcomes"
            )
        if len(included) < _MIN_EVENT_OBSERVATIONS:
            rejection_reasons.append(
                f"at least {_MIN_EVENT_OBSERVATIONS} complete observations are required"
            )

        successful = not rejection_reasons
        effective_resolution = (
            resolution
            if successful
            else replace(
                resolution,
                sufficient=False,
                warnings=tuple(
                    dict.fromkeys((*resolution.warnings, *rejection_reasons))
                ),
            )
        )
        metrics = {
            "sample_size": len(included),
            "condition_matches": condition_matches,
            "included_observations": len(included),
            "excluded_observations": len(excluded),
            "mean_forward_return": fmean(returns) if returns else None,
            "minimum_forward_return": min(returns) if returns else None,
            "maximum_forward_return": max(returns) if returns else None,
            "horizon_sessions": horizon,
        }
        executed_filters = {
            "condition": spec.canonical_condition,
            "start_date": str(start_date) if start_date else None,
            "end_date": str(end_date) if end_date else None,
            "feature_quality": FeatureDataStatus.EXACT_DATE.value,
            "feature_status_contract_version": FEATURE_STATUS_CONTRACT_VERSION,
            "feature_observable_at_event": True,
            "canonical_interval": "1D",
            "canonical_quality": "good|ok|pass",
            "unresolved_quarantine": False,
        }
        result = {
            **metrics,
            "specification": spec.payload(),
            "specification_hash": spec.specification_hash,
            "executed_filters": executed_filters,
            "observations": [
                {
                    "symbol": row[0],
                    "entry_date": str(row[1]),
                    "observable_feature_date": str(row[2]) if row[2] else None,
                    "entry_close": row[3],
                    "outcome_date": str(row[4]) if row[4] else None,
                    "outcome_close": row[5],
                    "forward_return": row[6],
                    "status": row[7],
                }
                for row in observations[:_MAX_RECORDED_OBSERVATIONS]
            ],
            "rejection_reasons": rejection_reasons,
        }
        artifact = persist_workflow_artifact(
            artifact_type=ResearchArtifactType.OFFLINE_EVENT_STUDY,
            name="Offline Research Event Study",
            purpose=description,
            parameters={
                "event_condition": spec.canonical_condition,
                "exit_condition": f"after {horizon} trading sessions",
                "horizon_sessions": horizon,
                "start_date": str(start_date) if start_date else None,
                "end_date": str(end_date) if end_date else None,
                "specification_hash": spec.specification_hash,
            },
            metrics=metrics,
            result=result,
            resolution=effective_resolution,
            summary_body=(
                "Executed a deterministic condition against observable feature rows and "
                "calculated the requested forward close return from canonical OHLCV. "
                "No broker, account, allocation, or live execution state was used."
            ),
            metrics_csv=metrics_csv(metrics),
            lineage_extra={
                "specification_hash": spec.specification_hash,
                "specification_version": spec.spec_version,
                "executed_filters": executed_filters,
                "outcome_definition": (
                    f"close at entry plus {horizon} trading sessions / entry close - 1"
                ),
                "price_basis": spec.price_basis,
                "metric_policy_version": spec.metric_policy_version,
                "feature_status_contract_version": FEATURE_STATUS_CONTRACT_VERSION,
                "future_feature_selection": False,
            },
            validation_extra={
                "condition_matches": condition_matches,
                "included_observations": len(included),
                "excluded_observations": len(excluded),
                "rejection_reasons": rejection_reasons,
                "all_selected_rows_observable": not excluded,
            },
            reproducibility_extra={
                "specification": spec.payload(),
                "specification_hash": spec.specification_hash,
                "executed_filters": executed_filters,
            },
        )
        self._repository.save_offline_event_study(
            OfflineEventStudy(
                artifact=artifact,
                event_definition=spec.canonical_condition,
                entry_condition=spec.canonical_condition,
                exit_condition=f"after {horizon} trading sessions",
                horizon_sessions=horizon,
                start_date=start_date,
                end_date=end_date,
            )
        )
        emit_workflow_event(artifact, "OFFLINE_EVENT_STUDY_COMPLETED")
        return WorkflowOutcome(
            artifact=artifact,
            rows=tuple(
                (
                    row[0],
                    row[1],
                    row[4],
                    row[6],
                    row[7],
                )
                for row in observations
            ),
        )

    def _load_event_observations(
        self,
        predicate: str,
        predicate_params: list[float],
        *,
        horizon: int,
        start_date: date | None,
        end_date: date | None,
    ) -> list[tuple]:
        clauses = [predicate]
        parameters: list[object] = list(predicate_params)
        if start_date is not None:
            clauses.append("f.date >= ?")
            parameters.append(start_date)
        if end_date is not None:
            clauses.append("f.date <= ?")
            parameters.append(end_date)
        where = " AND ".join(clauses)
        feature_exclusion_sql = feature_exclusion_reason_sql("source")
        return self._conn.execute(
            f"""
            WITH feature_rows AS (
                SELECT
                    source.*,
                    {feature_exclusion_sql} AS feature_exclusion_reason
                FROM feature_snapshot source
            ),
            price_path AS (
                SELECT
                    symbol,
                    CAST(time AS DATE) AS price_date,
                    close AS entry_close,
                    LEAD(close, {horizon}) OVER (
                        PARTITION BY symbol ORDER BY time
                    ) AS outcome_close,
                    LEAD(CAST(time AS DATE), {horizon}) OVER (
                        PARTITION BY symbol ORDER BY time
                    ) AS outcome_date
                FROM canonical_ohlcv
                WHERE interval = '1D'
                  AND lower(trim(coalesce(quality_status, ''))) IN ('good', 'ok', 'pass')
            ),
            unresolved_quarantine AS (
                SELECT DISTINCT symbol, CAST(time AS DATE) AS quarantine_date
                FROM ohlcv_quarantine
                WHERE interval = '1D' AND resolution_ref IS NULL
            )
            SELECT
                f.symbol,
                f.date,
                f.as_of_bar_date,
                p.entry_close,
                p.outcome_date,
                p.outcome_close,
                CASE
                    WHEN p.entry_close IS NULL OR p.entry_close = 0
                         OR p.outcome_close IS NULL
                         OR NOT isfinite(p.entry_close)
                         OR NOT isfinite(p.outcome_close)
                    THEN NULL
                    ELSE p.outcome_close / p.entry_close - 1
                END AS forward_return,
                CASE
                    WHEN f.feature_exclusion_reason IS NOT NULL
                    THEN f.feature_exclusion_reason
                    WHEN f.as_of_bar_date IS NULL OR f.as_of_bar_date > f.date
                    THEN 'non_observable_feature'
                    WHEN f.benchmark_as_of_bar_date IS NULL OR f.benchmark_as_of_bar_date > f.date
                    THEN 'non_observable_benchmark'
                    WHEN q.symbol IS NOT NULL
                    THEN 'unresolved_quarantine'
                    WHEN p.entry_close IS NULL OR p.entry_close = 0
                         OR NOT isfinite(p.entry_close)
                    THEN 'missing_entry_price'
                    WHEN p.outcome_close IS NULL OR p.outcome_date IS NULL
                         OR NOT isfinite(p.outcome_close)
                    THEN 'missing_outcome'
                    ELSE 'included'
                END AS observation_status
            FROM feature_rows f
            LEFT JOIN price_path p
              ON p.symbol = f.symbol AND p.price_date = f.date
            LEFT JOIN unresolved_quarantine q
              ON q.symbol = f.symbol AND q.quarantine_date = f.date
            WHERE {where}
            ORDER BY f.date, f.symbol
            """,
            parameters,
        ).fetchall()


__all__ = ["ResearchStudyService"]
