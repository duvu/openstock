"""Core data models for the data quality layer.

Provides structured, serializable representations of quality issues
and validation reports.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class QualityIssue:
    """Represents a single data quality finding.

    Attributes:
        code: Machine-readable issue code (e.g. ``SCHEMA_MISSING_COLUMN``).
        severity: One of ``"info"``, ``"warning"``, ``"error"``.
        message: Human-readable description.
        column: Column name the issue relates to, if applicable.
        row_index: Integer row index where the issue was detected, if applicable.
        value: The offending value, if applicable.
        context: Arbitrary extra metadata for downstream consumers.
    """

    code: str
    severity: str  # "info" | "warning" | "error"
    message: str
    column: str | None = None
    row_index: int | None = None
    value: Any | None = None
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a plain-dict representation."""
        return asdict(self)

    def to_json(self) -> str:
        """Return a JSON string representation."""
        return json.dumps(self.to_dict(), default=str)


@dataclass
class ValidationReport:
    """Aggregated result of validating a single DataFrame.

    Attributes:
        valid: ``True`` when the report contains no errors.
        dataset_type: One of ``"ohlcv"``, ``"price_board"``,
            ``"intraday_trades"``, ``"reference"``, ``"fundamental"``.
        provider: Provider name that produced the data, e.g. ``"DNSE"``.
        symbol: Ticker symbol, e.g. ``"FPT"``.
        interval: Time resolution, e.g. ``"1D"``.
        row_count: Number of rows in the DataFrame that was validated.
        latest_time: ISO-formatted string of the latest timestamp found,
            or ``None`` if not applicable / not found.
        freshness_status: One of ``"fresh"``, ``"stale"``, ``"unknown"``.
        errors: List of error-severity :class:`QualityIssue` objects.
        warnings: List of warning-severity :class:`QualityIssue` objects.
        infos: List of info-severity :class:`QualityIssue` objects.
    """

    valid: bool
    dataset_type: str
    provider: str | None
    symbol: str | None
    interval: str | None
    row_count: int
    latest_time: str | None
    freshness_status: str  # "fresh" | "stale" | "unknown"
    errors: list[QualityIssue] = field(default_factory=list)
    warnings: list[QualityIssue] = field(default_factory=list)
    infos: list[QualityIssue] = field(default_factory=list)

    @property
    def severity(self) -> str:
        """Aggregate severity of the entire report.

        Returns ``"error"`` when any error-severity issues exist,
        ``"warning"`` when only warnings exist, and ``"info"`` otherwise.
        """
        if self.errors:
            return "error"
        if self.warnings:
            return "warning"
        return "info"

    @property
    def all_issues(self) -> list[QualityIssue]:
        """All issues concatenated: errors + warnings + infos."""
        return self.errors + self.warnings + self.infos

    def to_dict(self) -> dict[str, Any]:
        """Return a plain-dict representation."""
        return {
            "valid": self.valid,
            "dataset_type": self.dataset_type,
            "provider": self.provider,
            "symbol": self.symbol,
            "interval": self.interval,
            "row_count": self.row_count,
            "latest_time": self.latest_time,
            "freshness_status": self.freshness_status,
            "severity": self.severity,
            "errors": [i.to_dict() for i in self.errors],
            "warnings": [i.to_dict() for i in self.warnings],
            "infos": [i.to_dict() for i in self.infos],
        }

    def to_json(self) -> str:
        """Return a JSON string representation."""
        return json.dumps(self.to_dict(), default=str)
