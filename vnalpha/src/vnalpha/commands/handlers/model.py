from __future__ import annotations

from typing import Any

from vnalpha.commands.errors import CommandValidationError
from vnalpha.commands.models import (
    CommandResult,
    CommandStatus,
    ParsedCommand,
    ResultPanel,
)
from vnalpha.model_routing import (
    DEFAULT_OVERRIDE_STORE,
    ModelProfile,
    ModelRoutingConfig,
    get_last_route_decision,
    resolve_model_route,
)

_PROFILE_NAMES = frozenset(profile.value for profile in ModelProfile)
_ROUTE_STAGES = frozenset(
    {"classify", "plan", "synthesize", "compact", "title", "diagnose", "generic"}
)


def handle_model(
    parsed: ParsedCommand,
    *,
    session_id: str | None = None,
    **_kwargs: Any,
) -> CommandResult:
    subcommand = parsed.positional[0].lower() if parsed.positional else "status"
    if subcommand in _PROFILE_NAMES:
        parsed = ParsedCommand(
            command_name=parsed.command_name,
            raw_text=parsed.raw_text,
            positional=["use", subcommand],
            filters=list(parsed.filters),
            options=dict(parsed.options),
        )
        subcommand = "use"

    if subcommand == "status":
        return _status_result(session_id=session_id)
    if subcommand == "profiles":
        return _profiles_result()
    if subcommand == "use":
        return _use_result(parsed, session_id=session_id)
    if subcommand == "reset":
        return _reset_result(parsed, session_id=session_id)
    if subcommand == "explain-route":
        return _explain_route_result(parsed)
    raise CommandValidationError(
        "Unsupported /model subcommand. Use: status, profiles, use, reset, "
        "explain-route."
    )


def _status_result(*, session_id: str | None = None) -> CommandResult:
    override = DEFAULT_OVERRIDE_STORE.get_current_override(session_id=session_id)
    last_route = get_last_route_decision()
    active_profile = override.session_profile or override.workspace_profile
    config, config_error = _load_optional_config()
    if config is None:
        return CommandResult(
            status=CommandStatus.PARTIAL,
            title="/model status",
            summary="Assistant model routing is disabled until a verified model is configured.",
            panels=[
                ResultPanel(
                    title="Model Routing Status",
                    content={
                        "active_override": (
                            active_profile.value if active_profile is not None else None
                        ),
                        "session_id": session_id,
                        "override_source": (
                            "session"
                            if override.session_profile is not None
                            else "workspace"
                            if override.workspace_profile is not None
                            else None
                        ),
                        "routing_mode": "disabled",
                        "configured": False,
                        "configuration_error": config_error,
                        "distinct_model_count": 0,
                        "distinct_models": [],
                        "default_profile": ModelProfile.DEFAULT.value,
                        "resolved_models": {},
                        "effective_fallbacks": {},
                        "last_route": (
                            last_route.to_dict() if last_route is not None else None
                        ),
                    },
                )
            ],
        )

    distinct_models = _distinct_models(config)
    routing_mode = "multi_model" if len(distinct_models) > 1 else "single_model"
    return CommandResult(
        status=CommandStatus.SUCCESS,
        title="/model status",
        summary=(
            f"Active model override: {active_profile.value}; routing mode: {routing_mode}."
            if active_profile is not None
            else f"Model routing policy is active in {routing_mode} mode."
        ),
        panels=[
            ResultPanel(
                title="Model Routing Status",
                content={
                    "active_override": (
                        active_profile.value if active_profile is not None else None
                    ),
                    "session_id": session_id,
                    "override_source": (
                        "session"
                        if override.session_profile is not None
                        else "workspace"
                        if override.workspace_profile is not None
                        else None
                    ),
                    "routing_mode": routing_mode,
                    "configured": True,
                    "distinct_model_count": len(distinct_models),
                    "distinct_models": sorted(distinct_models),
                    "default_profile": ModelProfile.DEFAULT.value,
                    "resolved_models": _profile_models(config),
                    "effective_fallbacks": _effective_fallbacks(config),
                    "last_route": (
                        last_route.to_dict() if last_route is not None else None
                    ),
                },
            )
        ],
    )


def _profiles_result() -> CommandResult:
    config = _load_config()
    distinct_models = _distinct_models(config)
    return CommandResult(
        status=CommandStatus.SUCCESS,
        title="/model profiles",
        summary=(
            f"{len(ModelProfile)} profile(s) resolve to "
            f"{len(distinct_models)} distinct model(s)."
        ),
        panels=[
            ResultPanel(
                title="Configured Profiles",
                content={
                    "routing_mode": (
                        "multi_model" if len(distinct_models) > 1 else "single_model"
                    ),
                    "profiles": [
                        {
                            "profile": profile.value,
                            "model_id": config.model_for(profile),
                            "provider": config.provider_for(profile),
                            "explicitly_configured": config.is_explicitly_configured(
                                profile
                            ),
                            "effective_fallbacks": _effective_fallbacks(config)[
                                profile.value
                            ],
                        }
                        for profile in ModelProfile
                    ],
                    "raw_model_override_allowed": config.allow_raw_override,
                },
            )
        ],
    )


def _use_result(
    parsed: ParsedCommand, *, session_id: str | None = None
) -> CommandResult:
    if len(parsed.positional) < 2:
        raise CommandValidationError(
            "Usage: /model use <profile> [--scope session|workspace]."
        )
    try:
        profile = ModelProfile.parse(parsed.positional[1])
    except ValueError as exc:
        raise CommandValidationError(str(exc)) from exc
    scope = _validated_scope(
        parsed.options.get("scope", "workspace"), allowed={"session", "workspace"}
    )
    try:
        override = DEFAULT_OVERRIDE_STORE.set_override(
            profile, scope=scope, session_id=session_id
        )
    except (RuntimeError, ValueError) as exc:
        raise CommandValidationError(str(exc)) from exc
    active_profile = override.session_profile or override.workspace_profile
    return CommandResult(
        status=CommandStatus.SUCCESS,
        title="/model use",
        summary=f"Model profile override set to {profile.value} ({scope}).",
        panels=[
            ResultPanel(
                title="Model Override",
                content={
                    "profile": profile.value,
                    "scope": scope,
                    "active_profile": (
                        active_profile.value if active_profile is not None else None
                    ),
                },
            )
        ],
    )


def _reset_result(
    parsed: ParsedCommand, *, session_id: str | None = None
) -> CommandResult:
    scope = _validated_scope(
        parsed.options.get("scope", "all"),
        allowed={"all", "session", "workspace"},
    )
    try:
        DEFAULT_OVERRIDE_STORE.clear_override(scope=scope, session_id=session_id)
    except ValueError as exc:
        raise CommandValidationError(str(exc)) from exc
    return CommandResult(
        status=CommandStatus.SUCCESS,
        title="/model reset",
        summary=f"Model override cleared ({scope}); routing policy restored.",
        panels=[
            ResultPanel(
                title="Model Override",
                content={"scope": scope, "active_profile": None},
            )
        ],
    )


def _explain_route_result(
    parsed: ParsedCommand, *, session_id: str | None = None
) -> CommandResult:
    if len(parsed.positional) < 2:
        raise CommandValidationError(
            "Usage: /model explain-route <stage-or-task> [--stage STAGE]."
        )
    target = parsed.positional[1].strip().lower().replace("-", "_")
    stage_option = parsed.options.get("stage")
    if stage_option:
        stage = str(stage_option).strip().lower().replace("-", "_")
        task_type = target
    elif target in _ROUTE_STAGES:
        stage = target
        task_type = None
    else:
        stage = "synthesize"
        task_type = target
    if stage not in _ROUTE_STAGES:
        allowed = ", ".join(sorted(_ROUTE_STAGES))
        raise CommandValidationError(
            f"Unknown model route stage '{stage}'. Expected one of: {allowed}."
        )
    config = _load_config()
    decision = resolve_model_route(
        config,
        stage=stage,
        task_type=task_type,
        override=DEFAULT_OVERRIDE_STORE.get_current_override(session_id=session_id),
    )
    effective_fallbacks = _effective_fallbacks(config)[decision.profile.value]
    payload = decision.to_dict()
    payload["effective_fallbacks"] = effective_fallbacks
    return CommandResult(
        status=CommandStatus.SUCCESS,
        title="/model explain-route",
        summary=(
            f"{stage}/{task_type or '-'} routes to {decision.profile.value} "
            f"({decision.model_id}); {len(effective_fallbacks)} effective fallback(s)."
        ),
        panels=[ResultPanel(title="Route Decision", content=payload)],
    )


def _validated_scope(value: object, *, allowed: set[str]) -> str:
    scope = str(value).strip().lower()
    if scope not in allowed:
        expected = ", ".join(sorted(allowed))
        raise CommandValidationError(
            f"Invalid model override scope '{scope}'. Expected one of: {expected}."
        )
    return scope


def _load_config() -> ModelRoutingConfig:
    try:
        return ModelRoutingConfig.from_env()
    except ValueError as exc:
        raise CommandValidationError(
            f"Invalid model routing configuration: {exc}"
        ) from exc


def _load_optional_config() -> tuple[ModelRoutingConfig | None, str | None]:
    try:
        return ModelRoutingConfig.from_env(), None
    except ValueError as exc:
        return None, str(exc)


def _profile_models(config: ModelRoutingConfig) -> dict[str, str]:
    return {profile.value: config.model_for(profile) for profile in ModelProfile}


def _distinct_models(config: ModelRoutingConfig) -> set[str]:
    return {config.model_for(profile) for profile in ModelProfile}


def _effective_fallbacks(config: ModelRoutingConfig) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = {}
    for profile in ModelProfile:
        primary_model = config.model_for(profile)
        seen_models = {primary_model}
        effective: list[dict[str, str]] = []
        for fallback in config.fallback_chain(profile):
            fallback_model = config.model_for(fallback)
            if fallback_model in seen_models:
                continue
            seen_models.add(fallback_model)
            effective.append({"profile": fallback.value, "model_id": fallback_model})
        result[profile.value] = effective
    return result
