"""Base class for all dataset validators."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd

from vnstock.core.quality.models import ValidationReport


class BaseValidator(ABC):
    """Abstract base for all dataset validators.

    Subclasses must implement :meth:`validate`.
    """

    dataset_type: str = ""

    @abstractmethod
    def validate(
        self,
        df: pd.DataFrame,
        provider: str | None = None,
        symbol: str | None = None,
        interval: str | None = None,
        config: Any | None = None,
    ) -> ValidationReport:
        """Validate *df* and return a :class:`ValidationReport`.

        Args:
            df: The DataFrame to validate.
            provider: Provider name, for report metadata.
            symbol: Ticker symbol, for report metadata.
            interval: Time resolution, for report metadata.
            config: Optional :class:`~vnstock.core.settings.QualityConfig`
                instance.  When ``None``, default settings apply.

        Returns:
            A :class:`~vnstock.core.quality.models.ValidationReport`.
        """
