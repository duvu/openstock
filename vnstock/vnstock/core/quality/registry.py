"""Validator registry.

Provides a single entry point for running validation on a DataFrame
by dataset type.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from vnstock.core.quality.base import BaseValidator
from vnstock.core.quality.models import ValidationReport

# Registry: dataset_type → validator instance
_REGISTRY: dict[str, BaseValidator] = {}


def register(validator: BaseValidator) -> None:
    """Register a validator for its ``dataset_type``.

    Args:
        validator: An instance of :class:`~vnstock.core.quality.base.BaseValidator`.
    """
    _REGISTRY[validator.dataset_type] = validator


def get_validator(dataset_type: str) -> BaseValidator | None:
    """Return the registered validator for *dataset_type*, or ``None``."""
    return _REGISTRY.get(dataset_type)


def validate_dataframe(
    df: pd.DataFrame,
    dataset_type: str,
    provider: str | None = None,
    symbol: str | None = None,
    interval: str | None = None,
    config: Any | None = None,
) -> ValidationReport:
    """Validate *df* against the registered contract for *dataset_type*.

    Args:
        df: DataFrame to validate.
        dataset_type: One of the registered dataset types
            (``"ohlcv"``, ``"price_board"``, ``"intraday_trades"``).
        provider: Provider name for report metadata.
        symbol: Ticker symbol for report metadata.
        interval: Time resolution for report metadata.
        config: Optional :class:`~vnstock.core.settings.QualityConfig`.

    Returns:
        A :class:`~vnstock.core.quality.models.ValidationReport`.

    Raises:
        ValueError: When *dataset_type* has no registered validator.
    """
    validator = get_validator(dataset_type)
    if validator is None:
        raise ValueError(
            f"No validator registered for dataset_type '{dataset_type}'. "
            f"Supported types: {sorted(_REGISTRY.keys())}"
        )
    return validator.validate(
        df, provider=provider, symbol=symbol, interval=interval, config=config
    )


# ---------------------------------------------------------------------------
# Register built-in validators
# ---------------------------------------------------------------------------


def _register_defaults() -> None:
    from vnstock.core.quality.validators.intraday import IntradayValidator
    from vnstock.core.quality.validators.ohlcv import OHLCVValidator
    from vnstock.core.quality.validators.price_board import PriceBoardValidator

    register(OHLCVValidator())
    register(PriceBoardValidator())
    register(IntradayValidator())


_register_defaults()
