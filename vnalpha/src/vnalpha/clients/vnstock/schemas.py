"""Pydantic schemas for vnstock-service responses."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ResponseMeta(BaseModel):
    dataset: str
    provider: str
    quality_status: Optional[str] = None
    quality_report: Optional[dict[str, Any]] = None
    runtime_path: Optional[str] = None
    fetched_at: Optional[str] = None


class VnstockResponse(BaseModel):
    """Generic vnstock-service response envelope."""
    data: list[dict[str, Any]]
    meta: ResponseMeta
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class OHLCVRecord(BaseModel):
    symbol: Optional[str] = None
    time: Optional[str] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[float] = None
    interval: Optional[str] = None


class SymbolRecord(BaseModel):
    symbol: str
    exchange: Optional[str] = None
    name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    is_active: Optional[bool] = None


class ProviderHealthRecord(BaseModel):
    provider: str
    dataset: Optional[str] = None
    status: str
    failure_count: Optional[int] = None
    last_success_at: Optional[str] = None
    last_failure_at: Optional[str] = None


class ProviderCapabilityRecord(BaseModel):
    provider: str
    dataset: str
    supported: bool
    status: Optional[str] = None


class SymbolsResponse(VnstockResponse):
    pass


class OHLCVResponse(VnstockResponse):
    pass


class ProviderHealthResponse(BaseModel):
    """Provider health is not wrapped in data/meta/diagnostics."""
    providers: list[dict[str, Any]] = Field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> "ProviderHealthResponse":
        # Handle both {providers: [...]} and flat list
        if "providers" in raw:
            return cls(providers=raw["providers"])
        if isinstance(raw, list):
            return cls(providers=raw)
        # Could be data/meta/diagnostics envelope
        if "data" in raw:
            return cls(providers=raw["data"])
        return cls(providers=[])
