from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ModelProfile(str, Enum):
    SMALL = "small"
    DEFAULT = "default"
    REASONING = "reasoning"
    LONG_CONTEXT = "long_context"

    @classmethod
    def parse(cls, value: str | ModelProfile) -> ModelProfile:
        if isinstance(value, cls):
            return value
        normalized = str(value).strip().lower().replace("-", "_")
        try:
            return cls(normalized)
        except ValueError as exc:
            allowed = ", ".join(profile.value for profile in cls)
            raise ValueError(
                f"Unknown model profile '{value}'. Expected one of: {allowed}."
            ) from exc


class ModelCapability(str, Enum):
    JSON_SCHEMA = "json_schema"

    @classmethod
    def parse(cls, value: str | ModelCapability) -> ModelCapability:
        if isinstance(value, cls):
            return value
        normalized = str(value).strip().lower().replace("-", "_")
        try:
            return cls(normalized)
        except ValueError as exc:
            allowed = ", ".join(capability.value for capability in cls)
            raise ValueError(
                f"Unknown model capability '{value}'. Expected one of: {allowed}."
            ) from exc


class ModelRouteStage(str, Enum):
    CLASSIFY = "classify"
    PLAN = "plan"
    SYNTHESIZE = "synthesize"
    COMPACT = "compact"
    TITLE = "title"
    DIAGNOSE = "diagnose"
    GENERIC = "generic"


class ModelTaskType(str, Enum):
    INTENT_CLASSIFICATION = "intent_classification"
    NORMAL_ANSWER = "normal_answer"
    SIMPLE_SUMMARY = "simple_summary"
    WATCHLIST_SUMMARY = "watchlist_summary"
    MULTI_SYMBOL_COMPARISON = "multi_symbol_comparison"
    DEEP_SYMBOL_ANALYSIS = "deep_symbol_analysis"
    SHORTLIST_GENERATION = "shortlist_generation"
    RESEARCH_SCENARIO = "research_scenario"
    WORKSPACE_COMPACTION = "workspace_compaction"
    ERROR_DIAGNOSIS = "error_diagnosis"
    TITLE_GENERATION = "title_generation"


@dataclass(frozen=True, slots=True)
class ModelRouteDecision:
    profile: ModelProfile
    model_id: str
    stage: str
    task_type: str | None
    route_reason: str
    provider: str | None = None
    override_source: str | None = None
    fallback_chain: tuple[ModelProfile, ...] = ()
    capabilities: tuple[ModelCapability, ...] = ()

    def supports(self, capability: ModelCapability | str) -> bool:
        return ModelCapability.parse(capability) in self.capabilities

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile.value,
            "model_id": self.model_id,
            "provider": self.provider,
            "stage": self.stage,
            "task_type": self.task_type,
            "route_reason": self.route_reason,
            "override_source": self.override_source,
            "fallback_chain": [profile.value for profile in self.fallback_chain],
            "capabilities": [capability.value for capability in self.capabilities],
        }
