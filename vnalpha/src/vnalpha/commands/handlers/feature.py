from __future__ import annotations

from vnalpha.commands.errors import CommandValidationError
from vnalpha.commands.models import CommandResult, ParsedCommand, ResultPanel
from vnalpha.research_automation.feature_service import FeatureAutomationService


def handle_feature(parsed: ParsedCommand, conn=None, **_kwargs) -> CommandResult:
    if conn is None:
        return CommandResult(
            status="FAILED", title="/feature", summary="No database connection."
        )
    if not parsed.positional:
        raise CommandValidationError(
            "Feature subcommand is required: create or validate."
        )
    subcommand = parsed.positional[0].lower()
    service = FeatureAutomationService(conn)
    if subcommand == "create":
        return _create(parsed, service)
    if subcommand == "validate":
        return _validate(parsed, service)
    raise CommandValidationError(
        "Unsupported /feature subcommand. Supported: create, validate."
    )


def _create(parsed: ParsedCommand, service: FeatureAutomationService) -> CommandResult:
    if parsed.filters or set(parsed.options) - {"universe"}:
        raise CommandValidationError("/feature create supports only --universe.")
    definition = " ".join(parsed.positional[1:]).strip()
    if not definition:
        raise CommandValidationError(
            "/feature create requires feature_name = expression."
        )
    universe_value = parsed.options.get("universe")
    if universe_value is True:
        raise CommandValidationError("--universe requires a value.")
    try:
        feature = service.create(
            definition,
            universe=str(universe_value) if universe_value else None,
        )
    except ValueError as exc:
        raise CommandValidationError(str(exc)) from exc
    return CommandResult(
        status="SUCCESS",
        title="/feature create",
        summary=f"Research feature {feature.feature_name} was persisted; no code was executed.",
        panels=[
            ResultPanel(
                title="Research Feature",
                content={
                    "artifact_id": feature.artifact.artifact_id,
                    "feature_name": feature.feature_name,
                    "expression": feature.feature_expression,
                    "universe": feature.universe,
                    "status": feature.artifact.status.value,
                    "research_only": True,
                },
            )
        ],
        warnings=list(feature.artifact.caveats),
    )


def _validate(
    parsed: ParsedCommand, service: FeatureAutomationService
) -> CommandResult:
    if len(parsed.positional) != 2 or parsed.options or parsed.filters:
        raise CommandValidationError(
            "/feature validate requires exactly one feature ID or name."
        )
    try:
        validation = service.validate(parsed.positional[1])
    except ValueError as exc:
        raise CommandValidationError(str(exc)) from exc
    return CommandResult(
        status="SUCCESS" if validation.schema_valid else "PARTIAL",
        title="/feature validate",
        summary=f"Feature validation completed with {validation.quality_status} quality status.",
        panels=[
            ResultPanel(title="Feature Validation", content=validation.as_payload())
        ],
        warnings=list(validation.warnings),
    )


__all__ = ["handle_feature"]
