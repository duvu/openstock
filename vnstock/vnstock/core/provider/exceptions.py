"""
Platform-level exceptions for the vnstock plugin architecture.

These exceptions are distinct from the legacy VnstockError hierarchy
in vnstock/core/exceptions.py. They target the new plugin/routing layer.

Hierarchy::

    VnstockPlatformError
    ├── DatasetContractError
    ├── ProviderNotFoundError
    ├── UnsupportedDatasetError
    ├── UnsupportedDatasetForProviderError
    ├── ProviderFetchError
    ├── NoProviderForDatasetError
    ├── NoHealthyProviderError
    ├── ProviderInCooldownError
    └── ProviderDisabledError
"""

from __future__ import annotations


class VnstockPlatformError(Exception):
    """Base exception for the vnstock plugin platform layer."""


class DatasetContractError(VnstockPlatformError):
    """Raised when a dataset contract is missing or invalid.

    Args:
        dataset: The dataset name that caused the error.
        message: Optional detail message.
    """

    def __init__(self, dataset: str, message: str | None = None) -> None:
        self.dataset = dataset
        detail = message or f"Dataset contract error for '{dataset}'."
        super().__init__(detail)


class ProviderNotFoundError(VnstockPlatformError):
    """Raised when a requested provider is not registered.

    Args:
        name: The provider name that was not found.
    """

    def __init__(self, name: str) -> None:
        self.provider_name = name
        super().__init__(f"Provider '{name}' is not registered.")


class UnsupportedDatasetError(VnstockPlatformError):
    """Raised when no registered provider supports the requested dataset.

    Args:
        dataset: The dataset name with no supporting providers.
    """

    def __init__(self, dataset: str) -> None:
        self.dataset = dataset
        super().__init__(f"No registered provider supports dataset '{dataset}'.")


class UnsupportedDatasetForProviderError(VnstockPlatformError):
    """Raised when a specific provider does not support the requested dataset.

    Args:
        provider_name: The provider that was asked.
        dataset: The dataset name that provider does not support.
    """

    def __init__(self, provider_name: str, dataset: str) -> None:
        self.provider_name = provider_name
        self.dataset = dataset
        super().__init__(
            f"Provider '{provider_name}' does not support dataset '{dataset}'."
        )


class ProviderFetchError(VnstockPlatformError):
    """Raised when a provider fails to fetch data.

    Args:
        provider_name: The provider that failed.
        dataset: The dataset that was being fetched.
        cause: The underlying exception, if any.
    """

    def __init__(
        self,
        provider_name: str,
        dataset: str,
        cause: BaseException | None = None,
    ) -> None:
        self.provider_name = provider_name
        self.dataset = dataset
        self.cause = cause
        msg = f"Provider '{provider_name}' failed to fetch dataset '{dataset}'."
        if cause:
            msg += f" Cause: {cause}"
        super().__init__(msg)


class NoProviderForDatasetError(VnstockPlatformError):
    """Raised when no provider is registered that supports *dataset* at all.

    Unlike :class:`UnsupportedDatasetError` (which signals no provider passed
    health/policy filters), this error means the dataset has zero registered
    providers regardless of health.

    Args:
        dataset: The dataset name with no registered providers.
    """

    def __init__(self, dataset: str) -> None:
        self.dataset = dataset
        super().__init__(f"No provider is registered for dataset '{dataset}'.")


class NoHealthyProviderError(VnstockPlatformError):
    """Raised when providers exist for *dataset* but none pass health checks.

    Args:
        dataset: The dataset that was requested.
        candidates: Provider names that were evaluated but rejected.
        rejection_reasons: Optional mapping of provider name → reason string.
    """

    def __init__(
        self,
        dataset: str,
        candidates: list[str] | None = None,
        rejection_reasons: dict[str, str] | None = None,
    ) -> None:
        self.dataset = dataset
        self.candidates = candidates or []
        self.rejection_reasons = rejection_reasons or {}
        msg = f"No healthy provider available for dataset '{dataset}'."
        if self.candidates:
            msg += f" Evaluated: {', '.join(self.candidates)}."
        super().__init__(msg)


class ProviderInCooldownError(VnstockPlatformError):
    """Raised when an explicitly requested provider is currently in cooldown.

    Args:
        provider_name: The provider name in cooldown.
        dataset: The requested dataset.
        cooldown_until: ISO-format timestamp when cooldown expires.
    """

    def __init__(
        self,
        provider_name: str,
        dataset: str,
        cooldown_until: str | None = None,
    ) -> None:
        self.provider_name = provider_name
        self.dataset = dataset
        self.cooldown_until = cooldown_until
        msg = f"Provider '{provider_name}' is in cooldown for dataset '{dataset}'."
        if cooldown_until:
            msg += f" Cooldown expires at {cooldown_until}."
        super().__init__(msg)


class ProviderDisabledError(VnstockPlatformError):
    """Raised when an explicitly requested provider is administratively disabled.

    Args:
        provider_name: The disabled provider name.
        dataset: The requested dataset.
        notes: Optional human-readable reason for disabling.
    """

    def __init__(
        self,
        provider_name: str,
        dataset: str,
        notes: str | None = None,
    ) -> None:
        self.provider_name = provider_name
        self.dataset = dataset
        self.notes = notes
        msg = f"Provider '{provider_name}' is disabled for dataset '{dataset}'."
        if notes:
            msg += f" Notes: {notes}"
        super().__init__(msg)
