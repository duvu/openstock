"""Domain models for the publication-aware fundamentals vertical (issue #257)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Final

FUNDAMENTALS_CONTRACT_VERSION: Final = "fundamentals-v1"

# Allowed fiscal periods and statement scopes; anything else fails closed.
FISCAL_PERIODS: Final = frozenset({"FY", "Q1", "Q2", "Q3", "Q4", "H1", "H2"})


class StatementScope(str, Enum):
    """Whether values are consolidated (group) or separate (parent-only)."""

    CONSOLIDATED = "CONSOLIDATED"
    SEPARATE = "SEPARATE"


STATEMENT_SCOPES: Final = frozenset(s.value for s in StatementScope)


class AuditStatus(str, Enum):
    AUDITED = "AUDITED"
    REVIEWED = "REVIEWED"
    UNAUDITED = "UNAUDITED"


@dataclass(frozen=True, slots=True)
class FundamentalFact:
    """One immutable financial-fact revision for a symbol/period/scope.

    ``published_at`` is when the fact became public; ``available_from`` is the
    earliest instant it may enter an as-of snapshot. As-of queries exclude any
    fact whose ``published_at`` is after the requested date so future-published
    facts never leak into historical analysis.
    """

    fact_id: str
    revision_number: int
    symbol: str
    fiscal_year: int
    fiscal_period: str
    statement_scope: StatementScope
    published_at: str  # ISO date
    period_end_date: str  # ISO date
    audit_status: AuditStatus
    currency: str
    unit: str
    revenue: float | None = None
    net_income: float | None = None
    eps: float | None = None
    total_assets: float | None = None
    total_equity: float | None = None
    total_liabilities: float | None = None
    operating_cash_flow: float | None = None
    source_reference: str = ""
    source_authority: str = ""
    available_from: str | None = None  # ISO datetime; defaults to published_at

    def __post_init__(self) -> None:
        if self.fiscal_period not in FISCAL_PERIODS:
            raise ValueError(
                f"Unsupported fiscal_period {self.fiscal_period!r}; "
                f"expected one of {sorted(FISCAL_PERIODS)}"
            )
        if self.revision_number < 1:
            raise ValueError("revision_number must be >= 1")
        if not self.symbol:
            raise ValueError("symbol is required")
        if not self.currency or not self.unit:
            raise ValueError("currency and unit are required (must be explicit)")


def fact_content_hash(fact: FundamentalFact) -> str:
    """Deterministic content hash over the material numeric + identity fields.

    Two facts with identical content produce the same hash, so re-ingesting the
    same source revision is idempotent.
    """
    payload = {
        "symbol": fact.symbol,
        "fiscal_year": fact.fiscal_year,
        "fiscal_period": fact.fiscal_period,
        "statement_scope": fact.statement_scope.value,
        "period_end_date": fact.period_end_date,
        "published_at": fact.published_at,
        "currency": fact.currency,
        "unit": fact.unit,
        "revenue": fact.revenue,
        "net_income": fact.net_income,
        "eps": fact.eps,
        "total_assets": fact.total_assets,
        "total_equity": fact.total_equity,
        "total_liabilities": fact.total_liabilities,
        "operating_cash_flow": fact.operating_cash_flow,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def compute_roe(net_income: float | None, total_equity: float | None) -> float | None:
    """Return return-on-equity, or None when inputs are missing or non-positive.

    Fails closed (None) rather than emitting a misleading ratio for zero or
    negative equity.
    """
    if net_income is None or total_equity is None:
        return None
    if total_equity <= 0:
        return None
    return net_income / total_equity


def compute_debt_to_equity(
    total_liabilities: float | None, total_equity: float | None
) -> float | None:
    """Return debt-to-equity, or None when inputs are missing or non-positive."""
    if total_liabilities is None or total_equity is None:
        return None
    if total_equity <= 0:
        return None
    return total_liabilities / total_equity


__all__ = [
    "FISCAL_PERIODS",
    "FUNDAMENTALS_CONTRACT_VERSION",
    "STATEMENT_SCOPES",
    "AuditStatus",
    "FundamentalFact",
    "StatementScope",
    "compute_debt_to_equity",
    "compute_roe",
    "fact_content_hash",
]
