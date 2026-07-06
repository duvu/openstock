"""
Base dataset contract model and registry for vnstock.

DatasetContract defines the canonical shape for a financial dataset.
DatasetContractRegistry manages available contracts by dataset name.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DatasetContract:
    """Canonical description of a financial dataset.

    Attributes:
        dataset: Dotted dataset name, e.g. ``"equity.ohlcv"``.
        required_columns: Columns that must be present in conforming data.
        optional_columns: Columns that may be present; not required.
        dtype_rules: Expected pandas dtype string per column.
        time_column: Name of the primary time/timestamp column, if any.
        symbol_column: Name of the symbol/ticker column, if any.
        validator: Short key naming the quality validator to bind, if any.
        description: Human-readable description.
    """

    dataset: str
    required_columns: list[str]
    optional_columns: list[str] = field(default_factory=list)
    dtype_rules: dict[str, Any] = field(default_factory=dict)
    time_column: str | None = None
    symbol_column: str | None = "symbol"
    validator: str | None = None
    description: str | None = None


class DatasetContractRegistry:
    """Registry of dataset contracts keyed by dataset name.

    Example::

        registry = DatasetContractRegistry()
        registry.register(OHLCV_CONTRACT)
        contract = registry.get("equity.ohlcv")
    """

    def __init__(self) -> None:
        self._contracts: dict[str, DatasetContract] = {}

    def register(self, contract: DatasetContract) -> None:
        """Register a dataset contract.

        Args:
            contract: The contract to register.

        Raises:
            ValueError: If a contract with the same dataset name is already registered.
        """
        if contract.dataset in self._contracts:
            raise ValueError(
                f"Dataset contract '{contract.dataset}' is already registered."
            )
        self._contracts[contract.dataset] = contract

    def get(self, dataset: str) -> DatasetContract:
        """Return the contract for *dataset*.

        Args:
            dataset: Dotted dataset name, e.g. ``"equity.ohlcv"``.

        Returns:
            The matching :class:`DatasetContract`.

        Raises:
            KeyError: If no contract is registered for *dataset*.
        """
        if dataset not in self._contracts:
            available = sorted(self._contracts)
            raise KeyError(
                f"No contract registered for dataset '{dataset}'. "
                f"Available datasets: {available}"
            )
        return self._contracts[dataset]

    def list(self) -> list[DatasetContract]:
        """Return all registered contracts sorted by dataset name."""
        return [self._contracts[k] for k in sorted(self._contracts)]

    def names(self) -> list[str]:
        """Return all registered dataset names sorted."""
        return sorted(self._contracts)

    def __len__(self) -> int:
        return len(self._contracts)

    def __contains__(self, dataset: str) -> bool:
        return dataset in self._contracts
