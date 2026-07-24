"""Concurrent-safe OHLCV provider fetch outcomes without warehouse writes."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError

from vnalpha.clients.vnstock.client import VnstockClient
from vnalpha.clients.vnstock.errors import (
    VnstockConnectionError,
    VnstockDataError,
    VnstockHTTPError,
    VnstockTimeoutError,
)
from vnalpha.clients.vnstock.schemas import OHLCVResponse
from vnalpha.clients.vnstock.source_policy import validate_persistence_source
from vnalpha.core.logging import get_logger
from vnalpha.core.text_safety import redact_structure
from vnalpha.ingestion.models import (
    IngestionErrorCategory,
    IngestionRemediationAction,
    JsonValue,
    SymbolIngestionResult,
    SymbolIngestionStatus,
)
from vnalpha.ingestion.persistence import (
    persistence_diagnostics,
    validated_ohlcv_price_basis,
)
from vnalpha.ingestion.provider_failures import (
    is_retryable_http_failure,
    project_http_diagnostics,
)
from vnalpha.ingestion.symbol_outcomes import (
    failed_symbol_result,
    invalid_symbol_result,
    remediation_step,
)

logger = get_logger("ingestion.sync_ohlcv")
_MAX_ATTEMPTS = 2


@dataclass(frozen=True, slots=True)
class FetchedOHLCV:
    response: OHLCVResponse
    provider: str
    price_basis: str
    quality_report: dict[str, JsonValue]
    diagnostics: dict[str, JsonValue]
    attempts: int


FetchOHLCVOutcome = FetchedOHLCV | SymbolIngestionResult


def fetch_ohlcv_for_symbol(
    client: VnstockClient,
    symbol: str,
    *,
    start: str | None = None,
    end: str | None = None,
    interval: str = "1D",
    source: str | None = None,
) -> FetchOHLCVOutcome:
    """Fetch and validate one OHLCV payload without mutating the warehouse."""
    provider = source or "auto"
    attempted_providers: list[str] = []
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            response = client.get_equity_ohlcv(
                symbol=symbol,
                start=start,
                end=end,
                interval=interval,
                source=source,
            )
        except VnstockHTTPError as exc:
            if exc.provider is not None and exc.provider not in attempted_providers:
                attempted_providers.append(exc.provider)
            diagnostics = project_http_diagnostics(
                exc,
                source_requested=source or "auto",
                attempted_providers=tuple(attempted_providers),
            )
            failed_provider = exc.provider or provider
            if exc.status_code == 422:
                return invalid_symbol_result(
                    symbol,
                    start,
                    end,
                    failed_provider,
                    IngestionErrorCategory.PROVIDER_DATA,
                    "Provider rejected invalid OHLCV data.",
                    attempt,
                    diagnostics=diagnostics,
                    diagnostics_ref=exc.request_id,
                )
            retryable = is_retryable_http_failure(exc)
            if retryable and attempt < _MAX_ATTEMPTS:
                logger.warning("Retrying OHLCV provider request for %s", symbol)
                continue
            return failed_symbol_result(
                symbol,
                start,
                end,
                failed_provider,
                IngestionErrorCategory.HTTP,
                retryable,
                "Provider HTTP request failed.",
                attempt,
                diagnostics=diagnostics,
                diagnostics_ref=exc.request_id,
            )
        except VnstockTimeoutError:
            if attempt < _MAX_ATTEMPTS:
                logger.warning("Retrying OHLCV provider request for %s", symbol)
                continue
            return failed_symbol_result(
                symbol,
                start,
                end,
                provider,
                IngestionErrorCategory.TIMEOUT,
                True,
                "Provider request timed out.",
                attempt,
            )
        except VnstockConnectionError:
            if attempt < _MAX_ATTEMPTS:
                logger.warning("Retrying OHLCV provider request for %s", symbol)
                continue
            return failed_symbol_result(
                symbol,
                start,
                end,
                provider,
                IngestionErrorCategory.CONNECTION,
                True,
                "Provider connection failed.",
                attempt,
            )
        except VnstockDataError:
            return invalid_symbol_result(
                symbol,
                start,
                end,
                provider,
                IngestionErrorCategory.INVALID_JSON,
                "Provider returned invalid JSON.",
                attempt,
            )
        except ValidationError:
            return invalid_symbol_result(
                symbol,
                start,
                end,
                provider,
                IngestionErrorCategory.INVALID_DATA,
                "Provider returned invalid OHLCV data.",
                attempt,
            )
        except RuntimeError:
            return failed_symbol_result(
                symbol,
                start,
                end,
                provider,
                IngestionErrorCategory.PROVIDER,
                False,
                "Provider runtime failed.",
                attempt,
            )

        provider = response.meta.provider.strip().upper()
        diagnostics = persistence_diagnostics(provider, response.diagnostics)
        if response.meta.dataset != "equity.ohlcv":
            return invalid_symbol_result(
                symbol,
                start,
                end,
                provider,
                IngestionErrorCategory.PROVIDER_DATA,
                "Provider returned an unexpected OHLCV dataset.",
                attempt,
                diagnostics=diagnostics,
            )
        actual_source = validate_persistence_source(provider)
        requested_source = source.strip().upper() if source else None
        if requested_source is not None and actual_source != requested_source:
            return invalid_symbol_result(
                symbol,
                start,
                end,
                provider,
                IngestionErrorCategory.PROVIDER_DATA,
                "Provider response did not match the explicitly selected source.",
                attempt,
                diagnostics=diagnostics,
            )
        quality_report = response.meta.quality_report or response.diagnostics.get(
            "quality", {}
        )
        if not isinstance(quality_report, dict):
            quality_report = {}
        redacted_quality_report = redact_structure(quality_report)
        quality_report = (
            redacted_quality_report if isinstance(redacted_quality_report, dict) else {}
        )
        quality_status = (response.meta.quality_status or "").lower()
        if quality_status == "skipped":
            return SymbolIngestionResult(
                symbol=symbol,
                status=SymbolIngestionStatus.SKIPPED,
                requested_start=start,
                requested_end=end,
                provider=provider,
                diagnostics_ref=response.meta.request_id,
                quality_report=quality_report,
                diagnostics=diagnostics,
                message="Provider marked the OHLCV request as skipped.",
                attempts=attempt,
            )
        if quality_status not in {
            "pass",
            "success",
            "error",
            "fail",
            "failed",
            "invalid",
        }:
            return invalid_symbol_result(
                symbol,
                start,
                end,
                provider,
                IngestionErrorCategory.PROVIDER_DATA,
                "Provider response lacked validated quality evidence.",
                attempt,
                diagnostics=diagnostics,
            )
        if not response.data:
            remediation = remediation_step(
                symbol,
                start,
                end,
                source,
                IngestionRemediationAction.VERIFY_RANGE_AND_RETRY,
                "Verify the requested range and provider, then retry the bounded command.",
            )
            return SymbolIngestionResult(
                symbol=symbol,
                status=SymbolIngestionStatus.EMPTY,
                requested_start=start,
                requested_end=end,
                provider=provider,
                diagnostics_ref=response.meta.request_id,
                quality_report=quality_report,
                diagnostics=diagnostics,
                message="Provider returned no rows for the requested range.",
                remediation=f"{remediation.guidance} {remediation.render_command()}",
                remediation_steps=(remediation,),
                attempts=attempt,
            )
        return FetchedOHLCV(
            response=response,
            provider=provider,
            price_basis=validated_ohlcv_price_basis(provider, response.diagnostics),
            quality_report=quality_report,
            diagnostics=diagnostics,
            attempts=attempt,
        )
    raise AssertionError("bounded retry loop did not return")


__all__ = ["FetchedOHLCV", "FetchOHLCVOutcome", "fetch_ohlcv_for_symbol"]
