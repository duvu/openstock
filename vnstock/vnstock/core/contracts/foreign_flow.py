"""
Foreign flow dataset contracts: daily foreign investor buy/sell data.
"""

from vnstock.core.contracts.base import DatasetContract

FOREIGN_FLOW_DAILY_CONTRACT = DatasetContract(
    dataset="foreign_flow.daily",
    required_columns=["symbol", "time", "buy_volume", "sell_volume"],
    optional_columns=[
        "buy_value",
        "sell_value",
        "net_volume",
        "net_value",
        "room_remaining",
        "fetched_at",
        "provider",
    ],
    dtype_rules={
        "symbol": "string",
        "time": "datetime64[ns]",
        "buy_volume": "float64",
        "sell_volume": "float64",
    },
    time_column="time",
    symbol_column="symbol",
    validator=None,
    description="Daily foreign investor buy/sell activity for equity instruments.",
)
