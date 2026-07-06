"""Structured data models for provider hardening: capability, health, comparison, issues."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional


@dataclass(frozen=True)
class ProviderCapability:
    """Declares a single supported capability for a provider.

    Attributes:
        provider: Provider name (e.g. ``"DNSE"``, ``"KBS"``, ``"VCI"``).
        dataset_type: Type of data (e.g. ``"ohlcv"``, ``"price_board"``,
            ``"intraday_trades"``).
        asset_class: Asset class (e.g. ``"equity"``, ``"index"``,
            ``"derivative"``).
        method: Method name on the provider class (e.g. ``"history"``,
            ``"price_board"``).
        intervals: Supported interval strings (e.g. ``["1D", "1W", "1M"]``).
        supports_batch: Provider can return multiple symbols in one call.
        supports_intraday: Provider supports intraday tick data.
        supports_history: Provider supports historical time-series.
        supports_live_snapshot: Provider supports real-time/live snapshots.
        requires_auth: Endpoint requires authentication credentials.
        is_live_testable: Whether a live smoke test is appropriate.
        notes: Free-text notes for documentation and matrix generation.
    """

    provider: str
    dataset_type: str
    asset_class: str
    method: str
    intervals: List[str]
    supports_batch: bool = False
    supports_intraday: bool = False
    supports_history: bool = False
    supports_live_snapshot: bool = False
    requires_auth: bool = False
    is_live_testable: bool = True
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass
class ProviderIssue:
    """Structured issue record for a provider capability problem.

    Attributes:
        code: Machine-readable issue code (e.g. ``"SCHEMA_DRIFT_MAJOR"``).
        severity: One of ``"error"``, ``"warning"``, or ``"info"``.
        provider: Provider name.
        capability: Dataset type + asset class (e.g. ``"ohlcv/equity"``).
        message: Human-readable description.
        context: Optional additional context dict.
    """

    code: str
    severity: Literal["error", "warning", "info"]
    provider: str
    capability: str
    message: str
    context: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


@dataclass
class ProviderHealth:
    """Health state for a provider at a point in time.

    Attributes:
        provider: Provider name.
        status: Overall health status.
        checked_at: Timestamp of the health check.
        capabilities_checked: List of capability keys checked
            (e.g. ``["ohlcv/equity", "price_board/equity"]``).
        latency_ms: Observed latency in milliseconds (``None`` if not measured).
        error_rate: Fraction of recent requests that errored (0.0–1.0,
            ``None`` if not measured).
        schema_status: Whether the schema is compatible, drifted, or unknown.
        freshness_status: Whether the data was fresh, stale, or unknown.
        issues: List of structured issue records.
    """

    provider: str
    status: Literal["healthy", "degraded", "failing", "unknown"]
    checked_at: datetime
    capabilities_checked: List[str] = field(default_factory=list)
    latency_ms: Optional[float] = None
    error_rate: Optional[float] = None
    schema_status: Literal["compatible", "drifted", "unknown"] = "unknown"
    freshness_status: Literal["fresh", "stale", "unknown"] = "unknown"
    issues: List[ProviderIssue] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["checked_at"] = self.checked_at.isoformat()
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


@dataclass
class ProviderComparisonReport:
    """Report comparing overlapping provider outputs for the same capability.

    Attributes:
        dataset_type: Type of data compared (e.g. ``"ohlcv"``).
        symbol: The symbol compared.
        providers: Ordered list of provider names included.
        comparable: Whether a meaningful comparison was possible.
        base_provider: Provider used as the reference baseline.
        row_count_by_provider: Row count for each provider result.
        missing_dates_by_provider: Dates present in other providers but
            absent in this one.
        price_diff_summary: Summary of price differences (max/mean pct).
        volume_diff_summary: Summary of volume differences (max/mean pct).
        issues: List of structured issues found during comparison.
        interval: Interval used (e.g. ``"1D"``).
        start: Start date of the comparison range.
        end: End date of the comparison range.
    """

    dataset_type: str
    symbol: str
    providers: List[str]
    comparable: bool
    base_provider: str
    row_count_by_provider: Dict[str, int] = field(default_factory=dict)
    missing_dates_by_provider: Dict[str, List[str]] = field(default_factory=dict)
    price_diff_summary: Dict[str, Any] = field(default_factory=dict)
    volume_diff_summary: Dict[str, Any] = field(default_factory=dict)
    issues: List[ProviderIssue] = field(default_factory=list)
    interval: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)
