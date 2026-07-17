"""
PluginRuntime — central execution path for dataset fetches.

Execution flow::

    DatasetRequest
        → resolve DatasetContract (if validate=True)
        → PluginRouter.resolve(dataset, source)
        → provider.validate_params(dataset, params)
        → provider.fetch(dataset, params)
        → record_success / typed record_failure on health store
        → wrap result in DataResult
        → return DataFrame (or DataResult when return_result=True)
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import pandas as pd

from vnstock.core.auth.redaction import is_sensitive_key, redact_dict
from vnstock.core.provider.exceptions import (
    DatasetContractError,
    ProviderFetchError,
    VnstockPlatformError,
)
from vnstock.core.provider.health import (
    DEFAULT_HEALTH_STORE,
    InMemoryProviderHealthStore,
)
from vnstock.core.provider.plugin_router import PluginRouter
from vnstock.core.provider.routing import RoutingPolicy
from vnstock.core.result import DataResult
from vnstock.core.runtime.request import DatasetRequest

if TYPE_CHECKING:
    from vnstock.core.contracts.base import DatasetContractRegistry
    from vnstock.core.provider.plugin_registry import PluginRegistry

_NON_HEALTH_FAILURE_KINDS = frozenset(
    {
        "not_installed",
        "untested_version",
        "license_not_acknowledged",
        "credentials_missing",
        "authentication",
        "entitlement",
        "quota",
        "invalid_request",
    }
)
_COOLDOWN_FAILURE_KINDS = frozenset({"rate_limit", "concurrency", "transient"})


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _dtype_matches(series: pd.Series, expected_dtype: Any) -> bool:
    expected = str(expected_dtype)
    actual = series.dtype
    if expected == "string":
        if pd.api.types.is_object_dtype(actual):
            return bool(series.dropna().map(lambda value: isinstance(value, str)).all())
        return bool(pd.api.types.is_string_dtype(actual))
    if expected == "float64":
        return bool(
            pd.api.types.is_numeric_dtype(actual)
            and not pd.api.types.is_bool_dtype(actual)
        )
    if expected == "int64":
        return bool(
            pd.api.types.is_integer_dtype(actual)
            and not pd.api.types.is_bool_dtype(actual)
        )
    if expected == "datetime64[ns]":
        return bool(
            pd.api.types.is_datetime64_any_dtype(actual)
            and not isinstance(actual, pd.DatetimeTZDtype)
        )
    if expected == "datetime64[ns, UTC]":
        return bool(
            isinstance(actual, pd.DatetimeTZDtype) and str(actual.tz).upper() == "UTC"
        )
    return bool(pd.api.types.is_dtype_equal(actual, expected_dtype))


def _failure_kind(exc: BaseException) -> str | None:
    value = getattr(exc, "kind", None)
    if value is None:
        return None
    raw = getattr(value, "value", value)
    normalized = str(raw).strip().lower()
    return normalized or None


def _record_failure_for_exception(
    router: PluginRouter,
    provider: str,
    dataset: str,
    exc: BaseException,
) -> None:
    """Update provider health only when the failure represents provider health.

    Installation, credentials, authentication, entitlement, quota and invalid
    request failures are deployment/account/request states. They must fail the
    explicit request but must not poison provider health for other operators.
    Transient, concurrency and rate-limit failures enter an immediate bounded
    cooldown. Untyped legacy provider errors preserve the previous behavior.
    """

    kind = _failure_kind(exc)
    if kind in _NON_HEALTH_FAILURE_KINDS:
        return
    if kind in _COOLDOWN_FAILURE_KINDS:
        router.record_failure(
            provider,
            dataset,
            notes=f"typed_provider_failure:{kind}",
            failure_threshold=1,
            cooldown_seconds=30.0,
        )
        return
    router.record_failure(
        provider,
        dataset,
        notes=(
            f"typed_provider_failure:{kind}"
            if kind is not None
            else f"ProviderFetchError in runtime for dataset '{dataset}'"
        ),
    )


class PluginRuntime:
    """Central execution engine for the vnstock plugin platform."""

    def __init__(
        self,
        registry: "PluginRegistry",
        *,
        contract_registry: "DatasetContractRegistry | None" = None,
        health_store: InMemoryProviderHealthStore | None = None,
        policy: RoutingPolicy | None = None,
        runtime_path: str = "plugin_runtime",
    ) -> None:
        self.registry = registry
        self._contract_registry = contract_registry
        self.health_store = (
            health_store if health_store is not None else DEFAULT_HEALTH_STORE
        )
        self.policy = policy or RoutingPolicy.default()
        self.runtime_path = runtime_path
        self._router = PluginRouter(
            registry=registry,
            health_store=self.health_store,
            policy=self.policy,
        )

    def fetch(
        self,
        dataset: str,
        params: dict[str, Any] | None = None,
        *,
        source: str | None = None,
        validate: bool = False,
        quality_mode: str = "warn",
        return_result: bool = False,
    ) -> pd.DataFrame | DataResult:
        """Fetch a dataset using an explicit source or the router policy."""

        request = DatasetRequest(
            dataset=dataset,
            params=params or {},
            source=source,
            validate=validate,
            quality_mode=quality_mode,
            return_result=return_result,
        )
        return self._execute(request)

    def fetch_request(self, request: DatasetRequest) -> pd.DataFrame | DataResult:
        """Execute a pre-built request."""

        return self._execute(request)

    def _execute(self, request: DatasetRequest) -> pd.DataFrame | DataResult:
        dataset = request.dataset
        params = dict(request.params)
        source = request.source

        start_ts = time.monotonic()
        provider = self._router.resolve(dataset, source=source, params=params)
        routing_decision = self._router.last_decision
        fiinquantx_request = provider.name.strip().upper() == "FIINQUANTX"
        validate = request.validate or fiinquantx_request
        quality_mode = "strict" if fiinquantx_request else request.quality_mode

        try:
            provider.validate_params(dataset, params)
        except ValueError as exc:
            raise VnstockPlatformError(
                f"Invalid parameters for dataset '{dataset}' on provider "
                f"'{provider.name}': {exc}"
            ) from exc

        latency_ms: float | None = None
        try:
            df = provider.fetch(dataset, params)
            latency_ms = (time.monotonic() - start_ts) * 1000
        except ProviderFetchError as exc:
            _record_failure_for_exception(
                self._router,
                provider.name,
                dataset,
                exc,
            )
            raise
        except VnstockPlatformError:
            self._router.record_failure(
                provider.name,
                dataset,
                notes=f"VnstockPlatformError in runtime for dataset '{dataset}'",
            )
            raise
        except Exception as exc:
            self._router.record_failure(
                provider.name,
                dataset,
                notes=f"unexpected_provider_failure:{type(exc).__name__}",
            )
            raise ProviderFetchError(provider.name, dataset, cause=exc) from exc

        quality_status: str | None = None
        quality_report: dict[str, Any] = {}
        contract_errors: list[str] = []

        if validate:
            contract_errors = self._validate_contract(
                df,
                dataset,
                provider=provider.name,
                params=params,
                strict=quality_mode == "strict",
            )
            if contract_errors:
                quality_status = "FAIL"
                quality_report = {"contract_errors": contract_errors}
                if quality_mode == "strict":
                    self._router.record_failure(
                        provider.name,
                        dataset,
                        notes=f"Contract validation failed: {contract_errors}",
                    )
                    raise DatasetContractError(
                        dataset,
                        message=f"Contract validation failed: {contract_errors}",
                    )
            else:
                quality_status = "PASS"
                quality_report = {"contract_errors": []}

        self._router.record_success(provider.name, dataset, latency_ms=latency_ms)

        diagnostics = self._build_diagnostics(
            routing_decision=routing_decision,
            provider_diagnostics=provider.diagnostics(),
            latency_ms=latency_ms,
            contract_errors=contract_errors,
            provider_name=provider.name,
        )
        provider_lineage = _safe_provider_lineage(df.attrs)
        if provider_lineage:
            diagnostics["provider_lineage"] = provider_lineage

        result = DataResult(
            dataset=dataset,
            provider=provider.name,
            data=df,
            quality_status=quality_status,
            quality_report=quality_report or None,
            diagnostics=diagnostics,
            fetched_at=datetime.now(tz=timezone.utc).replace(tzinfo=None),
        )
        result.diagnostics["runtime_path"] = self.runtime_path  # type: ignore[index]

        if request.return_result:
            return result
        return result.to_dataframe()

    def _validate_contract(
        self,
        df: pd.DataFrame,
        dataset: str,
        *,
        provider: str,
        params: dict[str, Any],
        strict: bool,
    ) -> list[str]:
        registry = self._get_contract_registry()
        try:
            contract = registry.get(dataset)
        except KeyError:
            return [f"No contract registered for dataset '{dataset}'"] if strict else []

        errors: list[str] = []
        missing = [
            column for column in contract.required_columns if column not in df.columns
        ]
        if missing:
            errors.append(f"Missing required columns: {missing}")
        for column, expected_dtype in contract.dtype_rules.items():
            if column not in df.columns:
                continue
            actual_dtype = df[column].dtype
            if not _dtype_matches(df[column], expected_dtype):
                errors.append(
                    f"Column '{column}' dtype is '{actual_dtype}', expected "
                    f"'{expected_dtype}'"
                )
        if contract.validator is not None and not missing and not df.empty:
            from vnstock.core.quality.registry import validate_dataframe

            try:
                report = validate_dataframe(
                    df,
                    contract.validator,
                    provider=provider,
                    symbol=_optional_text(params.get("symbol")),
                    interval=_optional_text(params.get("interval")),
                )
            except ValueError as exc:
                errors.append(str(exc))
            else:
                errors.extend(
                    f"{issue.code}: {issue.message}" for issue in report.errors
                )
        return errors

    def _get_contract_registry(self) -> "DatasetContractRegistry":
        if self._contract_registry is not None:
            return self._contract_registry
        from vnstock.core.contracts import CONTRACT_REGISTRY

        return CONTRACT_REGISTRY

    def _build_diagnostics(
        self,
        *,
        routing_decision: Any,
        provider_diagnostics: dict[str, Any],
        latency_ms: float | None,
        contract_errors: list[str],
        provider_name: str = "",
    ) -> dict[str, Any]:
        diag: dict[str, Any] = {}
        if routing_decision is not None:
            diag["routing"] = routing_decision.to_dict()
        if latency_ms is not None:
            diag["latency_ms"] = round(latency_ms, 2)
        if contract_errors:
            diag["contract_errors"] = contract_errors
        redacted_provider_diag = redact_dict(provider_diagnostics)
        safe_provider_diag = {
            key: value
            for key, value in redacted_provider_diag.items()
            if not is_sensitive_key(key)
        }
        if safe_provider_diag:
            diag["provider_diagnostics"] = safe_provider_diag

        try:
            from vnstock.core.auth.diagnostics import AuthDiagnostics

            auth_ctx = provider_diagnostics.get("auth_context")
            if auth_ctx is not None:
                diag["auth"] = AuthDiagnostics.from_context(auth_ctx).to_dict()
            else:
                diag["auth"] = AuthDiagnostics.unauthenticated(provider_name).to_dict()
        except Exception:
            diag["auth"] = {"auth_used": False, "auth_type": "none"}
        return diag


def _safe_provider_lineage(attrs: dict[str, Any]) -> dict[str, Any]:
    lineage: dict[str, Any] = {}
    for key in (
        "sdk_version",
        "contract_version",
        "source_method",
        "source_query",
        "snapshot_semantics",
    ):
        value = attrs.get(key)
        if isinstance(value, (str, int, float, bool)) or value is None:
            if value is not None:
                lineage[key] = value
    request_policy = attrs.get("ohlcv_request_policy")
    if isinstance(request_policy, dict):
        safe_policy = {
            key: value
            for key, value in request_policy.items()
            if key in {"adjusted", "basis", "lasted", "mode", "start", "end"}
            and (isinstance(value, (str, int, float, bool)) or value is None)
        }
        if safe_policy:
            lineage["ohlcv_request_policy"] = safe_policy
    return lineage
