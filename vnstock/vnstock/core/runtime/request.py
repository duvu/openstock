"""
DatasetRequest — structured input envelope for PluginRuntime.

Usage::

    from vnstock.core.runtime.request import DatasetRequest

    req = DatasetRequest(
        dataset="equity.ohlcv",
        params={"symbol": "FPT", "start": "2024-01-01", "end": "2024-06-30"},
        source=None,       # auto routing
        validate=True,
        return_result=False,
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DatasetRequest:
    """Structured input for a PluginRuntime.fetch() call.

    Attributes:
        dataset: Dotted dataset name, e.g. ``"equity.ohlcv"``.
        params: Provider-specific fetch parameters.
        source: Explicit provider name (``"KBS"``, ``"VCI"``, etc.) or
            ``None`` / ``"auto"`` for automatic selection.
        validate: Whether to validate the output against the
            :class:`~vnstock.core.contracts.base.DatasetContract`.
        quality_mode: Quality validation mode: ``"off"`` / ``"warn"`` /
            ``"strict"``. Overrides global quality settings.
        return_result: When ``True``, return a :class:`DataResult` instead
            of a bare :class:`pandas.DataFrame`.
    """

    dataset: str
    params: dict[str, Any] = field(default_factory=dict)
    source: str | None = None
    validate: bool = False
    quality_mode: str = "warn"
    return_result: bool = False

    def __post_init__(self) -> None:
        if not self.dataset or not isinstance(self.dataset, str):
            raise ValueError("DatasetRequest.dataset must be a non-empty string.")
        if "." not in self.dataset:
            raise ValueError(
                f"DatasetRequest.dataset must be a dotted name "
                f"(e.g. 'equity.ohlcv'), got: {self.dataset!r}"
            )
        if not isinstance(self.params, dict):
            raise TypeError(
                f"DatasetRequest.params must be a dict, got {type(self.params).__name__}"
            )
        if self.quality_mode not in ("off", "warn", "strict"):
            raise ValueError(
                f"DatasetRequest.quality_mode must be 'off', 'warn', or 'strict', "
                f"got: {self.quality_mode!r}"
            )
