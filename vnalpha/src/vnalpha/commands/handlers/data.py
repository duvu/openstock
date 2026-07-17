from __future__ import annotations

from vnalpha.commands.errors import CommandValidationError
from vnalpha.commands.models import (
    CommandResult,
    CommandStatus,
    ParsedCommand,
    ResultPanel,
)
from vnalpha.data_provisioning.service import (
    DataProvisioningRequest,
    DataProvisioningService,
    DataProvisioningValidationError,
    ProvisioningStatus,
)
from vnalpha.scoring.policy import (
    BASELINE_SCORING_POLICY,
    parse_scoring_policy_reference,
)


def handle_data(
    parsed: ParsedCommand,
    conn=None,
    service: DataProvisioningService | None = None,
    **_kwargs,
) -> CommandResult:
    if conn is None:
        return CommandResult(
            status=CommandStatus.FAILED,
            title="/data",
            summary="No database connection.",
        )
    if parsed.filters:
        raise CommandValidationError("Filters are not supported by /data.")
    unsupported_options = set(parsed.options) - {
        "start",
        "end",
        "date",
        "source",
        "benchmark",
        "from",
        "to",
        "scoring-policy",
        "rebuild-policy",
    }
    if unsupported_options:
        rendered_options = ", ".join(
            f"--{option}" for option in sorted(unsupported_options)
        )
        raise CommandValidationError(f"Unsupported option: {rendered_options}.")
    operation = parsed.positional[0] if parsed.positional else ""
    if operation == "gaps":
        if len(parsed.positional) != 2:
            raise CommandValidationError(_usage())
        artifact = "ohlcv"
        symbol = parsed.positional[1]
    else:
        if len(parsed.positional) < 2 or len(parsed.positional) > 3:
            raise CommandValidationError(_usage())
        artifact = parsed.positional[1]
        symbol = parsed.positional[2] if len(parsed.positional) == 3 else None
    scoring_policy = _option_value(parsed, "scoring-policy")
    policy_auto = scoring_policy is None
    try:
        policy_id, policy_version = (
            parse_scoring_policy_reference(scoring_policy)
            if scoring_policy
            else (
                BASELINE_SCORING_POLICY.policy_id,
                BASELINE_SCORING_POLICY.version,
            )
        )
    except ValueError as exc:
        raise CommandValidationError("--scoring-policy must use ID@version.") from exc
    request = DataProvisioningRequest(
        operation=operation,
        artifact=artifact,
        symbol=symbol,
        start=_range_option(parsed, "start", "from"),
        end=_range_option(parsed, "end", "to"),
        date=_option_value(parsed, "date"),
        source=_option_value(parsed, "source"),
        benchmark=_option_value(parsed, "benchmark"),
        scoring_policy_id=policy_id,
        scoring_policy_version=policy_version,
        rebuild_policy=parsed.options.get("rebuild-policy") is True,
        scoring_policy_auto=policy_auto,
    )
    provisioning_service = service or DataProvisioningService(conn)
    try:
        result = provisioning_service.execute(request)
    except DataProvisioningValidationError as exc:
        raise CommandValidationError(f"{exc} {_usage()}") from exc

    return CommandResult(
        status=_command_status(result.status),
        title=f"/data {result.operation} {result.artifact}",
        summary=_summary(result),
        panels=[ResultPanel(title="Data Provisioning", content=_payload(result))],
        warnings=list(result.warnings),
    )


def _option_value(parsed: ParsedCommand, name: str) -> str | None:
    value = parsed.options.get(name)
    if value is None:
        return None
    if isinstance(value, bool):
        raise CommandValidationError(f"--{name} requires a value.")
    return value


def _range_option(parsed: ParsedCommand, primary: str, alias: str) -> str | None:
    primary_value = _option_value(parsed, primary)
    alias_value = _option_value(parsed, alias)
    if primary_value is not None and alias_value is not None:
        raise CommandValidationError(f"Use only one of --{primary} or --{alias}.")
    return primary_value or alias_value


def _command_status(status: ProvisioningStatus) -> CommandStatus:
    match status:
        case ProvisioningStatus.SUCCESS:
            return CommandStatus.SUCCESS
        case ProvisioningStatus.PARTIAL:
            return CommandStatus.PARTIAL
        case ProvisioningStatus.FAILED:
            return CommandStatus.FAILED


def _summary(result) -> str:
    if result.status is ProvisioningStatus.FAILED:
        return result.error or "Data provisioning did not complete."
    return f"{result.artifact} {result.status.value.lower()}."


def _payload(result) -> dict[str, str | dict[str, int] | list[str] | None]:
    return {
        "status": result.status.value,
        "operation": result.operation,
        "artifact": result.artifact,
        "symbol": result.symbol,
        "source": result.source,
        "start": result.start,
        "end": result.end,
        "resolved_date": result.resolved_date,
        "requested_date": result.requested_date,
        "freshness": result.freshness,
        "lineage": result.lineage,
        "follow_up": result.follow_up,
        "counts": result.counts,
        "warnings": list(result.warnings),
        "error": result.error,
        "terminal_reason": result.terminal_reason,
        "correlation_id": result.correlation_id,
        "symbol_results": [
            symbol_result.to_payload() for symbol_result in result.symbol_results
        ],
    }


def _usage() -> str:
    return (
        "Use /data download <symbols|ohlcv SYMBOL|index [SYMBOL]> "
        "[--start YYYY-MM-DD] [--end YYYY-MM-DD] [--source PROVIDER] "
        "[--scoring-policy ID@VERSION] or "
        "/data build <canonical SYMBOL|features SYMBOL --date DATE|score SYMBOL --date DATE|"
        "market-regime --date DATE|sector-strength --date DATE>, "
        "/data sync daily [--date DATE], /data gaps SYMBOL [--from DATE] [--to DATE], "
        "or /data repair ohlcv SYMBOL [--from DATE] [--to DATE]."
    )
