"""
Unit tests for dataset contract registry.
"""

import pytest

from vnstock.core.contracts import CONTRACT_REGISTRY
from vnstock.core.contracts.base import DatasetContract, DatasetContractRegistry


class TestDatasetContractRegistry:
    """Tests for DatasetContractRegistry."""

    def test_register_and_get(self):
        """Task 16: Contract registration round-trip."""
        registry = DatasetContractRegistry()
        contract = DatasetContract(
            dataset="test.sample",
            required_columns=["symbol", "time", "value"],
        )
        registry.register(contract)
        retrieved = registry.get("test.sample")
        assert retrieved is contract

    def test_duplicate_registration_raises(self):
        """Task 17: Duplicate dataset registration raises ValueError."""
        registry = DatasetContractRegistry()
        contract = DatasetContract(
            dataset="test.duplicate",
            required_columns=["symbol"],
        )
        registry.register(contract)
        with pytest.raises(ValueError, match="already registered"):
            registry.register(contract)

    def test_unknown_dataset_raises(self):
        """Task 18: Unknown dataset lookup raises KeyError."""
        registry = DatasetContractRegistry()
        with pytest.raises(KeyError, match="No contract registered"):
            registry.get("nonexistent.dataset")

    def test_list_returns_sorted(self):
        """list() returns contracts sorted by dataset name."""
        registry = DatasetContractRegistry()
        for name in ["z.last", "a.first", "m.middle"]:
            registry.register(DatasetContract(dataset=name, required_columns=[]))
        names = [c.dataset for c in registry.list()]
        assert names == ["a.first", "m.middle", "z.last"]

    def test_names(self):
        """names() returns sorted dataset name strings."""
        registry = DatasetContractRegistry()
        registry.register(DatasetContract(dataset="b.two", required_columns=[]))
        registry.register(DatasetContract(dataset="a.one", required_columns=[]))
        assert registry.names() == ["a.one", "b.two"]

    def test_contains(self):
        """__contains__ works as membership check."""
        registry = DatasetContractRegistry()
        registry.register(DatasetContract(dataset="x.test", required_columns=[]))
        assert "x.test" in registry
        assert "missing.dataset" not in registry

    def test_len(self):
        """__len__ reports number of registered contracts."""
        registry = DatasetContractRegistry()
        assert len(registry) == 0
        registry.register(DatasetContract(dataset="q.one", required_columns=[]))
        assert len(registry) == 1


class TestBuiltinContractRegistry:
    """Tests for the module-level CONTRACT_REGISTRY."""

    def test_equity_ohlcv_exists(self):
        """equity.ohlcv contract is registered."""
        contract = CONTRACT_REGISTRY.get("equity.ohlcv")
        assert contract.dataset == "equity.ohlcv"

    def test_equity_ohlcv_required_columns(self):
        """equity.ohlcv contract has all required columns per spec."""
        contract = CONTRACT_REGISTRY.get("equity.ohlcv")
        required = set(contract.required_columns)
        assert {"symbol", "time", "open", "high", "low", "close", "volume"}.issubset(
            required
        )

    def test_fifteen_builtin_contracts(self):
        """All 15 built-in dataset contracts are registered."""
        assert len(CONTRACT_REGISTRY) == 15

    def test_all_expected_datasets_registered(self):
        """All expected dataset names are registered."""
        expected = {
            "equity.ohlcv",
            "equity.quote",
            "equity.intraday_trades",
            "index.ohlcv",
            "reference.symbols",
            "reference.company_info",
            "reference.corporate_actions",
            "reference.index_membership_snapshot",
            "reference.sector_membership_snapshot",
            "fundamental.balance_sheet",
            "fundamental.income_statement",
            "fundamental.cash_flow",
            "fundamental.financial_ratio",
            "fund.nav",
            "foreign_flow.daily",
        }
        registered = set(CONTRACT_REGISTRY.names())
        assert expected == registered

    def test_ohlcv_has_validator(self):
        """equity.ohlcv contract has a validator binding."""
        contract = CONTRACT_REGISTRY.get("equity.ohlcv")
        assert contract.validator is not None

    def test_ohlcv_dtype_rules(self):
        """equity.ohlcv dtype rules include time as datetime64."""
        contract = CONTRACT_REGISTRY.get("equity.ohlcv")
        assert contract.dtype_rules.get("time") == "datetime64[ns]"

    def test_contract_is_frozen(self):
        """DatasetContract is frozen (immutable)."""
        contract = CONTRACT_REGISTRY.get("equity.ohlcv")
        with pytest.raises((AttributeError, TypeError)):
            contract.dataset = "mutated"  # type: ignore[misc]
