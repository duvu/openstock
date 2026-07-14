from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd

from vnstock.core.provider.exceptions import ProviderDisabledError
from vnstock.providers.fiinquantx.bridge import SUPPORTED_VERSIONS, load_fiinquantx_sdk
from vnstock.providers.fiinquantx.policy import ENABLED_DATASETS

if TYPE_CHECKING:
    from vnstock.core.auth.spec import AuthSpec


class FiinQuantXProviderPlugin:
    name = "FIINQUANTX"

    def capabilities(self) -> dict[str, Any]:
        return {
            dataset: {
                "supported": False,
                "status": "unsupported",
                "auth_required": True,
                "explicit_only": True,
                "intervals": ["1D"],
                "notes": "Disabled until licensed runtime evidence enables this contract.",
            }
            for dataset in sorted(ENABLED_DATASETS)
        }

    def validate_params(self, dataset: str, params: dict[str, Any]) -> None:
        if dataset not in ENABLED_DATASETS:
            raise ValueError(f"Unsupported FiinQuantX dataset: {dataset}")
        if dataset in {"equity.ohlcv", "index.ohlcv"} and not params.get("symbol"):
            raise ValueError(f"'symbol' is required for dataset '{dataset}'")

    def fetch(self, dataset: str, params: dict[str, Any]) -> pd.DataFrame:
        self.validate_params(dataset, params)
        sdk = load_fiinquantx_sdk()
        raise ProviderDisabledError(
            self.name,
            dataset,
            notes=f"Runtime evidence is required before enabling FiinQuantX ({sdk.state.value}).",
        )

    def diagnostics(self) -> dict[str, Any]:
        sdk = load_fiinquantx_sdk()
        return {
            "name": self.name,
            "state": sdk.state.value,
            "sdk_version": sdk.version,
            "contract_versions": dict(SUPPORTED_VERSIONS),
            "enabled_datasets": [],
            "configured_limits": {"max_concurrency": 1, "max_rows": 10000},
        }

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
