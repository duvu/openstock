from __future__ import annotations

from vnalpha.ingestion.models import (
    IngestionErrorCategory,
    IngestionRemediationAction,
    IngestionRemediationStep,
    JsonValue,
    SymbolIngestionResult,
    SymbolIngestionStatus,
)


def failed_symbol_result(
    symbol: str,
    start: str | None,
    end: str | None,
    provider: str,
    category: IngestionErrorCategory,
    retryable: bool,
    message: str,
    attempts: int,
    diagnostics: dict[str, JsonValue] | None = None,
    diagnostics_ref: str | None = None,
) -> SymbolIngestionResult:
    remediation = remediation_step(
        symbol,
        start,
        end,
        None,
        IngestionRemediationAction.RETRY_OHLCV,
        "Retry the bounded provider request.",
    )
    return SymbolIngestionResult(
        symbol=symbol,
        status=SymbolIngestionStatus.FAILED,
        requested_start=start,
        requested_end=end,
        provider=provider,
        error_category=category,
        retryable=retryable,
        message=message,
        diagnostics_ref=diagnostics_ref,
        diagnostics=diagnostics or {},
        remediation=f"{remediation.guidance} {remediation.render_command()}",
        remediation_steps=(remediation,),
        attempts=attempts,
    )


def invalid_symbol_result(
    symbol: str,
    start: str | None,
    end: str | None,
    provider: str,
    category: IngestionErrorCategory,
    message: str,
    attempts: int,
    diagnostics: dict[str, JsonValue] | None = None,
    diagnostics_ref: str | None = None,
) -> SymbolIngestionResult:
    remediation = remediation_step(
        symbol,
        start,
        end,
        None,
        IngestionRemediationAction.INSPECT_DIAGNOSTICS_AND_RETRY,
        "Inspect the diagnostics reference, correct provider data, then retry.",
    )
    return SymbolIngestionResult(
        symbol=symbol,
        status=SymbolIngestionStatus.INVALID,
        requested_start=start,
        requested_end=end,
        provider=provider,
        error_category=category,
        message=message,
        diagnostics_ref=diagnostics_ref,
        diagnostics=diagnostics or {},
        remediation=f"{remediation.guidance} {remediation.render_command()}",
        remediation_steps=(remediation,),
        attempts=attempts,
    )


def remediation_step(
    symbol: str,
    start: str | None,
    end: str | None,
    source: str | None,
    action: IngestionRemediationAction,
    guidance: str,
) -> IngestionRemediationStep:
    parts = ["vnalpha", "data", "download", "ohlcv", symbol]
    if start:
        parts.extend(("--start", start))
    if end:
        parts.extend(("--end", end))
    if source:
        parts.extend(("--source", source))
    return IngestionRemediationStep(
        action=action,
        command=tuple(parts),
        guidance=guidance,
    )
