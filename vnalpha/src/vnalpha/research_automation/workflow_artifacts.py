from __future__ import annotations

from pathlib import Path
from typing import Any

from vnalpha.observability.context import get_correlation_id, get_run_context
from vnalpha.research_automation.artifact_writer import ResearchArtifactWriter
from vnalpha.research_automation.dataset_resolver import DatasetResolution
from vnalpha.research_automation.layout import ResearchArtifactLayout
from vnalpha.research_automation.models import (
    ResearchArtifact,
    ResearchArtifactStatus,
    ResearchArtifactType,
    new_research_artifact_id,
    now_utc,
)
from vnalpha.research_automation.validators import generate_research_caveats


def persist_workflow_artifact(
    *,
    artifact_type: ResearchArtifactType,
    name: str,
    purpose: str,
    parameters: dict[str, Any],
    metrics: dict[str, Any],
    result: dict[str, Any],
    resolution: DatasetResolution,
    summary_body: str,
    metrics_csv: str | None = None,
    candidates_csv: str | None = None,
) -> ResearchArtifact:
    artifact_id = new_research_artifact_id(_artifact_prefix(artifact_type))
    run_dir, run_id = _run_identity()
    correlation_id = _correlation_id(artifact_id)
    quality_status = dict(resolution.dataset.quality_status)
    period_coverage = 1.0 if resolution.sufficient else 0.0
    caveats = generate_research_caveats(
        sample_size=resolution.dataset.row_count,
        period_coverage=period_coverage,
        quality_status=quality_status,
        transaction_costs_included=False,
    )
    lineage = {
        "computation": "approved_deterministic_tool",
        "dataset_snapshot_id": resolution.dataset.snapshot_id,
        "source_table": resolution.dataset.dataset_name,
        "generated_code": False,
    }
    status = (
        ResearchArtifactStatus.SUCCEEDED
        if resolution.sufficient
        else ResearchArtifactStatus.REJECTED
    )
    result_payload = {
        **result,
        "sample_size": resolution.dataset.row_count,
        "period_coverage": period_coverage,
        "research_only": True,
    }
    summary = _summary(name, summary_body, caveats)
    outputs = ResearchArtifactWriter(
        ResearchArtifactLayout(run_dir=run_dir, artifact_id=artifact_id)
    ).persist_outputs(
        result=result_payload,
        summary=summary,
        lineage=lineage,
        validation={
            "schema_valid": True,
            "dataset_sufficient": resolution.sufficient,
            "sample_size": resolution.dataset.row_count,
            "period_coverage": period_coverage,
            "warnings": list(resolution.warnings),
        },
        reproducibility_manifest={
            "artifact_type": artifact_type.value,
            "parameters": parameters,
            "dataset_snapshot_id": resolution.dataset.snapshot_id,
            "deterministic_tool": True,
        },
        metrics_csv=metrics_csv,
        candidates_csv=candidates_csv,
    )
    return ResearchArtifact(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        name=name,
        purpose=purpose,
        created_at=now_utc(),
        created_by="command",
        correlation_id=correlation_id,
        status=status,
        input_datasets=(resolution.dataset,),
        sandbox_job_id=None,
        parameters=parameters,
        metrics=metrics,
        lineage=lineage,
        quality_status=quality_status,
        caveats=caveats,
        outputs=outputs,
        run_id=run_id,
    )


def _summary(name: str, body: str, caveats: tuple[str, ...]) -> str:
    caveat_lines = "\n".join(f"- {item}" for item in caveats)
    return (
        f"# {name}\n\n{body}\n\n"
        "This is a research-only result, not a trading recommendation.\n\n"
        f"## Caveats\n\n{caveat_lines}\n"
    )


def _correlation_id(artifact_id: str) -> str:
    value = get_correlation_id()
    return value if value != "unset" else f"research-{artifact_id[-16:]}"


def _run_identity() -> tuple[Path, str]:
    context = get_run_context()
    if context is not None:
        return context.run_dir, context.run_id
    run_id = "research-command"
    return Path("logs") / "runs" / run_id, run_id


def _artifact_prefix(artifact_type: ResearchArtifactType) -> str:
    return {
        ResearchArtifactType.INDICATOR_EXPERIMENT: "experiment",
        ResearchArtifactType.HYPOTHESIS_TEST: "hypothesis",
        ResearchArtifactType.PATTERN_SCAN: "pattern",
        ResearchArtifactType.OFFLINE_EVENT_STUDY: "event-study",
        ResearchArtifactType.FEATURE: "feature",
    }[artifact_type]


__all__ = ["persist_workflow_artifact"]
