from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from json import dumps, loads
from typing import Mapping, Protocol

import duckdb
from pydantic import ValidationError

from vnalpha.clients.vnstock.client import VnstockClient
from vnalpha.clients.vnstock.errors import (
    VnstockConnectionError,
    VnstockDataError,
    VnstockHTTPError,
)
from vnalpha.clients.vnstock.schemas import CompanyInfoRecord, CompanyInfoResponse


class CompanyContextStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    EMPTY = "EMPTY"
    UNSUPPORTED = "UNSUPPORTED"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"
    UNAVAILABLE = "UNAVAILABLE"
    HISTORICAL_UNAVAILABLE = "HISTORICAL_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class CompanyContextSnapshot:
    symbol: str
    provider: str
    observed_at: datetime
    content_hash: str
    exchange: str
    short_name: str | None
    full_name: str | None
    website: str | None
    industry: str | None
    industry_code: str | None
    company_type: str | None
    established_year: int | None
    employees: int | None
    foreign_percent: float | None
    outstanding_share: float | None
    issue_share: float | None
    stock_rating: str | None

    @classmethod
    def from_record(
        cls,
        record: CompanyInfoRecord,
        *,
        provider: str,
        observed_at: datetime,
        content_hash: str,
    ) -> CompanyContextSnapshot:
        return cls(
            symbol=record.symbol,
            provider=provider,
            observed_at=observed_at,
            content_hash=content_hash,
            exchange=record.exchange,
            short_name=record.short_name,
            full_name=record.full_name,
            website=record.website,
            industry=record.industry,
            industry_code=record.industry_code,
            company_type=record.company_type,
            established_year=record.established_year,
            employees=record.employees,
            foreign_percent=record.foreign_percent,
            outstanding_share=record.outstanding_share,
            issue_share=record.issue_share,
            stock_rating=record.stock_rating,
        )

    def payload(self) -> dict[str, str | int | float | None]:
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "short_name": self.short_name,
            "full_name": self.full_name,
            "website": self.website,
            "industry": self.industry,
            "industry_code": self.industry_code,
            "company_type": self.company_type,
            "established_year": self.established_year,
            "employees": self.employees,
            "foreign_percent": self.foreign_percent,
            "outstanding_share": self.outstanding_share,
            "issue_share": self.issue_share,
            "stock_rating": self.stock_rating,
        }

    def to_dict(self) -> dict[str, str | int | float | None]:
        return {
            **self.payload(),
            "provider": self.provider,
            "observed_at": self.observed_at.isoformat(),
            "content_hash": self.content_hash,
        }


@dataclass(frozen=True, slots=True)
class CompanyContextResult:
    status: CompanyContextStatus
    snapshot: CompanyContextSnapshot | None
    failure_category: str | None = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> CompanyContextResult | None:
        try:
            status = CompanyContextStatus(str(payload["status"]))
        except (KeyError, ValueError):
            return None
        failure_category = payload.get("failure_category")
        if not isinstance(failure_category, str):
            failure_category = None
        snapshot_payload = payload.get("snapshot")
        if status is not CompanyContextStatus.AVAILABLE:
            return cls(status, None, failure_category)
        if not isinstance(snapshot_payload, Mapping):
            return None
        try:
            record = CompanyInfoRecord.model_validate(snapshot_payload)
            provider = str(snapshot_payload["provider"])
            observed_at = datetime.fromisoformat(str(snapshot_payload["observed_at"]))
            content_hash = str(snapshot_payload["content_hash"])
        except (KeyError, TypeError, ValueError, ValidationError):
            return None
        return cls(
            status,
            CompanyContextSnapshot.from_record(
                record,
                provider=provider,
                observed_at=observed_at,
                content_hash=content_hash,
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "snapshot": self.snapshot.to_dict() if self.snapshot is not None else None,
            "failure_category": self.failure_category,
        }


class CompanyInfoClient(Protocol):
    def get_company_info(self, symbol: str) -> CompanyInfoResponse: ...


def refresh_company_context(
    connection: duckdb.DuckDBPyConnection,
    symbol: str,
    client: CompanyInfoClient | None = None,
) -> CompanyContextResult:
    normalized_symbol = symbol.strip().upper()
    if client is not None:
        return _refresh_with_client(connection, normalized_symbol, client)
    with VnstockClient() as default_client:
        return _refresh_with_client(connection, normalized_symbol, default_client)


def get_current_company_context(
    connection: duckdb.DuckDBPyConnection,
    symbol: str,
    *,
    historical: bool,
) -> CompanyContextResult:
    if historical:
        return CompanyContextResult(CompanyContextStatus.HISTORICAL_UNAVAILABLE, None)
    row = connection.execute(
        """
        SELECT provider, observed_at, content_hash, payload_json, status, failure_category
        FROM company_context_revision
        WHERE symbol = ?
        ORDER BY CASE status WHEN 'AVAILABLE' THEN 0 ELSE 1 END, observed_at DESC
        LIMIT 1
        """,
        [symbol.strip().upper()],
    ).fetchone()
    if row is None:
        return CompanyContextResult(CompanyContextStatus.UNAVAILABLE, None)
    provider, observed_at, content_hash, payload_json, status, failure_category = row
    stored_status = CompanyContextStatus(str(status))
    if stored_status is not CompanyContextStatus.AVAILABLE:
        return CompanyContextResult(
            stored_status,
            None,
            str(failure_category) if failure_category is not None else None,
        )
    payload = loads(str(payload_json))
    record = CompanyInfoRecord.model_validate(payload)
    return CompanyContextResult(
        stored_status,
        CompanyContextSnapshot.from_record(
            record,
            provider=str(provider),
            observed_at=observed_at,
            content_hash=str(content_hash),
        ),
    )


def _refresh_with_client(
    connection: duckdb.DuckDBPyConnection,
    symbol: str,
    client: CompanyInfoClient,
) -> CompanyContextResult:
    try:
        response = client.get_company_info(symbol)
    except VnstockHTTPError as error:
        status = (
            CompanyContextStatus.UNSUPPORTED
            if error.status_code in {404, 422}
            else CompanyContextStatus.PROVIDER_FAILURE
        )
        return _store_outcome(
            connection, symbol, None, status, error.service_error_code
        )
    except (VnstockConnectionError, VnstockDataError, ValidationError):
        return _store_outcome(
            connection,
            symbol,
            None,
            CompanyContextStatus.PROVIDER_FAILURE,
            "VNSTOCK_PROVIDER_FAILURE",
        )
    if not response.data:
        return _store_outcome(
            connection, symbol, response.meta.provider, CompanyContextStatus.EMPTY, None
        )
    record = response.data[0]
    fields = record.model_dump(mode="json")
    content_hash = sha256(
        dumps(fields, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    observed_at = _observed_at(response)
    snapshot = CompanyContextSnapshot.from_record(
        record,
        provider=response.meta.provider,
        observed_at=observed_at,
        content_hash=content_hash,
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO company_context_revision
        (revision_id, symbol, provider, observed_at, status, content_hash, payload_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            _revision_id(symbol, response.meta.provider, content_hash),
            symbol,
            response.meta.provider,
            observed_at,
            CompanyContextStatus.AVAILABLE.value,
            content_hash,
            dumps(snapshot.payload(), sort_keys=True, separators=(",", ":")),
        ],
    )
    return get_current_company_context(connection, symbol, historical=False)


def _store_outcome(
    connection: duckdb.DuckDBPyConnection,
    symbol: str,
    provider: str | None,
    status: CompanyContextStatus,
    failure_category: str | None,
) -> CompanyContextResult:
    observed_at = datetime.now(UTC)
    outcome_hash = sha256(
        f"{symbol}:{provider}:{status.value}:{failure_category}".encode("utf-8")
    ).hexdigest()
    connection.execute(
        """
        INSERT OR IGNORE INTO company_context_revision
        (revision_id, symbol, provider, observed_at, status, content_hash, failure_category)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            _revision_id(symbol, provider or "UNKNOWN", outcome_hash),
            symbol,
            provider,
            observed_at,
            status.value,
            outcome_hash,
            failure_category,
        ],
    )
    return CompanyContextResult(status, None, failure_category)


def _observed_at(response: CompanyInfoResponse) -> datetime:
    if response.meta.fetched_at is None:
        return datetime.now(UTC)
    return datetime.fromisoformat(response.meta.fetched_at.replace("Z", "+00:00"))


def _revision_id(symbol: str, provider: str, content_hash: str) -> str:
    return sha256(f"{symbol}:{provider}:{content_hash}".encode("utf-8")).hexdigest()
