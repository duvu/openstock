from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from vnalpha.model_routing.config import ModelRoutingConfig
from vnalpha.model_routing.models import ModelProfile

_REASONING_TASKS: Final[frozenset[str]] = frozenset(
    {
        "multi_symbol_comparison",
        "deep_symbol_analysis",
        "shortlist_generation",
        "research_scenario",
        "error_diagnosis",
    }
)
_SMALL_TASKS: Final[frozenset[str]] = frozenset(
    {"intent_classification", "title_generation"}
)


def _normalized(value: str | None) -> str:
    return (value or "").strip().lower().replace("-", "_")


def profile_for(
    *,
    stage: str,
    explicit_profile: ModelProfile | None = None,
    task_type: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    config: ModelRoutingConfig | None = None,
) -> ModelProfile:
    if explicit_profile is not None:
        return explicit_profile
    return default_profile_for_stage(
        stage,
        task_type=task_type,
        metadata=metadata,
        config=config,
    )


def default_profile_for_stage(
    stage: str,
    *,
    task_type: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    config: ModelRoutingConfig | None = None,
) -> ModelProfile:
    normalized_stage = _normalized(stage)
    normalized_task = _normalized(task_type)
    route_metadata = dict(metadata or {})

    if route_metadata.get("requires_deep_reasoning") is True:
        return ModelProfile.REASONING
    if normalized_task in _SMALL_TASKS:
        return ModelProfile.SMALL
    if normalized_task in _REASONING_TASKS:
        return ModelProfile.REASONING
    if normalized_stage in {"classify", "title"}:
        return ModelProfile.SMALL
    if normalized_stage == "diagnose":
        return ModelProfile.REASONING
    if normalized_stage == "compact" or normalized_task == "workspace_compaction":
        if config is not None and config.is_explicitly_configured(
            ModelProfile.LONG_CONTEXT
        ):
            return ModelProfile.LONG_CONTEXT
        return ModelProfile.REASONING
    if normalized_task == "watchlist_summary":
        symbol_count = int(route_metadata.get("symbol_count", 0) or 0)
        artifact_count = int(route_metadata.get("artifact_count", 0) or 0)
        context_bytes = int(route_metadata.get("context_bytes", 0) or 0)
        if symbol_count > 10 or artifact_count > 20 or context_bytes > 24_000:
            return ModelProfile.REASONING
        return ModelProfile.DEFAULT
    if normalized_stage == "plan":
        return ModelProfile.REASONING
    return ModelProfile.DEFAULT
