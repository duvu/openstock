from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import pandas as pd

from vnstock.providers.fiinquantx.bridge import (
    SUPPORTED_VERSIONS,
    FiinQuantXState,
    load_fiinquantx_sdk,
)
from vnstock.providers.fiinquantx.exceptions import (
    FiinQuantXNotInstalledError,
    FiinQuantXProviderError,
    FiinQuantXVersionError,
)
from vnstock.providers.fiinquantx.normalize import normalize_membership, normalize_ohlcv
from vnstock.providers.fiinquantx.policy import (
    DOCUMENTED_DATASETS,
    IMPLEMENTED_DATASETS,
)
from vnstock.providers.fiinquantx.session import FiinQuantXSessionProvider

if TYPE_CHECKING:
    from vnstock.core.auth.spec import AuthSpec


class FiinQuantXProviderPlugin:
    name = "FIINQUANTX"

    def capabilities(self) -> dict[str, Any]:
        sdk = load_fiinquantx_sdk()
        return {
            dataset: {
                "supported": (
                    sdk.state is FiinQuantXState.INSTALLED_SUPPORTED
                    and dataset in IMPLEMENTED_DATASETS
                    and self._licensed_runtime_acknowledged()
                    and self._credentials_configured()
                ),
                "status": (
                    "experimental"
                    if dataset in IMPLEMENTED_DATASETS
                    and sdk.state is FiinQuantXState.INSTALLED_SUPPORTED
                    and self._licensed_runtime_acknowledged()
                    and self._credentials_configured()
                    else "unsupported"
                ),
                "auth_required": True,
                "explicit_only": True,
                "intervals": ["1D"],
                "notes": self._capability_note(dataset, sdk.state),
            }
            for dataset in sorted(DOCUMENTED_DATASETS)
        }

    def validate_params(self, dataset: str, params: dict[str, Any]) -> None:
        if dataset not in IMPLEMENTED_DATASETS:
            raise ValueError(f"Unsupported FiinQuantX dataset: {dataset}")
        if not params.get("symbol"):
            raise ValueError(f"'symbol' is required for dataset '{dataset}'")
        if (
            dataset in {"equity.ohlcv", "index.ohlcv"}
            and params.get("interval", "1D") != "1D"
        ):
            raise ValueError("FiinQuantX supports only verified interval '1D'.")
        if dataset in {"equity.ohlcv", "index.ohlcv"}:
            count_back = params.get("count_back", 100)
            if (
                isinstance(count_back, bool)
                or not isinstance(count_back, int)
                or not 1 <= count_back <= 10000
            ):
                raise ValueError("'count_back' must be an integer from 1 to 10000.")

    def fetch(self, dataset: str, params: dict[str, Any]) -> pd.DataFrame:
        self.validate_params(dataset, params)
        sdk = load_fiinquantx_sdk()
        if sdk.state is FiinQuantXState.NOT_INSTALLED:
            raise FiinQuantXNotInstalledError(dataset)
        if sdk.state is FiinQuantXState.UNTESTED_VERSION or sdk.module is None:
            raise FiinQuantXVersionError(dataset)
        try:
            session = FiinQuantXSessionProvider().get_session(sdk.module, dataset)
            if dataset in {"equity.ohlcv", "index.ohlcv"}:
                event = session.Fetch_Trading_Data(
                    realtime=False,
                    tickers=[str(params["symbol"]).upper()],
                    fields=["open", "high", "low", "close", "volume", "value"],
                    adjusted=bool(params.get("adjusted", True)),
                    by="1d",
                    period=params.get("count_back", 100),
                    lasted=bool(params.get("lasted", False)),
                )
                result = normalize_ohlcv(event.get_data(), dataset)
            else:
                result = normalize_membership(
                    session.TickerList(ticker=str(params["symbol"]).upper()),
                    str(params["symbol"]),
                )
        except FiinQuantXProviderError:
            raise
        except Exception:
            raise FiinQuantXProviderError(dataset) from None
        result.attrs.update(
            {
                "provider": self.name,
                "dataset": dataset,
                "sdk_version": sdk.version,
                "contract_version": SUPPORTED_VERSIONS[sdk.version],
                "adjusted": bool(params.get("adjusted", True)),
            }
        )
        if dataset in {
            "reference.index_membership_snapshot",
            "reference.sector_membership_snapshot",
        }:
            result.attrs["snapshot_semantics"] = "observed_current_membership"
        return result

    def diagnostics(self) -> dict[str, Any]:
        sdk = load_fiinquantx_sdk()
        return {
            "name": self.name,
            "state": sdk.state.value,
            "sdk_version": sdk.version,
            "contract_versions": dict(SUPPORTED_VERSIONS),
            "enabled_datasets": [
                dataset
                for dataset, capability in self.capabilities().items()
                if capability["supported"]
            ],
            "credentials_configured": self._credentials_configured(),
            "licensed_runtime_acknowledged": self._licensed_runtime_acknowledged(),
            "configured_limits": {"max_concurrency": 1, "max_rows": 10000},
        }

    @staticmethod
    def _licensed_runtime_acknowledged() -> bool:
        return os.environ.get("VNSTOCK_FIINQUANTX_LICENSED", "false").lower() in {
            "1",
            "true",
            "yes",
        }

    @staticmethod
    def _credentials_configured() -> bool:
        return bool(
            os.environ.get("FIINQUANT_USERNAME")
            and os.environ.get("FIINQUANT_PASSWORD")
        )

    def _capability_note(self, dataset: str, state: FiinQuantXState) -> str:
        if dataset not in IMPLEMENTED_DATASETS:
            return "Disabled until the licensed runtime contract is verified."
        if not self._licensed_runtime_acknowledged():
            return "Disabled until the licensed runtime is explicitly acknowledged."
        if not self._credentials_configured():
            return (
                "Disabled until both credential environment variables are configured."
            )
        if state is FiinQuantXState.INSTALLED_SUPPORTED:
            return "Bounded historical contract verified for SDK 0.1.64."
        return f"SDK runtime is unavailable ({state.value})."

    def auth_spec(self, dataset: str) -> "AuthSpec":
        from vnstock.core.auth.spec import AuthSpec
        from vnstock.core.auth.types import AuthType

        return AuthSpec(
            auth_type=AuthType.CUSTOM,
            required=True,
            explicit_only=True,
            scopes=(dataset,),
            notes="Credentials remain in local credential storage and are never data parameters.",
        )
