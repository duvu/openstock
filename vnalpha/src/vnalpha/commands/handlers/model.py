from __future__ import annotations

from typing import Any

from vnalpha.commands.errors import CommandValidationError
from vnalpha.commands.models import CommandResult, CommandStatus, ParsedCommand, ResultPanel
from vnalpha.model_routing import (
    DEFAULT_OVERRIDE_STORE,
    ModelProfile,
    ModelRoutingConfig,
    get_last_route_decision,
    resolve_model_route,
)


def handle_model(parsed: ParsedCommand, **_kwargs: Any) -> CommandResult:
    subcommand = parsed.positional[0].lower() if parsed.positional else "status"
    if subcommand in {profile.value for profile in ModelProfile}:
        parsed = ParsedCommand(
            command_name=parsed.command_name,
            raw_text=parsed.raw_text,
            positional=["use", subcommand],
            filters=list(parsed.filters),
            options=dict(parsed.options),
        )
        subcommand = "use"

    if subcommand == "status":
        return _status_result()
    if subcommand == "profiles":
        return _profiles_result()
    if subcommand == "use":
        return _use_result(parsed)
    if subcommand == "reset":
        return _reset_result(parsed)
    if subcommand == "explain-route":
        return _explain_route_result(parsed)
    raise CommandValidationError(
        "Unsupported /model subcommand. Use: status, profiles, use, reset, explain-route."
    )


def _status_result() -> CommandResult:
    config = ModelRoutingConfig.from_env()
    override = DEFAULT_OVERRIDE_STORE.get_current_override()
    last_route = get_last_route_decision()
    active_profile = override.session_profile or override.workspace_profile
    return CommandResult(
        status=CommandStatus.SUCCESS,
        title="/model status",
        summary=(
            f"Active model override: {active_profile.value}."
            if active_profile is not None
            else "Model routing policy is active with no override."
        ),
        panels=[
            ResultPanel(
                title="Model Routing Status",
                content={
                    "active_override": active_profile.value
                    if active_profile is not None
                    else None,
                    "override_source": "session"
                    if override.session_profile is not None
                    else "workspace"
                    if override.workspace_profile is not None
                    else None,
                    "default_profile": ModelProfile.DEFAULT.value,
                    "resolved_models": _profile_models(config),
                    "fallbacks": _fallbacks(config),
                    "last_route": last_route.to_dict() if last_route is not None else None,
                },
            )
        ],
    )


def _profiles_result() -> CommandResult:
    config = ModelRoutingConfig.from_env()
    return CommandResult(
        status=CommandStatus.SUCCESS,
        title="/model profiles",
        summary=f"{len(ModelProfile)} configured model profile(s).",
        panels=[
            ResultPanel(
                title="Configured Profiles",
                content={
                    "profiles": [
                        {
                            "profile": profile.value,
                            "model_id": config.model_for(profile),
                            "provider": config.provider_for(profile),
                            "explicitly_configured": config.is_explicitly_configured(
                                profile
                            ),
                            "fallbacks": [
                                fallback.value
                                for fallback in config.fallback_chain(profile)
                            ],
                        }
                        for profile in ModelProfile
                    ],
                    "raw_model_override_allowed": config.allow_raw_override,
                },
            )
        ],
    )


def _use_result(parsed: ParsedCommand) -> CommandResult:
    if len(parsed.positional) < 2:
        raise CommandValidationError("Usage: /model use <profile> [--scope session|workspace].")
    try:
        profile = ModelProfile.parse(parsed.positional[1])
    except ValueError as exc:
        raise CommandValidationError(str(exc)) from exc
    scope = str(parsed.options.get("scope", "workspace"))
    override = DEFAULT_OVERRIDE_STORE.set_override(profile, scope=scope)
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
                    "active_profile": active_profile.value
                    if active_profile is not None
                    else None,
                },
            )
        ],
    )


def _reset_result(parsed: ParsedCommand) -> CommandResult:
    scope = str(parsed.options.get("scope", "all"))
    DEFAULT_OVERRIDE_STORE.clear_override(scope=scope)
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


def _explain_route_result(parsed: ParsedCommand) -> CommandResult:
    if len(parsed.positional) < 2:
        raise CommandValidationError(
            "Usage: /model explain-route <stage-or-task> [--stage STAGE]."
        )
    target = parsed.positional[1].strip().lower().replace("-", "_")
    known_stages = {"classify", "plan", "synthesize", "compact", "title", "diagnose", "generic"}
    stage_option = parsed.options.get("stage")
    if stage_option:
        stage = str(stage_option)
        task_type = target
    elif target in known_stages:
        stage = target
        task_type = None
    else:
        stage = "synthesize"
        task_type = target
    decision = resolve_model_route(
        ModelRoutingConfig.from_env(),
        stage=stage,
        task_type=task_type,
        override=DEFAULT_OVERRIDE_STORE.get_current_override(),
    )
    return CommandResult(
        status=CommandStatus.SUCCESS,
        title="/model explain-route",
        summary=(
            f"{stage}/{task_type or '-'} routes to {decision.profile.value} "
            f"({decision.model_id})."
        ),
        panels=[ResultPanel(title="Route Decision", content=decision.to_dict())],
    )


def _profile_models(config: ModelRoutingConfig) -> dict[str, str]:
    return {profile.value: config.model_for(profile) for profile in ModelProfile}


def _fallbacks(config: ModelRoutingConfig) -> dict[str, list[str]]:
    return {
        profile.value: [item.value for item in config.fallback_chain(profile)]
        for profile in ModelProfile
    }
