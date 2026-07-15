from __future__ import annotations

from enum import Enum

from vnstock.core.provider.exceptions import ProviderFetchError


class FiinQuantXFailureKind(str, Enum):
    NOT_INSTALLED = "not_installed"
    UNTESTED_VERSION = "untested_version"
    LICENSE_NOT_ACKNOWLEDGED = "license_not_acknowledged"
    CREDENTIALS_MISSING = "credentials_missing"
    AUTHENTICATION = "authentication"
    ENTITLEMENT = "entitlement"
    RATE_LIMIT = "rate_limit"
    QUOTA = "quota"
    CONCURRENCY = "concurrency"
    INVALID_REQUEST = "invalid_request"
    SCHEMA = "schema"
    TRANSIENT = "transient"
    PROVIDER = "provider"


class FiinQuantXProviderError(ProviderFetchError):
    kind = FiinQuantXFailureKind.PROVIDER
    retryable = False

    def __init__(
        self,
        dataset: str,
        *,
        vendor_exception_type: str | None = None,
    ) -> None:
        self.kind = type(self).kind
        self.retryable = type(self).retryable
        self.vendor_exception_type = vendor_exception_type
        super().__init__("FIINQUANTX", dataset)

    def diagnostics(self) -> dict[str, str | bool | None]:
        return {
            "kind": self.kind.value,
            "retryable": self.retryable,
            "vendor_exception_type": self.vendor_exception_type,
        }


class FiinQuantXCredentialsMissingError(FiinQuantXProviderError):
    kind = FiinQuantXFailureKind.CREDENTIALS_MISSING


class FiinQuantXLicenseNotAcknowledgedError(FiinQuantXProviderError):
    kind = FiinQuantXFailureKind.LICENSE_NOT_ACKNOWLEDGED


class FiinQuantXNotInstalledError(FiinQuantXProviderError):
    kind = FiinQuantXFailureKind.NOT_INSTALLED


class FiinQuantXVersionError(FiinQuantXProviderError):
    kind = FiinQuantXFailureKind.UNTESTED_VERSION


class FiinQuantXAuthenticationError(FiinQuantXProviderError):
    kind = FiinQuantXFailureKind.AUTHENTICATION


class FiinQuantXEntitlementError(FiinQuantXProviderError):
    kind = FiinQuantXFailureKind.ENTITLEMENT


class FiinQuantXRateLimitError(FiinQuantXProviderError):
    kind = FiinQuantXFailureKind.RATE_LIMIT
    retryable = True


class FiinQuantXQuotaError(FiinQuantXProviderError):
    kind = FiinQuantXFailureKind.QUOTA


class FiinQuantXConcurrencyError(FiinQuantXProviderError):
    kind = FiinQuantXFailureKind.CONCURRENCY
    retryable = True


class FiinQuantXInvalidRequestError(FiinQuantXProviderError):
    kind = FiinQuantXFailureKind.INVALID_REQUEST


class FiinQuantXSchemaError(FiinQuantXProviderError):
    kind = FiinQuantXFailureKind.SCHEMA


class FiinQuantXTransientError(FiinQuantXProviderError):
    kind = FiinQuantXFailureKind.TRANSIENT
    retryable = True


_AUTH_MARKERS = (
    "authentication",
    "credential",
    "invalid password",
    "invalid username",
    "login",
    "not logged",
    "session expired",
    "unauthorized",
)
_ENTITLEMENT_MARKERS = (
    "access denied",
    "entitlement",
    "forbidden",
    "not allowed",
    "permission",
    "subscription",
)
_RATE_LIMIT_MARKERS = ("429", "rate limit", "too many request")
_QUOTA_MARKERS = ("quota", "monthly limit", "request limit exceeded")
_INVALID_REQUEST_MARKERS = (
    "bad request",
    "invalid argument",
    "invalid parameter",
    "unsupported interval",
)
_TRANSIENT_MARKERS = (
    "connection",
    "temporarily unavailable",
    "timeout",
    "timed out",
    "try again",
)


def map_fiinquantx_exception(
    exc: BaseException,
    dataset: str,
) -> FiinQuantXProviderError:
    """Map a vendor failure to a stable, redacted platform error.

    Vendor messages are inspected only in-process for classification. They are not
    copied into the public exception string, diagnostics, logs, or service output.
    """

    if isinstance(exc, FiinQuantXProviderError):
        return exc
    text = str(exc).strip().lower()
    exception_type = type(exc).__name__
    if any(marker in text for marker in _RATE_LIMIT_MARKERS):
        cls = FiinQuantXRateLimitError
    elif any(marker in text for marker in _QUOTA_MARKERS):
        cls = FiinQuantXQuotaError
    elif any(marker in text for marker in _ENTITLEMENT_MARKERS):
        cls = FiinQuantXEntitlementError
    elif any(marker in text for marker in _AUTH_MARKERS):
        cls = FiinQuantXAuthenticationError
    elif any(marker in text for marker in _INVALID_REQUEST_MARKERS):
        cls = FiinQuantXInvalidRequestError
    elif any(marker in text for marker in _TRANSIENT_MARKERS):
        cls = FiinQuantXTransientError
    else:
        cls = FiinQuantXProviderError
    return cls(dataset, vendor_exception_type=exception_type)


__all__ = [
    "FiinQuantXAuthenticationError",
    "FiinQuantXConcurrencyError",
    "FiinQuantXCredentialsMissingError",
    "FiinQuantXEntitlementError",
    "FiinQuantXFailureKind",
    "FiinQuantXInvalidRequestError",
    "FiinQuantXLicenseNotAcknowledgedError",
    "FiinQuantXNotInstalledError",
    "FiinQuantXProviderError",
    "FiinQuantXQuotaError",
    "FiinQuantXRateLimitError",
    "FiinQuantXSchemaError",
    "FiinQuantXTransientError",
    "FiinQuantXVersionError",
    "map_fiinquantx_exception",
]
