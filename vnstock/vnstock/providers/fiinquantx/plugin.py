from __future__ import annotations

import os
from datetime import date
from typing import TYPE_CHECKING, Any

import pandas as pd

from vnstock.providers.fiinquantx.approval import fiinquantx_license_approval
from vnstock.providers.fiinquantx.bridge import (
    SUPPORTED_VERSIONS,
    FiinQuantXState,
    load_fiinquantx_sdk,
)
from vnstock.providers.fiinquantx.exceptions import (
    FiinQuantXInvalidRequestError,
    FiinQuantXNotInstalledError,
    FiinQuantXProviderError,
    FiinQuantXVersionError,
    map_fiinquantx_exception,
)
from vnstock.providers.fiinquantx.normalize import normalize_membership, normalize_ohlcv
from vnstock.providers.fiinquantx.policy import (
    DOCUMENTED_DATASETS,
    IMPLEMENTED_DATASETS,
)
from vnstock.providers.fiinquantx.session import (
    DEFAULT_FIINQUANTX_SESSION_PROVIDER,
)

if TYPE_CHECKING:
    from vnstock.core.auth.spec import AuthSpec

_MAX_ROWS = 10_000
_MAX_RANGE_DAYS = 3_660


def _parse_iso_date(value: object, field: str) -> date | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError(f"'{field}' must be an ISO date string (YYYY-MM-DD).")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(
            f"'{field}' must be an ISO date string (YYYY-MM-DD)."
        ) from None


class FiinQuantXProviderPlugin:
    name = "FIINQUANTX"

    def capabilities(self) -> dict[str, Any]:
        sdk = load_fiinquantx_sdk()
        approval = fiinquantx_license_approval()
        runtime_ready = (
            sdk.state is FiinQuantXState.INSTALLED_SUPPORTED
            and approval.approved
            and self._credentials_configured()
        )
        return {
            dataset: {
                "supported": runtime_ready and dataset in IMPLEMENTED_DATASETS,
                "status": (
                    "experimental"
                    if runtime_ready and dataset in IMPLEMENTED_DATASETS
                    else "unsupported"
                ),
                "auth_required": True,
                "explicit_only": True,
                "intervals": ["1D"],
                "request_modes": (
                    ["count_back", "date_range"]
                    if dataset in {"equity.ohlcv", "index.ohlcv"}
                    else ["current_snapshot"]
                ),
                "notes": self._capability_note(dataset, sdk.state),
            }
            for dataset in sorted(DOCUMENTED_DATASETS)
        }

    def validate_params(self, dataset: str, params: dict[str, Any]) -> None:
        if dataset not in IMPLEMENTED_DATASETS:
            raise ValueError(f"Unsupported FiinQuantX dataset: {dataset}")
        allowed_params = {"symbol"}
        if dataset in {"equity.ohlcv", "index.ohlcv"}:
            allowed_params.update({"count_back", "interval", "start", "end"})
        unsupported_params = sorted(set(params) - allowed_params)
        if unsupported_params:
            raise ValueError(
                f"Unsupported FiinQuantX parameters: {', '.join(unsupported_params)}"
            )
        symbol = params.get("symbol")
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError(f"'symbol' is required for dataset '{dataset}'")
        if dataset not in {"equity.ohlcv", "index.ohlcv"}:
            return
        if params.get("interval", "1D") != "1D":
            raise ValueError("FiinQuantX supports only verified interval '1D'.")

        start = _parse_iso_date(params.get("start"), "start")
        end = _parse_iso_date(params.get("end"), "end")
        count_back = params.get("count_back")
        if start is not None and count_back is not None:
            raise ValueError("Use either 'count_back' or 'start'/'end', not both.")
        if end is not None and start is None:
            raise ValueError("'end' requires 'start'.")
        if start is not None and end is None:
            raise ValueError("'start' requires 'end' for a bounded date range.")
        if start is not None and end is not None:
            if end < start:
                raise ValueError("'end' must not be before 'start'.")
            if (end - start).days > _MAX_RANGE_DAYS:
                raise ValueError(
                    f"FiinQuantX date range must not exceed {_MAX_RANGE_DAYS} days."
                )
        if start is None:
            count_back = 100 if count_back is None else count_back
            if (
                isinstance(count_back, bool)
                or not isinstance(count_back, int)
                or not 1 <= count_back <= _MAX_ROWS
            ):
                raise ValueError(
                    f"'count_back' must be an integer from 1 to {_MAX_ROWS}."
                )

    def fetch(self, dataset: str, params: dict[str, Any]) -> pd.DataFrame:
        self.validate_params(dataset, params)
        sdk = load_fiinquantx_sdk()
        if sdk.state is FiinQuantXState.NOT_INSTALLED:
            raise FiinQuantXNotInstalledError(dataset)
        if sdk.state is FiinQuantXState.UNTESTED_VERSION or sdk.module is None:
            raise FiinQuantXVersionError(dataset)

        symbol = str(params["symbol"]).strip().upper()
        start = _parse_iso_date(params.get("start"), "start")
        end = _parse_iso_date(params.get("end"), "end")
        try:
            with DEFAULT_FIINQUANTX_SESSION_PROVIDER.request_session(
                sdk.module, dataset
            ) as session:
                if dataset in {"equity.ohlcv", "index.ohlcv"}:
                    request: dict[str, Any] = {
                        "realtime": False,
                        "tickers": [symbol],
                        "fields": [
                            "open",
                            "high",
                            "low",
                            "close",
                            "volume",
                            "value",
                        ],
                        "adjusted": True,
                        "by": "1d",
                        "lasted": False,
                    }
                    if start is not None:
                        request["from_date"] = start.isoformat()
                        request["to_date"] = end.isoformat() if end else None
                    else:
                        request["period"] = params.get("count_back", 100)
                    event = session.Fetch_Trading_Data(**request)
                    raw = event.get_data()
                else:
                    raw = session.TickerList(ticker=symbol)
        except FiinQuantXProviderError:
            raise
        except Exception as exc:  # noqa: BLE001 - vendor boundary
            raise map_fiinquantx_exception(exc, dataset) from None

        if dataset in {"equity.ohlcv", "index.ohlcv"}:
            result = normalize_ohlcv(raw, dataset)
            if not result.empty:
                result = result[result["symbol"] == symbol]
                if start is not None:
                    result = result[result["time"].dt.date >= start]
                if end is not None:
                    result = result[result["time"].dt.date <= end]
                result = result.sort_values("time")
                if start is None:
                    result = result.tail(int(params.get("count_back", 100)))
                result = result.reset_index(drop=True)
            if len(result) > _MAX_ROWS:
                raise FiinQuantXInvalidRequestError(dataset)
        else:
            result = normalize_membership(raw, symbol)

        result.attrs.update(
            {
                "provider": self.name,
                "dataset": dataset,
                "sdk_version": sdk.version,
                "contract_version": SUPPORTED_VERSIONS[sdk.version],
            }
        )
        if dataset in {"equity.ohlcv", "index.ohlcv"}:
            result.attrs["ohlcv_request_policy"] = {
                "adjusted": "requested_true",
                "lasted": "requested_false",
                "mode": "date_range" if start is not None else "count_back",
                "start": start.isoformat() if start else None,
                "end": end.isoformat() if end else None,
            }
        if dataset in {
            "reference.index_membership_snapshot",
            "reference.sector_membership_snapshot",
        }:
            result.attrs["snapshot_semantics"] = "observed_current_membership"
        return result

    def diagnostics(self) -> dict[str, Any]:
        sdk = load_fiinquantx_sdk()
        runtime = DEFAULT_FIINQUANTX_SESSION_PROVIDER.diagnostics()
        approval = fiinquantx_license_approval()
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
            "licensed_runtime_acknowledged": approval.acknowledged,
            "licensed_runtime_approved": approval.approved,
            "license_approval_reference_configured": approval.reference_configured,
            "license_approval_reference_fingerprint": approval.reference_fingerprint,
            "configured_limits": {
                "max_concurrency": runtime["max_concurrency"],
                "max_rows": _MAX_ROWS,
                "max_range_days": _MAX_RANGE_DAYS,
                "requests_per_second": None,
                "quota": "vendor contract not verified",
            },
            "runtime": runtime,
            "ohlcv_request_policy": {
                "adjusted": "requested_true",
                "lasted": "requested_false",
                "supported_modes": ["count_back", "date_range"],
            },
        }

    @staticmethod
    def _licensed_runtime_acknowledged() -> bool:
        return fiinquantx_license_approval().acknowledged

    @staticmethod
    def _licensed_runtime_approved() -> bool:
        return fiinquantx_license_approval().approved

    @staticmethod
    def _credentials_configured() -> bool:
        return bool(
            os.environ.get("FIINQUANT_USERNAME")
            and os.environ.get("FIINQUANT_PASSWORD")
        )

    def _capability_note(self, dataset: str, state: FiinQuantXState) -> str:
        approval = fiinquantx_license_approval()
        if dataset not in IMPLEMENTED_DATASETS:
            return "Disabled until the licensed runtime contract is verified."
        if not approval.acknowledged:
            return "Disabled until the licensed runtime is explicitly acknowledged."
        if not approval.reference_configured:
            return "Disabled until a reviewed license approval reference is configured."
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
