from __future__ import annotations

from vnalpha.commands.errors import CommandValidationError
from vnalpha.commands.handlers.research_automation_common import workflow_warnings
from vnalpha.commands.models import CommandResult, ParsedCommand, ResultPanel
from vnalpha.research_automation.study_service import ResearchStudyService


def handle_hypothesis(parsed: ParsedCommand, conn=None, **_kwargs) -> CommandResult:
    if conn is None:
        return CommandResult(
            status="FAILED", title="/hypothesis", summary="No database connection."
        )
    if not parsed.positional or parsed.positional[0].lower() != "test":
        raise CommandValidationError(
            "Unsupported /hypothesis subcommand. Supported: test."
        )
    if parsed.options or parsed.filters:
        raise CommandValidationError("/hypothesis test accepts hypothesis text only.")
    text = " ".join(parsed.positional[1:]).strip()
    if not text:
        raise CommandValidationError("/hypothesis test requires hypothesis text.")
    outcome = ResearchStudyService(conn).hypothesis(text)
    artifact = outcome.artifact
    return CommandResult(
        status="SUCCESS" if artifact.status.value == "succeeded" else "PARTIAL",
        title="/hypothesis test",
        summary="Hypothesis evaluated as historical evidence, not a recommendation.",
        panels=[
            ResultPanel(
                title="Plan Preview",
                content={
                    "dataset_refs": [
                        item.snapshot_id for item in artifact.input_datasets
                    ],
                    "computation": "approved deterministic tool",
                    "expected_artifacts": [
                        "manifest.json",
                        "result.json",
                        "summary.md",
                        "metrics.csv",
                        "lineage.json",
                        "validation.json",
                    ],
                    "assumptions": list(outcome.assumptions),
                    "caveats": list(artifact.caveats),
                },
            ),
            ResultPanel(
                title="Hypothesis Evidence",
                content={
                    "artifact_id": artifact.artifact_id,
                    "metrics": dict(artifact.metrics),
                    "research_only": True,
                },
            ),
        ],
        warnings=workflow_warnings(artifact),
    )


__all__ = ["handle_hypothesis"]
