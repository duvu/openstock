"""Local HTTP data service for vnstock.

Uses Python stdlib ``http.server`` — no extra dependencies needed.

Endpoint routing is handled by :class:`VnstockHandler`.

FORBIDDEN endpoints (must never exist):
  /v1/auth/login
  /v1/order*
  /v1/account*
  /v1/portfolio*
  /v1/transfer*
  /v1/margin*
  /v1/trading*

ALLOWED endpoint groups:
  GET /healthz
  GET /v1/providers
  GET /v1/providers/health
  GET /v1/providers/capabilities
  GET /v1/auth/status
  GET /v1/auth/providers
  GET /v1/equity/<dataset>?<params>
  GET /v1/index/<dataset>?<params>
  GET /v1/reference/<dataset>?<params>
  GET /v1/company/<dataset>?<params>
  GET /v1/fundamental/<dataset>?<params>
  GET /v1/fund/<dataset>?<params>
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Forbidden route prefixes (case-insensitive)
# ---------------------------------------------------------------------------

_FORBIDDEN_PREFIXES = (
    "/v1/auth/login",
    "/v1/order",
    "/v1/account",
    "/v1/portfolio",
    "/v1/transfer",
    "/v1/margin",
    "/v1/trading",
)

# Canonical data endpoint prefixes handled via PluginRuntime
_DATA_PREFIXES = (
    "/v1/equity/",
    "/v1/index/",
    "/v1/reference/",
    "/v1/company/",
    "/v1/fundamental/",
    "/v1/fund/",
    # Deprecated aliases (still dispatched through runtime)
    "/v1/market/",
)


def _is_forbidden(path: str) -> bool:
    """Return True if path matches a forbidden prefix."""
    p = path.lower().rstrip("/")
    for prefix in _FORBIDDEN_PREFIXES:
        if p == prefix or p.startswith(prefix + "/"):
            return True
    return False


def _is_data_endpoint(path: str) -> bool:
    """Return True if path should be dispatched to PluginRuntime."""
    p = path.lower()
    return any(p.startswith(pfx) for pfx in _DATA_PREFIXES)


# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------


class VnstockHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler for vnstock local data service."""

    # Populated on server instance
    _auth_manager: Any = None

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        logger.debug("[service] request completed")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)

        # ── Forbidden gate ────────────────────────────────────────────────
        if _is_forbidden(path):
            self._send_json(
                404,
                {
                    "error": "not_found",
                    "message": f"Endpoint '{path}' does not exist.",
                },
            )
            return

        # ── Route dispatch ────────────────────────────────────────────────
        if path in ("/healthz", "/health"):
            self._handle_healthz()
        elif path == "/v1/providers":
            self._handle_providers()
        elif path == "/v1/providers/health":
            self._handle_providers_health()
        elif path == "/v1/providers/capabilities":
            self._handle_providers_capabilities()
        elif path == "/v1/auth/status":
            self._handle_auth_status()
        elif path == "/v1/auth/providers":
            self._handle_auth_providers()
        elif _is_data_endpoint(path):
            self._handle_data(path, query)
        else:
            self._send_json(
                404,
                {
                    "error": "not_found",
                    "message": f"Endpoint '{path}' not found.",
                },
            )

    # ------------------------------------------------------------------ #
    # Non-data endpoint handlers                                          #
    # ------------------------------------------------------------------ #

    def _handle_healthz(self) -> None:
        self._send_json(200, {"status": "ok", "service": "vnstock"})

    def _handle_providers(self) -> None:
        try:
            from vnstock.core.runtime import default_plugin_registry

            registry = default_plugin_registry()
            providers = list(registry.names())
        except Exception:
            providers = []
        self._send_json(200, {"providers": providers})

    def _handle_providers_health(self) -> None:
        try:
            from vnstock.core.provider.health import DEFAULT_HEALTH_STORE

            all_providers = DEFAULT_HEALTH_STORE.all_providers()
            health_data = {}
            for pname in all_providers:
                for dataset in DEFAULT_HEALTH_STORE.all_datasets():
                    h = DEFAULT_HEALTH_STORE.get(pname, dataset)
                    if pname not in health_data:
                        health_data[pname] = {}
                    health_data[pname][dataset] = h.to_dict()
        except Exception:
            health_data = {}
        providers = [
            health for datasets in health_data.values() for health in datasets.values()
        ]
        self._send_json(200, {"health": health_data, "providers": providers})

    def _handle_providers_capabilities(self) -> None:
        """Return provider capabilities matrix (no auth material)."""
        try:
            from vnstock.core.runtime import default_plugin_registry

            registry = default_plugin_registry()
            caps: dict[str, Any] = {}
            try:
                caps = registry.capability_matrix()
            except AttributeError:
                # Fallback: iterate plugins manually
                for name in registry.names():
                    try:
                        plugin = registry.get(name)
                        caps[name] = plugin.capabilities()
                    except Exception:
                        caps[name] = {}
        except Exception:
            caps = {}
        self._send_json(200, {"capabilities": caps})

    def _handle_auth_status(self) -> None:
        """Return safe auth status — no token material."""
        if self._auth_manager is None:
            self._send_json(
                200, {"auth_status": {}, "note": "auth_manager not configured"}
            )
            return
        try:
            status = self._auth_manager.auth_status_all()
            # Strip any token material before returning
            safe_status = {}
            if isinstance(status, list):
                # Normalise list[dict] format returned by some implementations
                for entry in status:
                    if isinstance(entry, dict):
                        provider = entry.get("provider", "unknown")
                        safe_status[provider] = {
                            "authenticated": entry.get("authenticated", False),
                            "provider": provider,
                            "source": entry.get("source"),
                        }
            elif isinstance(status, dict):
                for provider, s in status.items():
                    safe_status[provider] = {
                        "authenticated": s.get("authenticated", False),
                        "provider": s.get("provider", provider),
                        "source": s.get("source"),
                    }
        except Exception:
            safe_status = {}
        self._send_json(200, {"auth_status": safe_status})

    def _handle_auth_providers(self) -> None:
        """Return which providers support auth (no credential material)."""
        try:
            from vnstock.providers import PROVIDER_PLUGINS

            auth_info: dict[str, Any] = {}
            for name, plugin_class in PROVIDER_PLUGINS.items():
                try:
                    plugin = plugin_class()
                    spec = plugin.auth_spec("equity.ohlcv")
                    auth_info[name] = {
                        "auth_type": spec.auth_type.value,
                        "required": spec.required,
                        "experimental": spec.experimental,
                        "explicit_only": spec.explicit_only,
                    }
                except Exception:
                    auth_info[name] = {"auth_type": "none", "required": False}
        except Exception:
            auth_info = {}
        self._send_json(200, {"auth_providers": auth_info})

    # ------------------------------------------------------------------ #
    # Data endpoint handler — routed through PluginRuntime                #
    # ------------------------------------------------------------------ #

    def _handle_data(self, path: str, query: dict[str, list[str]]) -> None:
        """Dispatch a data request through PluginRuntime.

        All supported canonical paths (and deprecated aliases) are mapped to
        a dataset name via :mod:`vnstock.service.dataset_mapper`, then fetched
        via :func:`vnstock.service.runtime_dependency.get_runtime`.

        Args:
            path: Normalised URL path (already rstrip'd).
            query: Parsed query-string dict from :func:`urllib.parse.parse_qs`.
        """
        from vnstock.core.provider.exceptions import (
            DatasetContractError,
            NoHealthyProviderError,
            ProviderFetchError,
            UnsupportedDatasetError,
            UnsupportedDatasetForProviderError,
            VnstockPlatformError,
        )
        from vnstock.service.dataset_mapper import (
            MapperError,
            extract_data_params,
            extract_runtime_params,
            path_to_dataset,
        )
        from vnstock.service.runtime_dependency import get_runtime
        from vnstock.service.serializers import RequestContext, serialize_data_result

        request_id = f"req_{uuid.uuid4().hex[:12]}"

        # 1. Map path → dataset
        try:
            dataset = path_to_dataset(path)
        except MapperError:
            self._send_json(
                404,
                {
                    "error": "unsupported_dataset",
                    "message": f"No dataset available at '{path}'.",
                    "request_id": request_id,
                },
            )
            return

        # 2. Extract runtime control params and data params
        runtime_params = extract_runtime_params(query)
        source: str | None = runtime_params.get("source")
        validate_str = runtime_params.get("validate", "false").lower()
        validate = validate_str in ("1", "true", "yes")
        quality_mode: str = runtime_params.get("quality_mode", "warn")

        try:
            params = extract_data_params(query)
        except ValueError:
            self._send_json(
                400,
                {
                    "error": "invalid_parameters",
                    "message": "Credential query parameters are not allowed.",
                    "dataset": dataset,
                    "request_id": request_id,
                },
            )
            return

        # 4. Fetch via PluginRuntime
        try:
            runtime = get_runtime()
            result = runtime.fetch(
                dataset,
                params,
                source=source,
                validate=validate,
                quality_mode=quality_mode,
                return_result=True,
            )
        except UnsupportedDatasetError as exc:
            self._send_json(
                404,
                {
                    "error": "unsupported_dataset",
                    "message": str(exc)[:300],
                    "dataset": dataset,
                    "request_id": request_id,
                },
            )
            return
        except UnsupportedDatasetForProviderError as exc:
            self._send_json(
                422,
                {
                    "error": "unsupported_dataset_for_provider",
                    "message": str(exc)[:300],
                    "dataset": dataset,
                    "request_id": request_id,
                },
            )
            return
        except NoHealthyProviderError as exc:
            self._send_json(
                503,
                {
                    "error": "no_healthy_provider",
                    "message": str(exc)[:300],
                    "dataset": dataset,
                    "candidates": list(exc.candidates),
                    "rejection_reasons": {
                        provider: reason[:200]
                        for provider, reason in exc.rejection_reasons.items()
                    },
                    "request_id": request_id,
                },
            )
            return
        except ProviderFetchError as exc:
            self._send_json(
                502,
                {
                    "error": "provider_fetch_error",
                    "message": str(exc)[:300],
                    "dataset": dataset,
                    "request_id": request_id,
                },
            )
            return
        except DatasetContractError as exc:
            self._send_json(
                422,
                {
                    "error": "contract_validation_failed",
                    "message": str(exc)[:300],
                    "dataset": dataset,
                    "request_id": request_id,
                },
            )
            return
        except VnstockPlatformError as exc:
            msg = str(exc)
            # Bad params tend to mention "Invalid parameters"
            status = (
                400 if "Invalid parameters" in msg or "invalid" in msg.lower() else 500
            )
            self._send_json(
                status,
                {
                    "error": "platform_error",
                    "message": msg[:300],
                    "dataset": dataset,
                    "request_id": request_id,
                },
            )
            return
        except Exception as exc:
            self._send_json(
                500,
                {
                    "error": "internal_error",
                    "message": str(exc)[:200],
                    "dataset": dataset,
                    "request_id": request_id,
                },
            )
            return

        # 5. Serialize DataResult → envelope
        ctx = RequestContext(
            dataset=dataset,
            source_requested=source,
            request_id=request_id,
        )
        envelope = serialize_data_result(result, ctx)
        self._send_json(200, envelope)

    # ------------------------------------------------------------------ #
    # Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# ---------------------------------------------------------------------------
# Server factory
# ---------------------------------------------------------------------------


def _make_handler(auth_manager: Any = None):
    """Create a handler class with auth_manager bound."""

    class BoundHandler(VnstockHandler):
        _auth_manager = auth_manager

    return BoundHandler


def run_server(
    host: str = "127.0.0.1",
    port: int = 6900,
    auth_manager: Any = None,
    *,
    _stop_event: threading.Event | None = None,
) -> None:
    """Start the vnstock local data service.

    Args:
        host: Bind address. Defaults to ``127.0.0.1`` (localhost-only).
        port: Bind port. Defaults to 6900.
        auth_manager: Optional :class:`AuthManager` for auth status endpoints.
        _stop_event: Internal use only — threading.Event to signal shutdown.
    """
    handler_class = _make_handler(auth_manager)
    server = HTTPServer((host, port), handler_class)
    logger.info(f"vnstock service listening on http://{host}:{port}")

    if _stop_event is not None:
        # Non-blocking for tests
        def _serve():
            while not _stop_event.is_set():
                server.handle_request()
            server.server_close()

        t = threading.Thread(target=_serve, daemon=True)
        t.start()
        return

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        logger.info("vnstock service stopped.")
