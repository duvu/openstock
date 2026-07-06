"""
Fund dataset contracts: NAV (Net Asset Value).
"""

from vnstock.core.contracts.base import DatasetContract

FUND_NAV_CONTRACT = DatasetContract(
    dataset="fund.nav",
    required_columns=["symbol", "time", "nav"],
    optional_columns=[
        "nav_change",
        "nav_change_pct",
        "fund_type",
        "aum",
        "fetched_at",
        "provider",
    ],
    dtype_rules={
        "symbol": "string",
        "time": "datetime64[ns]",
        "nav": "float64",
    },
    time_column="time",
    symbol_column="symbol",
    validator=None,
    description="Net Asset Value (NAV) time series for investment funds.",
)
