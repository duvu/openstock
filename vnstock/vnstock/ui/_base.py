from __future__ import annotations

from typing import Any

import pandas as pd


def _is_rate_limit(exc: Exception) -> bool:
    """Return True if *exc* looks like an HTTP 429 / rate-limit error."""
    msg = " ".join(str(a) for a in exc.args).lower()
    return "429" in msg or "rate limit" in msg or "too many requests" in msg


class BaseUI:
    """Base class for all UI modules."""

    def _dispatch(self, domain_name: str, method_name: str, *args, **kwargs) -> Any:
        """
        Dispatch the message to native providers/connectors.
        Automatically rotates providers via the load-balancer router when a
        POOLS entry exists and the caller did not explicitly pass source=.
        """
        from vnstock.ui._registry import MAP

        if domain_name not in MAP or method_name not in MAP[domain_name]:
            raise AttributeError(
                f"Method '{method_name}' not implemented for domain '{domain_name}'"
            )

        meta = MAP[domain_name][method_name]

        # 1. Handle nested sub-domains (e.g., Market -> equity -> ohlcv)
        consumed_subdomain: str | None = None
        if isinstance(meta, dict) and args:
            actual_method = args[0]
            if actual_method in meta:
                consumed_subdomain = actual_method
                meta = meta[actual_method]
                args = args[1:]
            else:
                raise AttributeError(
                    f"Method '{actual_method}' not found in sub-domain "
                    f"'{method_name}' of '{domain_name}'"
                )

        # 2. Handle redirection tuples (length 2)
        if isinstance(meta, tuple) and len(meta) == 2:
            redirect_domain, redirect_method = meta
            return self._dispatch(redirect_domain, redirect_method, *args, **kwargs)

        # 3. Standard Metadata Unpack
        try:
            module_type = meta[0]
            sub_module = meta[1]
            class_name = meta[2]
            function_name = meta[3]
        except (IndexError, TypeError) as e:
            raise AttributeError(
                f"Invalid registry entry for '{domain_name}.{method_name}'. Got: {meta}"
            ) from e

        # Record whether the caller explicitly passed source= BEFORE we apply the MAP default.
        _caller_set_source: bool = "source" in kwargs and kwargs["source"] is not None

        # Apply MAP default source when caller did not provide one.
        if len(meta) > 4 and not _caller_set_source:
            kwargs["source"] = meta[4]

        # 3b. Pop cache control kwargs before they leak into provider calls.
        _use_cache = kwargs.pop("use_cache", None)
        _cache_ttl = kwargs.pop("cache_ttl", None)

        # 3b2. Pop quality control kwargs before they leak into provider calls.
        # Honour per-call overrides; fall back to global QualityConfig defaults.
        from vnstock.core.settings import get_config as _get_config

        _quality_cfg = _get_config().quality
        _validate: bool = kwargs.pop("validate", _quality_cfg.enabled)
        _quality_mode: str = kwargs.pop("quality_mode", _quality_cfg.mode)

        # 3c. Load-balancer: override source via router when caller did not specify.
        _using_router = False
        _pool_key: tuple | None = None
        _pool_providers: list[str] = []

        if not _caller_set_source:
            from vnstock.core.router import router
            from vnstock.ui._pools import POOLS, _build_pool_key

            _pool_key = _build_pool_key(domain_name, method_name, consumed_subdomain)
            if _pool_key in POOLS:
                _pool_providers = POOLS[_pool_key]
                kwargs["source"] = router.pick(_pool_key, _pool_providers)
                _using_router = True

        # 3d. Cache lookup (skip when use_cache=False).
        _cache_manager = None
        _cache_key: str | None = None
        _smart_ttl: int = -1
        if _use_cache is not False:
            try:
                from vnstock.core.cache import (
                    get_cache_manager,
                    get_default_ttl,
                    make_cache_key,
                )

                _cache_manager = get_cache_manager()
                if _cache_manager.config.enabled:
                    _smart_ttl = get_default_ttl(
                        domain_name,
                        consumed_subdomain or "",
                        function_name,
                    )
                    _cache_key = make_cache_key(
                        kwargs.get("source", ""),
                        function_name,
                        {
                            "symbol": getattr(self, "symbol", None),
                            "args": list(args),
                            **{
                                k: v
                                for k, v in kwargs.items()
                                if k not in ("source", "random_agent", "show_log")
                            },
                        },
                        domain=domain_name,
                        subdomain=consumed_subdomain or "",
                    )
                    _cached = _cache_manager.get(_cache_key)
                    if _cached is not None:
                        return _cached
            except Exception:
                # Cache errors must never break normal operation
                _cache_manager = None
                _cache_key = None

        # 4. Multi-symbol Handling (Universal)
        symbol = getattr(self, "symbol", None)
        if isinstance(symbol, list) and module_type == "api":
            all_results = []
            for s in symbol:
                temp_inst = type(self)(symbol=s)
                res = temp_inst._dispatch(domain_name, method_name, *args, **kwargs)
                all_results.append(res)
            if all_results and isinstance(all_results[0], pd.DataFrame):
                return pd.concat(all_results).reset_index(drop=True)
            return all_results

        # 5. Native dispatch (with retry loop when router is active)
        max_attempts = len(_pool_providers) if _using_router and _pool_providers else 1
        last_exc: Exception | None = None

        for attempt in range(max_attempts):
            try:
                result = self._execute_dispatch(
                    module_type,
                    sub_module,
                    class_name,
                    function_name,
                    symbol,
                    args,
                    kwargs,
                )
                if _using_router and isinstance(result, pd.DataFrame):
                    result.attrs["source_used"] = kwargs.get("source", "")

                # Write to cache on success (skip when use_cache=False).
                if (
                    _use_cache is not False
                    and _cache_manager is not None
                    and _cache_key is not None
                ):
                    try:
                        if isinstance(_cache_ttl, int):
                            ttl = _cache_ttl  # explicit per-call override
                        elif _smart_ttl > 0:
                            ttl = _smart_ttl  # smart TTL from data category
                        else:
                            ttl = _cache_manager.config.ttl  # global fallback
                        _cache_manager.set(_cache_key, result, ttl)
                    except Exception:
                        pass  # cache write errors must never break the response

                # Optional quality validation
                if _validate and isinstance(result, pd.DataFrame):
                    result = _run_quality_validation(
                        result,
                        domain_name=domain_name,
                        method_name=method_name,
                        consumed_subdomain=consumed_subdomain,
                        quality_mode=_quality_mode,
                        provider=kwargs.get("source", ""),
                        symbol=getattr(self, "symbol", None),
                    )

                return result

            except Exception as exc:
                retriable = _is_retriable(exc)
                if _using_router and retriable and _pool_key and _pool_providers:
                    from vnstock.core.router import router
                    from vnstock.ui._pools import POOLS

                    router.mark_failed(_pool_key, kwargs["source"], _is_rate_limit(exc))
                    if attempt < max_attempts - 1:
                        kwargs["source"] = router.pick(_pool_key, _pool_providers)
                        last_exc = exc
                        continue
                raise

        if last_exc is not None:
            raise last_exc  # type: ignore[misc]

        # Should never reach here
        raise AttributeError(
            f"Method '{method_name}' not implemented for domain '{domain_name}'"
        )

    def _plugin_dispatch(
        self,
        dataset: str,
        params: dict | None = None,
        *,
        source: str | None = None,
        validate: bool = False,
        quality_mode: str = "warn",
        return_result: bool = False,
        allow_legacy_fallback: bool = False,
    ) -> Any:
        """Route a dataset request through the :class:`PluginRuntime`.

        This is the fail-closed routing boundary for migrated canonical
        datasets. A migrated dataset either serves the request through its
        canonical provider contract or raises a *typed* failure; it never
        silently drops into legacy explorer dispatch.

        Args:
            dataset: Dotted dataset name, e.g. ``"equity.ohlcv"``.
            params: Fetch parameters.
            source: Explicit provider name or ``None`` for auto selection.
            validate: Validate output against the DatasetContract.
            quality_mode: Quality validation mode (``"off"`` / ``"warn"`` /
                ``"strict"``).
            return_result: Return :class:`DataResult` instead of DataFrame.
            allow_legacy_fallback: Opt-in compatibility boundary for genuinely
                *non-migrated* capabilities. When ``True`` **and** no explicit
                ``source`` was requested, a capability-absence signal
                (:class:`UnsupportedDatasetError` /
                :class:`NoProviderForDatasetError`) causes this method to return
                ``None`` so the caller can re-route through :meth:`_dispatch`.
                All other failures — authentication, entitlement, rate limit,
                invalid request, schema/contract drift, cooldown, disabled
                provider and provider fetch errors — always propagate as typed
                exceptions. Explicit provider selection never falls back.

        Returns:
            :class:`pandas.DataFrame` or :class:`DataResult`, or ``None`` only
            when a non-migrated capability was requested with
            ``allow_legacy_fallback=True`` and no explicit ``source``.
        """
        from vnstock.core.provider.exceptions import (
            NoProviderForDatasetError,
            UnsupportedDatasetError,
        )
        from vnstock.core.runtime import default_runtime

        try:
            rt = default_runtime()
            return rt.fetch(
                dataset,
                params or {},
                source=source,
                validate=validate,
                quality_mode=quality_mode,
                return_result=return_result,
            )
        except (UnsupportedDatasetError, NoProviderForDatasetError) as _exc:
            # Capability-absence: the plugin platform has no provider for this
            # dataset at all. This is the only signal that may cross the
            # compatibility boundary, and only for auto-selected (no explicit
            # source) non-migrated capabilities.
            explicit_source = source is not None
            if allow_legacy_fallback and not explicit_source:
                import warnings as _w

                _w.warn(
                    f"COMPAT_LEGACY_DISPATCH: dataset '{dataset}' has no plugin "
                    f"provider ({type(_exc).__name__}); routing through the "
                    "non-canonical legacy explorer path. This capability is not "
                    "yet migrated to a canonical dataset contract.",
                    RuntimeWarning,
                    stacklevel=2,
                )
                return None  # Caller must handle None by re-routing via _dispatch
            raise

    def _execute_dispatch(
        self,
        module_type: str,
        sub_module: str,
        class_name: str | None,
        function_name: str,
        symbol: Any,
        args: tuple,
        kwargs: dict,
    ) -> Any:
        """Instantiate the provider class and invoke the target function."""
        import importlib
        import inspect

        if module_type == "api":
            module = importlib.import_module(f"vnstock.{sub_module}")
            if class_name:
                cls = getattr(module, class_name)
                sig = inspect.signature(cls.__init__)

                init_kwargs: dict = {}
                for param in [
                    "symbol",
                    "symbol_id",
                    "source",
                    "random_agent",
                    "show_log",
                ]:
                    if param in sig.parameters:
                        if param in ["symbol", "symbol_id"]:
                            init_kwargs[param] = symbol
                        elif param in kwargs:
                            init_kwargs[param] = kwargs.pop(param)

                obj = cls(**init_kwargs)
                func = getattr(obj, function_name)

                func_sig = inspect.signature(func)
                has_kwargs = any(
                    p.kind == p.VAR_KEYWORD for p in func_sig.parameters.values()
                )
                clean_kwargs = {
                    k: v
                    for k, v in kwargs.items()
                    if k not in ["source", "random_agent", "show_log"]
                }
                if not has_kwargs:
                    clean_kwargs = {
                        k: v
                        for k, v in clean_kwargs.items()
                        if k in func_sig.parameters
                    }

                if symbol:
                    consumed_by_init = "symbol" in sig.parameters
                    in_kwargs = any(
                        k in clean_kwargs
                        for k in ["symbol", "group", "code", "ticker", "query"]
                    )
                    if not consumed_by_init and not in_kwargs and not args:
                        if "symbol" in func_sig.parameters or has_kwargs:
                            return func(symbol, *args, **clean_kwargs)

                return func(*args, **clean_kwargs)

            else:
                func = getattr(module, function_name)
                func_sig = inspect.signature(func)
                has_kwargs = any(
                    p.kind == p.VAR_KEYWORD for p in func_sig.parameters.values()
                )
                clean_kwargs = {
                    k: v
                    for k, v in kwargs.items()
                    if k not in ["source", "random_agent", "show_log"]
                }
                if not has_kwargs:
                    clean_kwargs = {
                        k: v
                        for k, v in clean_kwargs.items()
                        if k in func_sig.parameters
                    }
                return func(*args, **clean_kwargs)

        elif module_type == "explorer":
            module = importlib.import_module(f"vnstock.explorer.{sub_module}")
            if class_name:
                cls = getattr(module, class_name)
                try:
                    sig = inspect.signature(cls.__init__)
                    init_kwargs = {}
                    for param in ["symbol", "symbol_id", "random_agent", "show_log"]:
                        if param in sig.parameters:
                            if param in ["symbol", "symbol_id"]:
                                init_kwargs[param] = symbol
                            elif param in kwargs:
                                init_kwargs[param] = kwargs.pop(param)
                    obj = cls(**init_kwargs)
                except (ValueError, TypeError):
                    obj = cls()
                func = getattr(obj, function_name)
            else:
                func = getattr(module, function_name)

            func_sig = inspect.signature(func)
            has_kwargs = any(
                p.kind == p.VAR_KEYWORD for p in func_sig.parameters.values()
            )
            clean_kwargs = {
                k: v
                for k, v in kwargs.items()
                if k not in ["source", "random_agent", "show_log"]
            }
            if not has_kwargs:
                clean_kwargs = {
                    k: v for k, v in clean_kwargs.items() if k in func_sig.parameters
                }
            return func(*args, **clean_kwargs)

        elif module_type == "connector":
            module = importlib.import_module(f"vnstock.connector.{sub_module}")
            cls = getattr(module, class_name)
            obj = cls()
            return getattr(obj, function_name)(*args, **kwargs)

        raise AttributeError(f"Unknown module_type '{module_type}'")


def _is_retriable(exc: Exception) -> bool:
    """Return True if *exc* is a transient error worth retrying."""
    try:
        import requests

        if isinstance(
            exc,
            (requests.exceptions.Timeout, requests.exceptions.ConnectionError),
        ):
            return True
    except ImportError:
        pass

    if isinstance(exc, (ValueError, RuntimeError)):
        msg = str(exc).lower()
        return any(
            m in msg
            for m in ("429", "rate limit", "too many requests", "503", "502", "500")
        )
    return False


class BaseDetailUI(BaseUI):
    """Base class for detail UI modules (e.g. Reference().company('VNM'))"""

    def __init__(self, symbol: str = None, **kwargs):
        self.symbol = symbol
        self.params = kwargs


# ---------------------------------------------------------------------------
# Quality validation helper (internal)
# ---------------------------------------------------------------------------

_DOMAIN_TO_DATASET_TYPE: dict[str, dict[str, str]] = {
    # domain_name -> {subdomain / method_name -> dataset_type}
    "Market": {
        "ohlcv": "ohlcv",
        "price_board": "price_board",
        "intraday": "intraday_trades",
    },
}


def _infer_dataset_type(
    domain_name: str,
    method_name: str,
    consumed_subdomain: str | None,
) -> str | None:
    """Return a dataset_type string or None when the method is not mapped."""
    domain_map = _DOMAIN_TO_DATASET_TYPE.get(domain_name, {})
    # Try subdomain first, then method_name
    key = consumed_subdomain or method_name
    return domain_map.get(key)


def _run_quality_validation(
    df: pd.DataFrame,
    *,
    domain_name: str,
    method_name: str,
    consumed_subdomain: str | None,
    quality_mode: str,
    provider: str | None,
    symbol: Any | None,
) -> pd.DataFrame:
    """Run quality validation and optionally raise or attach report.

    Args:
        df: DataFrame to validate.
        domain_name: UI domain (e.g. ``"Market"``).
        method_name: UI method (e.g. ``"equity"``).
        consumed_subdomain: Sub-method (e.g. ``"ohlcv"``).
        quality_mode: One of ``"off"``, ``"warn"``, ``"strict"``.
        provider: Provider name for report metadata.
        symbol: Ticker for report metadata.

    Returns:
        The original *df* (possibly with ``df.attrs["quality"]`` attached).
    """
    if quality_mode == "off":
        return df

    dataset_type = _infer_dataset_type(domain_name, method_name, consumed_subdomain)
    if dataset_type is None:
        # No mapping → cannot validate; skip silently
        return df

    try:
        import warnings as _warnings

        from vnstock.core.quality.exceptions import DataQualityError
        from vnstock.core.quality.registry import validate_dataframe

        sym_str = str(symbol) if symbol is not None else None
        report = validate_dataframe(
            df,
            dataset_type=dataset_type,
            provider=str(provider) if provider else None,
            symbol=sym_str,
        )

        from vnstock.core.settings import get_config

        cfg = get_config().quality
        if cfg.attach_report:
            df.attrs["quality"] = report

        if quality_mode == "strict" and not report.valid:
            raise DataQualityError(report)

        if quality_mode == "warn" and report.errors:
            _warnings.warn(
                f"Data quality issues detected ({len(report.errors)} errors). "
                "Inspect df.attrs['quality'] for details.",
                stacklevel=4,
            )

    except DataQualityError:
        raise
    except Exception as _validation_exc:
        # Quality validation internal errors must never break the data response.
        # In warn/strict mode, surface a warning so failures are observable.
        if quality_mode in ("warn", "strict"):
            import warnings as _w

            _w.warn(
                f"QUALITY_VALIDATION_INTERNAL_ERROR: validation failed internally "
                f"and was skipped ({type(_validation_exc).__name__}: {_validation_exc}). "
                "Data is returned unvalidated.",
                RuntimeWarning,
                stacklevel=4,
            )

    return df
