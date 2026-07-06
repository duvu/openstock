"""
Index dataset contracts: index OHLCV.
"""

from vnstock.core.contracts.base import DatasetContract

INDEX_OHLCV_CONTRACT = DatasetContract(
    dataset="index.ohlcv",
    required_columns=["symbol", "time", "open", "high", "low", "close", "volume"],
    optional_columns=["value", "provider", "fetched_at"],
    dtype_rules={
        "symbol": "string",
        "time": "datetime64[ns]",
        "open": "float64",
        "high": "float64",
        "low": "float64",
        "close": "float64",
        "volume": "float64",
    },
    time_column="time",
    symbol_column="symbol",
    validator="ohlcv",
    description="OHLCV bars for market index instruments (e.g. VN-Index, HNX-Index).",
)
