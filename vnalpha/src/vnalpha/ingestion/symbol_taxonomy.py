"""Typed normalization for source symbol lifecycle and taxonomy records."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SymbolTaxonomy:
    """A source observation normalized to the warehouse lifecycle contract."""

    symbol: str
    exchange: str | None
    name: str | None
    security_type: str
    lifecycle_status: str
    listing_date: str | None
    delisting_date: str | None
    sector_code: str | None
    sector_name: str | None
    industry_code: str | None
    industry_name: str | None
    taxonomy_name: str
    taxonomy_version: str
    classification_source: str
    effective_from: str | None

    @property
    def is_active_common_equity(self) -> bool:
        """Return whether this row belongs to the default research universe."""

        return (
            self.security_type == "COMMON_EQUITY" and self.lifecycle_status == "ACTIVE"
        )


def normalize_symbol_taxonomy(
    record: Mapping[str, object],
    source: str,
) -> SymbolTaxonomy:
    """Normalize one provider record without inventing unknown classifications."""

    symbol = _text(record, "symbol")
    if symbol is None:
        raise ValueError("Symbol source record is missing a symbol.")
    return SymbolTaxonomy(
        symbol=symbol.upper(),
        exchange=_text(record, "exchange"),
        name=_text(record, "name", "full_name", "company_name"),
        security_type=_security_type(
            _text(record, "security_type", "asset_type", "type")
        ),
        lifecycle_status=_lifecycle_status(
            _text(record, "lifecycle_status", "trading_status", "status")
        ),
        listing_date=_text(record, "listing_date", "listed_date"),
        delisting_date=_text(record, "delisting_date", "delisted_date"),
        sector_code=_text(record, "sector_code"),
        sector_name=_text(record, "sector_name", "sector"),
        industry_code=_text(record, "industry_code"),
        industry_name=_text(record, "industry_name", "industry"),
        taxonomy_name=_text(record, "taxonomy_name") or "source_unversioned",
        taxonomy_version=_text(record, "taxonomy_version") or "unversioned",
        classification_source=source,
        effective_from=_text(record, "classification_effective_from", "effective_from"),
    )


def _text(record: Mapping[str, object], *keys: str) -> str | None:
    """Return the first nonblank string-like provider value."""

    for key in keys:
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _security_type(value: str | None) -> str:
    """Map known source variants; retain unsupported types as UNKNOWN."""

    normalized = (value or "").upper().replace("-", "_").replace(" ", "_")
    if normalized in {"", "COMMON_STOCK", "COMMON_EQUITY", "STOCK", "EQUITY"}:
        return "COMMON_EQUITY"
    if normalized in {"ETF", "FUND", "EXCHANGE_TRADED_FUND"}:
        return "ETF"
    if normalized in {"CW", "COVERED_WARRANT", "WARRANT"}:
        return "COVERED_WARRANT"
    if normalized in {"INDEX", "BENCHMARK"}:
        return "INDEX"
    if normalized in {"BOND", "FIXED_INCOME"}:
        return "BOND"
    return "UNKNOWN"


def _lifecycle_status(value: str | None) -> str:
    """Map source lifecycle states while treating unlabelled source rows as live."""

    normalized = (value or "ACTIVE").upper().replace("-", "_").replace(" ", "_")
    if normalized in {"ACTIVE", "LISTED", "TRADING", "TRADEABLE"}:
        return "ACTIVE"
    if normalized in {"SUSPENDED", "HALTED", "PAUSED"}:
        return "SUSPENDED"
    if normalized in {"DELISTED", "DELIST", "REMOVED"}:
        return "DELISTED"
    if normalized in {"INACTIVE", "UNLISTED"}:
        return "INACTIVE"
    return "UNKNOWN"
