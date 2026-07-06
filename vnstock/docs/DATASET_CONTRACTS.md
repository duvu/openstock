# Dataset Contracts

Dataset contracts define the canonical shape of financial datasets in `vnstock`.

## Overview

A `DatasetContract` specifies:

- **dataset**: dotted name (e.g. `equity.ohlcv`)
- **required_columns**: columns that must be present
- **optional_columns**: columns that may be present
- **dtype_rules**: expected pandas dtype per column
- **time_column**: name of the primary timestamp column
- **symbol_column**: name of the ticker column
- **validator**: quality validator binding key
- **description**: human-readable description

## Built-in contracts

| Dataset | Required columns |
|---------|-----------------|
| `equity.ohlcv` | symbol, time, open, high, low, close, volume |
| `equity.quote` | symbol, close_price, volume_accumulated |
| `equity.intraday_trades` | symbol, time, price, volume, match_type |
| `index.ohlcv` | symbol, time, open, high, low, close, volume |
| `reference.symbols` | symbol, exchange |
| `reference.company_info` | symbol, exchange |
| `fundamental.balance_sheet` | symbol, year, period_type |
| `fundamental.income_statement` | symbol, year, period_type |
| `fundamental.cash_flow` | symbol, year, period_type |
| `fundamental.financial_ratio` | symbol, year, period_type |
| `fund.nav` | symbol, time, nav |
| `foreign_flow.daily` | symbol, time, buy_volume, sell_volume |

## Usage

```python
from vnstock.core.contracts import CONTRACT_REGISTRY

# Retrieve a contract
contract = CONTRACT_REGISTRY.get("equity.ohlcv")

# Check required columns
print(contract.required_columns)

# Check dtype rules
print(contract.dtype_rules)

# List all registered datasets
print(CONTRACT_REGISTRY.names())
```

## Adding a custom contract

```python
from vnstock.core.contracts.base import DatasetContract, DatasetContractRegistry
from vnstock.core.contracts import CONTRACT_REGISTRY

custom = DatasetContract(
    dataset="custom.my_dataset",
    required_columns=["symbol", "time", "value"],
    dtype_rules={"symbol": "string", "time": "datetime64[ns]", "value": "float64"},
    time_column="time",
    description="My custom dataset.",
)

CONTRACT_REGISTRY.register(custom)
```
