"""Pydantic schemas for vnstock-service responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class ResponseMeta(BaseModel):
    request_id: Optional[str] = None
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
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None
    interval: str = "1D"


class SymbolRecord(BaseModel):
    symbol: str
    exchange: Optional[str] = None
    name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    is_active: Optional[bool] = None


class MembershipRecord(BaseModel):
    entity_id: str
    member_symbol: str
    observed_at: datetime

    @field_validator("entity_id", "member_symbol")
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("membership identifiers must not be empty")
        return normalized


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


class CompanyInfoRecord(BaseModel):
    symbol: str
    exchange: str
    short_name: str | None = None
    full_name: str | None = None
    website: str | None = None
    industry: str | None = None
    industry_code: str | None = None
    company_type: str | None = None
    established_year: int | None = None
    employees: int | None = None
    foreign_percent: float | None = None
    outstanding_share: float | None = None
    issue_share: float | None = None
    stock_rating: str | None = None


class SymbolsResponse(VnstockResponse):
    pass


class OHLCVResponse(VnstockResponse):
    @field_validator("data")
    @classmethod
    def parse_ohlcv_records(cls, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            OHLCVRecord.model_validate(record).model_dump(mode="json")
            for record in records
        ]


class MembershipResponse(VnstockResponse):
    @field_validator("data")
    @classmethod
    def parse_membership_records(
        cls, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return [
            MembershipRecord.model_validate(record).model_dump(mode="json")
            for record in records
        ]


class CompanyInfoResponse(VnstockResponse):
    data: list[CompanyInfoRecord]


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
