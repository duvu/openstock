"""Errors for the vnstock-service client."""

from __future__ import annotations

import json
import re
from typing import Any

_SAFE_DIAGNOSTIC = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")
_MAX_DIAGNOSTIC_LENGTH = 160
_MAX_PROVIDER_CANDIDATES = 8


def _safe_diagnostic(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized or len(normalized) > _MAX_DIAGNOSTIC_LENGTH:
        return None
    return normalized if _SAFE_DIAGNOSTIC.fullmatch(normalized) else None


def _service_error_payload(body: str) -> dict[str, Any]:
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _provider_candidates(payload: dict[str, Any]) -> tuple[str, ...]:
    raw_candidates = payload.get("candidates")
    if not isinstance(raw_candidates, list):
        return ()
    candidates = []
    for candidate in raw_candidates[:_MAX_PROVIDER_CANDIDATES]:
        safe_candidate = _safe_diagnostic(candidate)
        if safe_candidate is not None:
            candidates.append(safe_candidate)
    return tuple(candidates)


class VnstockClientError(Exception):
    """Base client error."""


class VnstockConnectionError(VnstockClientError):
    """Cannot connect to vnstock-service."""


class VnstockTimeoutError(VnstockConnectionError):
    pass


class VnstockHTTPError(VnstockClientError):
    """Non-200 response from vnstock-service."""

    def __init__(self, status_code: int, path: str, body: str = "") -> None:
        self.status_code = status_code
        self.path = path
        self.body = body
        payload = _service_error_payload(body)
        self.service_error_code = _safe_diagnostic(payload.get("error"))
        self.request_id = _safe_diagnostic(payload.get("request_id"))
        self.dataset = _safe_diagnostic(payload.get("dataset"))
        self.provider = _safe_diagnostic(payload.get("provider"))
        self.provider_error_code = _safe_diagnostic(
            payload.get("provider_error_code") or payload.get("failure_kind")
        )
        self.provider_candidates = _provider_candidates(payload)
        retryable = payload.get("retryable")
        self.retryable = retryable if isinstance(retryable, bool) else None
        super().__init__(f"HTTP {status_code} from {path}")


class VnstockDataError(VnstockClientError):
    """Response body could not be parsed or is malformed."""
