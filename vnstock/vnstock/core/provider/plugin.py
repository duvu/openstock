"""
ProviderPlugin interface for vnstock provider plugins.

A ProviderPlugin is a typed Protocol that all internal provider adapters
should conform to. It exposes:

- provider name
- capability declaration (by dataset)
- dataset fetch
- parameter validation
- diagnostics
- auth spec (Phase 4)

Allowed capability status values:

    stable        Provider is production-ready and tested.
    experimental  Provider is functional but API may change.
    partial       Provider supports a subset of the dataset.
    deprecated    Provider is marked for removal in a future version.
    unsupported   Provider explicitly does not support this dataset.

Usage::

    from vnstock.core.provider.plugin import ProviderPlugin

    class MyProvider:
        name = "MY_PROVIDER"

        def capabilities(self) -> dict:
            return {
                "equity.ohlcv": {
                    "supported": True,
                    "status": "stable",
                    "auth_required": False,
                    "intervals": ["1D", "1W"],
                    "notes": "Historical OHLCV.",
                }
            }

        def fetch(self, dataset: str, params: dict) -> pd.DataFrame:
            ...

        def validate_params(self, dataset: str, params: dict) -> None:
            ...

        def diagnostics(self) -> dict:
            ...

        def auth_spec(self, dataset: str) -> "AuthSpec":
            from vnstock.core.auth.spec import AuthSpec
            return AuthSpec.no_auth()
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import pandas as pd

if TYPE_CHECKING:
    from vnstock.core.auth.spec import AuthSpec

#: Allowed capability status values for provider dataset capabilities.
CAPABILITY_STATUSES: frozenset[str] = frozenset(
    {
        "stable",
        "experimental",
        "partial",
        "deprecated",
        "unsupported",
    }
)


@runtime_checkable
class ProviderPlugin(Protocol):
    """Protocol interface for vnstock provider plugins.

    All provider adapters used by the new plugin-based routing path
    must conform to this protocol.

    Attributes:
        name: Short uppercase provider identifier, e.g. ``"KBS"``.
    """

    name: str

    def capabilities(self) -> dict[str, Any]:
        """Return capability metadata keyed by dataset name.

        The returned dict maps dataset names to capability descriptors.

        Example::

            {
                "equity.ohlcv": {
                    "supported": True,
                    "status": "stable",       # one of CAPABILITY_STATUSES
                    "auth_required": False,
                    "intervals": ["1D", "1W", "1M"],
                    "notes": "Default OHLCV provider.",
                }
            }

        Returns:
            Mapping of dataset name → capability descriptor dict.
        """
        ...

    def fetch(self, dataset: str, params: dict[str, Any]) -> pd.DataFrame:
        """Fetch data for *dataset* with *params*.

        Args:
            dataset: Dotted dataset name, e.g. ``"equity.ohlcv"``.
            params: Provider-specific parameters.

        Returns:
            A :class:`pandas.DataFrame` normalised to the dataset contract.

        Raises:
            UnsupportedDatasetForProviderError: If this provider does not
                support *dataset*.
            ProviderFetchError: On network or parsing failure.
        """
        ...

    def validate_params(self, dataset: str, params: dict[str, Any]) -> None:
        """Validate *params* for *dataset*.

        Args:
            dataset: Dotted dataset name.
            params: Parameters to validate.

        Raises:
            ValueError: If any parameter is invalid.
        """
        ...

    def diagnostics(self) -> dict[str, Any]:
        """Return provider health/diagnostics metadata.

        Returns:
            Dict with provider-specific health information.
        """
        ...

    def auth_spec(self, dataset: str) -> "AuthSpec":
        """Return the auth requirements for *dataset*.

        All providers must implement this method. Public providers should
        return ``AuthSpec.no_auth()``. Providers requiring authentication
        should return an appropriate ``AuthSpec``.

        Args:
            dataset: Dotted dataset name, e.g. ``"equity.ohlcv"``.

        Returns:
            :class:`~vnstock.core.auth.spec.AuthSpec` describing auth requirements.
        """
        ...
