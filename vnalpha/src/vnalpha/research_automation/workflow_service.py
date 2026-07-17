from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any, Mapping

import duckdb

from vnalpha.clients.vnstock.client import VnstockClient
from vnalpha.research_automation.dataset_resolver import (
    DatasetRef,
    DatasetResolution,
    DatasetResolver,
)
from vnalpha.research_automation.models import (
    DatasetExtensionExperiment,
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

    def dataset_extension(
        self,
        provider_name: str,
        dataset_name: str,
        extension_name: str,
        consumer_name: str,
    ) -> WorkflowOutcome:
        provider = provider_name.strip().upper()
        dataset = dataset_name.strip().lower()
        extension = extension_name.strip().lower()
        consumer = _normalized_text(consumer_name)

        if not provider or not dataset or not extension:
            raise ValueError(
                "provider_name, dataset_name, and extension_name are required."
            )
        if not consumer:
            raise ValueError("consumer_name is required.")

        capability_status, capability_payload, warnings = _resolve_extension_capability(
            provider, dataset, extension
        )
        dataset_version, entitlement, missingness, transformation = (
            _extract_extension_metadata(capability_payload)
        )
        experiment_hash = _experiment_hash(
            provider=provider,
            dataset=dataset,
            extension=extension,
            consumer=consumer,
            capability_status=capability_status,
            capability_payload=capability_payload,
            dataset_version=dataset_version,
            entitlement=entitlement,
            missingness=missingness,
            transformation=transformation,
        )
        resolution = _make_extension_resolution(provider, dataset, extension, warnings)

        artifact = persist_workflow_artifact(
            artifact_type=ResearchArtifactType.DATASET_EXTENSION_EXPERIMENT,
            name="Dataset Extension Experiment",
            purpose=f"{provider} capability for {dataset}:{extension}",
            parameters={
                "provider": provider,
                "dataset": dataset,
                "extension": extension,
                "consumer": consumer,
            },
            metrics={
                "provider": provider,
                "dataset": dataset,
                "extension": extension,
                "consumer": consumer,
                "dataset_version": dataset_version,
                "capability_status": capability_status,
                "supported": capability_status == "supported",
                "warning_count": len(warnings),
                "experiment_hash": experiment_hash,
            },
            result={
                "provider": provider,
                "dataset": dataset,
                "extension": extension,
                "consumer": consumer,
                "capability_status": capability_status,
                "capability_payload": dict(capability_payload),
            },
            resolution=resolution,
            summary_body=(
                "Recorded the provider capability status for one dataset extension check."
            ),
            metrics_csv=metrics_csv(
                {
                    "provider": provider,
                    "dataset": dataset,
                    "extension": extension,
                    "capability_status": capability_status,
                }
            ),
            lineage_extra={
                "query_target": f"{provider}:{dataset}:{extension}",
                "capability_status": capability_status,
                "capability_payload": dict(capability_payload),
                "consumer": consumer,
                "dataset_version": dataset_version,
            },
        )
        self._repository.save_dataset_extension(
            DatasetExtensionExperiment(
                artifact=artifact,
                definition=f"{provider} capability for {dataset}:{extension}",
                provider_name=provider,
                dataset_name=dataset,
                extension_name=extension,
                consumer_name=consumer,
                dataset_version=dataset_version,
                entitlement=entitlement,
                missingness=missingness,
                transformation=transformation,
                experiment_hash=experiment_hash,
                capability_status=capability_status,
                capability_payload=capability_payload,
            )
        )
        self._emit_experiment(artifact)
        return WorkflowOutcome(artifact=artifact)

    def _emit_experiment(self, artifact: ResearchArtifact) -> None:
        emit_workflow_event(artifact, "RESEARCH_EXPERIMENT_CREATED")
        event = (
            "RESEARCH_EXPERIMENT_SUCCEEDED"
            if artifact.status.value == "succeeded"
            else "RESEARCH_EXPERIMENT_FAILED"
        )
        emit_workflow_event(artifact, event)


def _resolve_extension_capability(
    provider: str,
    dataset: str,
    extension: str,
) -> tuple[str, Mapping[str, Any], tuple[str, ...]]:
    try:
        with VnstockClient() as client:
            raw_capabilities = client.get_provider_capabilities()
    except Exception as exc:
        raise ValueError("Unable to query provider capabilities.") from exc

    providers = _coerce_mapping(raw_capabilities.get("capabilities", {}))
    provider_payload = _select_mapping_case_insensitive(providers, provider)
    if not provider_payload:
        raise ValueError(f"Provider {provider!r} exposes no advertised capabilities.")

    dataset_payload = _select_mapping_case_insensitive(provider_payload, dataset)
    if not dataset_payload:
        raise ValueError(
            f"Dataset {dataset!r} is not exposed by provider {provider!r} in capability data."
        )

    extension_payload = _select_extension_payload(
        provider_payload,
        dataset,
        extension,
        dataset_payload,
    )
    if extension_payload:
        status = _coerce_capability_status(extension_payload)
        warnings: tuple[str, ...] = ()
        if status != "supported":
            warnings = f"{provider}/{dataset}:{extension} is exposed as unsupported for this endpoint."
        return status, extension_payload, warnings

    return (
        "unsupported",
        {},
        (
            f"{provider}/{dataset}:{extension} is not documented as a supported extension.",
        ),
    )


def _coerce_capability_status(payload: Mapping[str, Any]) -> str:
    status_value = payload.get("status")
    if isinstance(status_value, str):
        normalized = status_value.strip().lower()
        if normalized in {"supported", "unsupported"}:
            return normalized
        return "unsupported"
    supported = payload.get("supported")
    if isinstance(supported, bool):
        return "supported" if supported else "unsupported"
    unsupported = payload.get("unsupported")
    if isinstance(unsupported, bool):
        return "unsupported" if unsupported else "supported"
    return "supported"


def _make_extension_resolution(
    provider: str,
    dataset: str,
    extension: str,
    warnings: tuple[str, ...],
) -> DatasetResolution:
    status_warning = "good" if not warnings else "warning"
    all_warnings: list[str] = list(warnings)
    if warnings:
        all_warnings.append(
            f"{provider}/{dataset}:{extension} has unsupported capability status."
        )
    quality_status = {
        "status": status_warning,
        "provider": provider,
        "dataset": dataset,
        "extension": extension,
        "warnings": tuple(all_warnings),
    }
    return DatasetResolution(
        dataset=DatasetRef(
            dataset_name=dataset,
            snapshot_id=f"{provider.lower()}-{dataset}-{extension}-capability",
            symbols=(),
            interval="1D",
            row_count=1 if len(warnings) == 0 else 0,
            quality_status=quality_status,
        ),
        sufficient=len(warnings) == 0,
        warnings=tuple(all_warnings),
    )


def _select_mapping_case_insensitive(
    mapping: Mapping[str, Any], key: str
) -> Mapping[str, Any]:
    direct = mapping.get(key)
    if isinstance(direct, Mapping):
        return direct
    lowered_key = str(key).lower()
    for candidate_key, candidate_value in mapping.items():
        if str(candidate_key).lower() == lowered_key and isinstance(
            candidate_value, Mapping
        ):
            return candidate_value
    return {}


def _select_extension_payload(
    provider_payload: Mapping[str, Any],
    dataset: str,
    extension: str,
    dataset_payload: Mapping[str, Any],
) -> Mapping[str, Any]:
    extension_block = dataset_payload.get("extensions")
    if isinstance(extension_block, Mapping):
        selected = _select_mapping_case_insensitive(extension_block, extension)
        if selected:
            return selected

    selected = _select_mapping_case_insensitive(dataset_payload, extension)
    if selected:
        return selected

    for separator in (".", ":", "/", "_"):
        selected = _select_mapping_case_insensitive(
            provider_payload, f"{dataset}{separator}{extension}"
        )
        if selected:
            return selected

    return {}


def _coerce_mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _extract_extension_metadata(
    payload: Mapping[str, Any],
) -> tuple[str | None, Mapping[str, Any], Mapping[str, Any], str | None]:
    dataset_version = _normalize_optional_value(
        payload.get("dataset_version"),
        payload.get("version"),
    )
    transformation = _normalize_optional_value(payload.get("transformation"))
    entitlement = _coerce_mapping(payload.get("entitlement"))
    missingness = _coerce_mapping(payload.get("missingness"))
    if not missingness and (alt := payload.get("missing")) and isinstance(alt, Mapping):
        missingness = alt
    return dataset_version, entitlement, missingness, transformation


def _normalize_optional_value(value: Any, fallback: Any = None) -> str | None:
    selected = value if value is not None else fallback
    if selected is None:
        return None
    normalized = str(selected).strip()
    return normalized or None


def _experiment_hash(
    *,
    provider: str,
    dataset: str,
    extension: str,
    consumer: str,
    capability_status: str,
    capability_payload: Mapping[str, Any],
    dataset_version: str | None,
    entitlement: Mapping[str, Any],
    missingness: Mapping[str, Any],
    transformation: str | None,
) -> str:
    payload = {
        "provider": provider,
        "dataset": dataset,
        "extension": extension,
        "consumer": consumer,
        "capability_status": capability_status,
        "capability_payload": dict(capability_payload),
        "dataset_version": dataset_version,
        "entitlement": dict(entitlement),
        "missingness": dict(missingness),
        "transformation": transformation,
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _normalized_text(value: object) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    return normalized


__all__ = ["ResearchWorkflowService", "WorkflowOutcome"]
