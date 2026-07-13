from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import duckdb

from vnalpha.observability.context import get_correlation_id, get_run_context
from vnalpha.research_automation.artifact_writer import ResearchArtifactWriter
from vnalpha.research_automation.dataset_resolver import DatasetResolver
from vnalpha.research_automation.events import emit_research_event
from vnalpha.research_automation.layout import ResearchArtifactLayout
from vnalpha.research_automation.models import (
    ResearchArtifact,
    ResearchArtifactStatus,
    ResearchArtifactType,
    ResearchFeature,
    new_research_artifact_id,
    now_utc,
)
from vnalpha.research_automation.repository import ResearchAutomationRepository
from vnalpha.research_automation.validators import generate_research_caveats

_FEATURE_DEFINITION_RE: Final = re.compile(
    r"^(?P<name>[A-Za-z][A-Za-z0-9_]*)\s*=\s*(?P<expression>.+)$"
)
_UNSAFE_EXPRESSION_RE: Final = re.compile(
    r"(?:\bfuture(?:[_\s-]|\b)|\bforward(?:[_\s-]|\b)|\bnext[_\s-]|"
    r"\blead\s*\(|\bplace[_\s-]?order\b|\bbroker\b|\bbuy[_\s-]?order\b|"
    r"\bsell[_\s-]?order\b|\bexecute[_\s-]?trade\b|\blive[_\s-]?trade\b)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class FeatureValidation:
    artifact_id: str
    schema_valid: bool
    symbol_count: int
    row_count: int
    period_start: str | None
    period_end: str | None
    missing_ratio: float
    quality_status: str
    warnings: tuple[str, ...]

    def as_payload(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "schema_valid": self.schema_valid,
            "symbol_count": self.symbol_count,
            "row_count": self.row_count,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "missing_ratio": self.missing_ratio,
            "quality_status": self.quality_status,
            "warnings": list(self.warnings),
        }


class FeatureAutomationService:
    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn
        self._repository = ResearchAutomationRepository(conn)

    def create(self, definition: str, *, universe: str | None) -> ResearchFeature:
        match = _FEATURE_DEFINITION_RE.fullmatch(definition.strip())
        if match is None:
            raise ValueError("Feature definition must use: feature_name = expression.")
        name = match.group("name")
        expression = match.group("expression").strip()
        if _UNSAFE_EXPRESSION_RE.search(expression):
            raise ValueError(
                "Feature definition references future data or trading execution."
            )

        artifact_id = new_research_artifact_id("feature")
        run_dir, run_id = _run_identity()
        active_correlation_id = get_correlation_id()
        correlation_id = (
            active_correlation_id
            if active_correlation_id != "unset"
            else f"research-{artifact_id[-16:]}"
        )
        resolution = DatasetResolver(self._conn).resolve_feature_snapshot(
            universe=universe
        )
        quality = dict(resolution.dataset.quality_status)
        caveats = generate_research_caveats(
            sample_size=resolution.dataset.row_count,
            period_coverage=1.0 if resolution.sufficient else 0.0,
            quality_status=quality,
            transaction_costs_included=False,
        )
        lineage = {
            "definition_source": "slash_command",
            "dataset_snapshot_id": resolution.dataset.snapshot_id,
            "computation": "not_executed_definition_only",
        }
        outputs = ResearchArtifactWriter(
            ResearchArtifactLayout(run_dir=run_dir, artifact_id=artifact_id)
        ).persist_outputs(
            result={"feature_name": name.upper(), "status": "created"},
            summary=(
                f"# Feature {name.upper()}\n\nDefinition persisted for research-only use. "
                "No generated code was executed.\n"
            ),
            lineage=lineage,
            validation={"schema_valid": True, "execution_started": False},
            reproducibility_manifest={
                "feature_expression": expression,
                "dataset_snapshot_id": resolution.dataset.snapshot_id,
                "universe": universe,
            },
        )
        artifact = ResearchArtifact(
            artifact_id=artifact_id,
            artifact_type=ResearchArtifactType.FEATURE,
            name=name.upper(),
            purpose="Persist a reproducible research feature definition.",
            created_at=now_utc(),
            created_by="command",
            correlation_id=correlation_id,
            status=ResearchArtifactStatus.CREATED,
            input_datasets=(resolution.dataset,),
            sandbox_job_id=None,
            parameters={"expression": expression, "universe": universe},
            metrics={},
            lineage=lineage,
            quality_status=quality,
            caveats=caveats,
            outputs=outputs,
            run_id=run_id,
            related_feature_id=artifact_id,
        )
        feature = ResearchFeature(
            artifact=artifact,
            feature_name=name,
            feature_expression=expression,
            universe=universe,
        )
        self._repository.save_feature(feature)
        emit_research_event(
            "RESEARCH_ARTIFACT_CREATED",
            artifact_id=artifact_id,
            correlation_id=correlation_id,
            extra={"artifact_type": "feature"},
        )
        emit_research_event(
            "RESEARCH_FEATURE_CREATED",
            artifact_id=artifact_id,
            correlation_id=correlation_id,
        )
        return feature

    def validate(self, identifier: str) -> FeatureValidation:
        row = self._conn.execute(
            "SELECT f.artifact_id, f.feature_expression, a.validation_path, "
            "a.correlation_id FROM research_feature f JOIN research_artifact a "
            "USING (artifact_id) WHERE f.artifact_id = ? OR upper(f.feature_name) = upper(?) "
            "ORDER BY f.created_at_ts DESC LIMIT 1",
            [identifier, identifier],
        ).fetchone()
        if row is None:
            raise ValueError(f"Research feature {identifier!r} was not found.")
        expression = str(row[1])
        column = (
            expression if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", expression) else None
        )
        columns = {
            item[1]
            for item in self._conn.execute(
                "PRAGMA table_info('feature_snapshot')"
            ).fetchall()
        }
        schema_valid = column in columns if column else False
        missing_count = 0
        if schema_valid and column is not None:
            missing_count = int(
                self._conn.execute(
                    f'SELECT count(*) FROM feature_snapshot WHERE "{column}" IS NULL'
                ).fetchone()[0]
            )
        resolution = DatasetResolver(self._conn).resolve_feature_snapshot()
        row_count = resolution.dataset.row_count or 0
        missing_ratio = missing_count / row_count if row_count else 1.0
        warnings = [*resolution.warnings]
        if not schema_valid:
            warnings.append(
                "Feature expression is not a persisted feature_snapshot column."
            )
        if missing_ratio > 0.1:
            warnings.append(f"Feature missing ratio is {missing_ratio:.1%}.")
        quality_status = (
            "good"
            if schema_valid and resolution.sufficient and missing_ratio <= 0.1
            else "warning"
        )
        payload = FeatureValidation(
            artifact_id=str(row[0]),
            schema_valid=schema_valid,
            symbol_count=len(resolution.dataset.symbols),
            row_count=row_count,
            period_start=str(resolution.dataset.start_date)
            if resolution.dataset.start_date
            else None,
            period_end=str(resolution.dataset.end_date)
            if resolution.dataset.end_date
            else None,
            missing_ratio=missing_ratio,
            quality_status=quality_status,
            warnings=tuple(warnings),
        )
        Path(str(row[2])).write_text(
            json.dumps(payload.as_payload(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        status = (
            ResearchArtifactStatus.VALIDATED
            if schema_valid and resolution.sufficient
            else ResearchArtifactStatus.REJECTED
        )
        self._repository.mark_status(str(row[0]), status)
        emit_research_event(
            "RESEARCH_FEATURE_VALIDATED",
            artifact_id=str(row[0]),
            correlation_id=str(row[3]),
            status="OK" if status is ResearchArtifactStatus.VALIDATED else "REJECTED",
            extra={"quality_status": quality_status},
        )
        return payload


def _run_identity() -> tuple[Path, str]:
    context = get_run_context()
    if context is not None:
        return context.run_dir, context.run_id
    run_id = "research-command"
    return Path("logs") / "runs" / run_id, run_id


__all__ = ["FeatureAutomationService", "FeatureValidation"]
