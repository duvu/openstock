"""Outcome tracking errors."""

from __future__ import annotations


class OutcomeError(Exception):
    """Base class for outcome errors."""


class OutcomeEvaluationError(OutcomeError):
    """Raised when evaluation fails for a candidate."""


class OutcomeMissingDataError(OutcomeError):
    """Raised when required OHLCV or benchmark data is absent."""


class OutcomeAggregationError(OutcomeError):
    """Raised when aggregation fails."""


class OutcomeCalibrationError(OutcomeError):
    """Raised when calibration report generation fails."""
