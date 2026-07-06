"""
Dataset contract definitions for vnstock.

Contracts define the canonical shape, column requirements, dtype rules,
and validator bindings for each supported dataset type.

Usage::

    from vnstock.core.contracts import CONTRACT_REGISTRY
    from vnstock.core.contracts.base import DatasetContract

    contract = CONTRACT_REGISTRY.get("equity.ohlcv")
    print(contract.required_columns)
"""

from vnstock.core.contracts.base import DatasetContract, DatasetContractRegistry
from vnstock.core.contracts.equity import (
    INTRADAY_TRADES_CONTRACT,
    OHLCV_CONTRACT,
    QUOTE_CONTRACT,
)
from vnstock.core.contracts.foreign_flow import FOREIGN_FLOW_DAILY_CONTRACT
from vnstock.core.contracts.fund import FUND_NAV_CONTRACT
from vnstock.core.contracts.fundamental import (
    BALANCE_SHEET_CONTRACT,
    CASH_FLOW_CONTRACT,
    FINANCIAL_RATIO_CONTRACT,
    INCOME_STATEMENT_CONTRACT,
)
from vnstock.core.contracts.index import INDEX_OHLCV_CONTRACT
from vnstock.core.contracts.reference import COMPANY_INFO_CONTRACT, SYMBOLS_CONTRACT

# Module-level registry — all built-in contracts are pre-registered here.
CONTRACT_REGISTRY = DatasetContractRegistry()

_BUILTIN_CONTRACTS = [
    OHLCV_CONTRACT,
    QUOTE_CONTRACT,
    INTRADAY_TRADES_CONTRACT,
    INDEX_OHLCV_CONTRACT,
    SYMBOLS_CONTRACT,
    COMPANY_INFO_CONTRACT,
    BALANCE_SHEET_CONTRACT,
    INCOME_STATEMENT_CONTRACT,
    CASH_FLOW_CONTRACT,
    FINANCIAL_RATIO_CONTRACT,
    FUND_NAV_CONTRACT,
    FOREIGN_FLOW_DAILY_CONTRACT,
]

for _contract in _BUILTIN_CONTRACTS:
    CONTRACT_REGISTRY.register(_contract)

__all__ = [
    "DatasetContract",
    "DatasetContractRegistry",
    "CONTRACT_REGISTRY",
    "OHLCV_CONTRACT",
    "QUOTE_CONTRACT",
    "INTRADAY_TRADES_CONTRACT",
    "INDEX_OHLCV_CONTRACT",
    "SYMBOLS_CONTRACT",
    "COMPANY_INFO_CONTRACT",
    "BALANCE_SHEET_CONTRACT",
    "INCOME_STATEMENT_CONTRACT",
    "CASH_FLOW_CONTRACT",
    "FINANCIAL_RATIO_CONTRACT",
    "FUND_NAV_CONTRACT",
    "FOREIGN_FLOW_DAILY_CONTRACT",
]
