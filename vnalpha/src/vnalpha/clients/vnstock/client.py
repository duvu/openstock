"""vnstock-service HTTP client for vnalpha."""

from __future__ import annotations

import json
from typing import Any, Optional
from urllib.parse import urlencode

import httpx

from vnalpha.clients.vnstock.errors import (
    VnstockConnectionError,
    VnstockDataError,
    VnstockHTTPError,
    VnstockTimeoutError,
)
from vnalpha.clients.vnstock.schemas import (
    OHLCVResponse,
    ProviderHealthResponse,
    SymbolsResponse,
    VnstockResponse,
)
from vnalpha.clients.vnstock.source_policy import validate_persistence_source
from vnalpha.core.config import get_config
from vnalpha.core.logging import get_logger

logger = get_logger("clients.vnstock")


class VnstockClient:
    """HTTP client for vnstock-service."""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 30.0) -> None:
        cfg = get_config().vnstock
        self._base_url = (base_url or cfg.base_url).rstrip("/")
        self._timeout = timeout
        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=self._timeout,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "VnstockClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _get(
        self, path: str, params: Optional[dict[str, str]] = None
    ) -> dict[str, Any]:
        url = path
        if params:
            url = f"{path}?{urlencode({k: v for k, v in params.items() if v is not None})}"
        logger.debug("GET %s%s", self._base_url, url)
        try:
            r = self._client.get(url)
        except httpx.ConnectError as exc:
            raise VnstockConnectionError(
                f"Cannot connect to vnstock-service at {self._base_url}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise VnstockTimeoutError(
                f"Timeout connecting to vnstock-service at {self._base_url}"
            ) from exc
        if r.status_code != 200:
            raise VnstockHTTPError(r.status_code, path, r.text)
        try:
            return r.json()
        except json.JSONDecodeError as exc:
            raise VnstockDataError(f"Failed to parse JSON from {path}") from exc

    def health_check(self) -> dict[str, Any]:
        """GET /healthz."""
        return self._get("/healthz")

    def get_symbols(
        self,
        source: Optional[str] = None,
    ) -> SymbolsResponse:
        """GET /v1/reference/symbols."""
        source = validate_persistence_source(source)
        params = {}
        if source:
            params["source"] = source
        raw = self._get("/v1/reference/symbols", params or None)
        return SymbolsResponse.model_validate(raw)

    def get_equity_ohlcv(
        self,
        symbol: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        interval: str = "1D",
        source: Optional[str] = None,
    ) -> OHLCVResponse:
        """GET /v1/equity/ohlcv for warehouse-bound ingestion."""
        source = validate_persistence_source(source)
        params: dict[str, str] = {"symbol": symbol, "interval": interval}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        if source:
            params["source"] = source
        raw = self._get("/v1/equity/ohlcv", params)
        return OHLCVResponse.model_validate(raw)

    def get_corporate_actions(
        self,
        symbol: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        source: Optional[str] = None,
    ) -> VnstockResponse:
        """GET normalized corporate-action evidence for bounded ingestion."""
        source = validate_persistence_source(source)
        params: dict[str, str] = {"symbol": symbol}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        if source:
            params["source"] = source
        raw = self._get("/v1/reference/corporate-actions", params)
        return VnstockResponse.model_validate(raw)

    def get_equity_quote(
        self,
        symbol: str,
        source: Optional[str] = None,
    ) -> VnstockResponse:
        """GET /v1/equity/quote."""
        source = validate_persistence_source(source)
        params: dict[str, str] = {"symbol": symbol}
        if source:
            params["source"] = source
        raw = self._get("/v1/equity/quote", params)
        return VnstockResponse.model_validate(raw)

    def get_index_ohlcv(
        self,
        symbol: str = "VNINDEX",
        start: Optional[str] = None,
        end: Optional[str] = None,
        interval: str = "1D",
        source: Optional[str] = None,
    ) -> OHLCVResponse:
        """GET /v1/index/ohlcv for warehouse-bound ingestion."""
        source = validate_persistence_source(source)
        params: dict[str, str] = {"symbol": symbol, "interval": interval}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        if source:
            params["source"] = source
        raw = self._get("/v1/index/ohlcv", params)
        return OHLCVResponse.model_validate(raw)

    def get_provider_health(self) -> ProviderHealthResponse:
        """GET /v1/providers/health."""
        raw = self._get("/v1/providers/health")
        return ProviderHealthResponse.from_raw(raw)

    def get_provider_capabilities(self) -> dict[str, Any]:
        """GET /v1/providers/capabilities."""
        return self._get("/v1/providers/capabilities")
