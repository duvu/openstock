"""
Equity dataset contracts: OHLCV, quote, and intraday trades.
"""

from vnstock.core.contracts.base import DatasetContract

OHLCV_CONTRACT = DatasetContract(
    dataset="equity.ohlcv",
    required_columns=["symbol", "time", "open", "high", "low", "close", "volume"],
    optional_columns=["value", "provider", "fetched_at", "adjusted"],
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
    description="Daily or intraday OHLCV bars for equity instruments.",
)

QUOTE_CONTRACT = DatasetContract(
    dataset="equity.quote",
    required_columns=[
        "symbol",
        "close_price",
        "volume_accumulated",
    ],
    optional_columns=[
        "open_price",
        "high_price",
        "low_price",
        "reference_price",
        "ceiling_price",
        "floor_price",
        "buy_volume",
        "sell_volume",
        "foreign_buy_volume",
        "foreign_sell_volume",
        "fetched_at",
        "provider",
    ],
    dtype_rules={
        "symbol": "string",
        "close_price": "float64",
        "volume_accumulated": "float64",
    },
    symbol_column="symbol",
    validator="quote",
    description="Real-time or delayed price board snapshot for equities.",
)

INTRADAY_TRADES_CONTRACT = DatasetContract(
    dataset="equity.intraday_trades",
    required_columns=["symbol", "time", "price", "volume", "match_type"],
    optional_columns=["value", "sequence", "fetched_at", "provider"],
    dtype_rules={
        "symbol": "string",
        "time": "datetime64[ns]",
        "price": "float64",
        "volume": "float64",
        "match_type": "string",
    },
    time_column="time",
    symbol_column="symbol",
    validator="intraday_trades",
    description="Intraday tick-by-tick trade records for equity instruments.",
)
