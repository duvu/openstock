"""Errors for the vnstock-service client."""
from __future__ import annotations


class VnstockClientError(Exception):
    """Base client error."""


class VnstockConnectionError(VnstockClientError):
    """Cannot connect to vnstock-service."""


class VnstockHTTPError(VnstockClientError):
    """Non-200 response from vnstock-service."""

    def __init__(self, status_code: int, path: str, body: str = "") -> None:
        self.status_code = status_code
        self.path = path
        self.body = body
        super().__init__(f"HTTP {status_code} from {path}: {body[:200]}")


class VnstockDataError(VnstockClientError):
    """Response body could not be parsed or is malformed."""
