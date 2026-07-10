from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, TypedDict

from vnalpha.model_routing.models import ModelProfile, ModelRouteDecision


class RouteMetadata(TypedDict, total=False):
    request_id: str
    session_id: str
    workspace_id: str
    surface: str
    symbol_count: int
    artifact_count: int
    context_bytes: int
    requires_deep_reasoning: bool
    latency_ms: float
    tokens_in: int
    tokens_out: int
    estimated_cost: float
    error_type: str
    fallback_from: str
    fallback_to: str
    scope: str
    profile: str


@dataclass(frozen=True, slots=True)
class ModelRouteEvent:
    profile: str
    model_id: str
    provider: str | None
    stage: str
    task_type: str | None
    route_reason: str
    override_source: str | None
    fallback_chain: tuple[str, ...]
    metadata: Mapping[str, Any]


_ALLOWED_METADATA_KEYS = frozenset(RouteMetadata.__annotations__)


def redact_route_metadata(metadata: Mapping[str, Any]) -> RouteMetadata:
    redacted: RouteMetadata = {}
    for key in _ALLOWED_METADATA_KEYS:
        value = metadata.get(key)
        if value is not None:
            redacted[key] = value  # type: ignore[literal-required]
    return redacted


def route_event(
    decision: ModelRouteDecision,
    metadata: RouteMetadata | None = None,
) -> ModelRouteEvent:
    return ModelRouteEvent(
        profile=decision.profile.value,
        model_id=decision.model_id,
        provider=decision.provider,
        stage=decision.stage,
        task_type=decision.task_type,
        route_reason=decision.route_reason,
        override_source=decision.override_source,
        fallback_chain=tuple(profile.value for profile in decision.fallback_chain),
        metadata=MappingProxyType(dict(metadata or {})),
    )


def _base_metadata(
    decision: ModelRouteDecision,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        **decision.to_dict(),
        **redact_route_metadata(metadata or {}),
    }


def _emit(
    event_type: str,
    summary: str,
    *,
    decision: ModelRouteDecision | None = None,
    metadata: Mapping[str, Any] | None = None,
    status: str = "OK",
    level: str = "INFO",
) -> None:
    try:
        from vnalpha.observability.audit import log_audit

        extra = (
            _base_metadata(decision, metadata)
            if decision is not None
            else dict(redact_route_metadata(metadata or {}))
        )
        log_audit(
            event_type,
            summary,
            status=status,
            level=level,
            extra=extra,
            module="vnalpha.model_routing",
            mode="redacted",
        )
    except Exception:
        pass


def emit_route_selected(
    decision: ModelRouteDecision,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    _emit(
        "MODEL_ROUTE_SELECTED",
        f"Selected {decision.profile.value} model for {decision.stage}",
        decision=decision,
        metadata=metadata,
    )


def emit_call_started(
    decision: ModelRouteDecision,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    _emit(
        "MODEL_CALL_STARTED",
        f"Model call started: {decision.profile.value}/{decision.stage}",
        decision=decision,
        metadata=metadata,
        status="STARTED",
    )


def emit_call_succeeded(
    decision: ModelRouteDecision,
    *,
    latency_ms: float,
    usage: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    usage_data = dict(usage or {})
    _emit(
        "MODEL_CALL_SUCCEEDED",
        f"Model call succeeded: {decision.profile.value}/{decision.stage}",
        decision=decision,
        metadata={
            **dict(metadata or {}),
            "latency_ms": round(latency_ms, 2),
            "tokens_in": usage_data.get("prompt_tokens")
            or usage_data.get("input_tokens"),
            "tokens_out": usage_data.get("completion_tokens")
            or usage_data.get("output_tokens"),
            "estimated_cost": usage_data.get("estimated_cost"),
        },
    )


def emit_call_failed(
    decision: ModelRouteDecision,
    error: Exception,
    *,
    latency_ms: float,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    _emit(
        "MODEL_CALL_FAILED",
        f"Model call failed: {decision.profile.value}/{decision.stage}: {type(error).__name__}",
        decision=decision,
        metadata={
            **dict(metadata or {}),
            "latency_ms": round(latency_ms, 2),
            "error_type": type(error).__name__,
        },
        status="FAILED",
        level="ERROR",
    )


def emit_fallback_used(
    previous: ModelRouteDecision,
    fallback: ModelRouteDecision,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    _emit(
        "MODEL_FALLBACK_USED",
        f"Model fallback: {previous.profile.value} -> {fallback.profile.value}",
        decision=fallback,
        metadata={
            **dict(metadata or {}),
            "fallback_from": previous.profile.value,
            "fallback_to": fallback.profile.value,
        },
        status="WARN",
        level="WARNING",
    )


def emit_override_event(
    event_type: str,
    *,
    profile: ModelProfile | None,
    scope: str,
) -> None:
    _emit(
        event_type,
        (
            f"Model override set to {profile.value} ({scope})"
            if profile is not None
            else f"Model override cleared ({scope})"
        ),
        metadata={
            "scope": scope,
            "profile": profile.value if profile is not None else None,
        },
    )
