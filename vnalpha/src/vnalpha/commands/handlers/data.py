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
    unsupported_options = set(parsed.options) - {"start", "end", "date", "source"}
    if unsupported_options:
        rendered_options = ", ".join(
            f"--{option}" for option in sorted(unsupported_options)
        )
        raise CommandValidationError(f"Unsupported option: {rendered_options}.")
    if len(parsed.positional) < 2 or len(parsed.positional) > 3:
        raise CommandValidationError(_usage())

    operation, artifact = parsed.positional[:2]
    symbol = parsed.positional[2] if len(parsed.positional) == 3 else None
    request = DataProvisioningRequest(
        operation=operation,
        artifact=artifact,
        symbol=symbol,
        start=_option_value(parsed, "start"),
        end=_option_value(parsed, "end"),
        date=_option_value(parsed, "date"),
        source=_option_value(parsed, "source"),
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
        "correlation_id": result.correlation_id,
    }


def _usage() -> str:
    return (
        "Use /data download <symbols|ohlcv SYMBOL|index [SYMBOL]> "
        "[--start YYYY-MM-DD] [--end YYYY-MM-DD] [--source PROVIDER] or "
        "/data build <canonical SYMBOL|features SYMBOL --date DATE|score SYMBOL --date DATE|"
        "market-regime --date DATE|sector-strength --date DATE>."
    )
