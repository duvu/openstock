from __future__ import annotations

from vnalpha.clients.vnstock.errors import VnstockHTTPError
from vnalpha.ingestion.models import JsonValue


def is_retryable_http_failure(error: VnstockHTTPError) -> bool:
    if error.retryable is not None:
        return error.retryable
    return error.status_code in {408, 429} or error.status_code >= 500


def project_http_diagnostics(
    error: VnstockHTTPError,
    *,
    source_requested: str,
    attempted_providers: tuple[str, ...] = (),
) -> dict[str, JsonValue]:
    diagnostics: dict[str, JsonValue] = {
        "http_status": error.status_code,
        "source_requested": source_requested,
        "retryable": is_retryable_http_failure(error),
    }
    optional_values: tuple[tuple[str, str | None], ...] = (
        ("service_error_code", error.service_error_code),
        ("request_id", error.request_id),
        ("dataset", error.dataset),
        ("provider", error.provider),
        ("provider_error_code", error.provider_error_code),
    )
    for key, value in optional_values:
        if value is not None:
            diagnostics[key] = value
    if error.provider_candidates:
        diagnostics["provider_candidates"] = list(error.provider_candidates)
    if attempted_providers:
        diagnostics["attempted_providers"] = list(attempted_providers)
    return diagnostics


__all__ = ["is_retryable_http_failure", "project_http_diagnostics"]
