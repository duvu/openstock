"""
Reference dataset contracts: symbol listings and company information.
"""

from vnstock.core.contracts.base import DatasetContract

SYMBOLS_CONTRACT = DatasetContract(
    dataset="reference.symbols",
    required_columns=["symbol", "exchange"],
    optional_columns=[
        "short_name",
        "full_name",
        "industry",
        "industry_code",
        "company_type",
        "listing_date",
        "fetched_at",
        "provider",
    ],
    dtype_rules={
        "symbol": "string",
        "exchange": "string",
    },
    symbol_column="symbol",
    validator=None,
    description="Master symbol listing including exchange and sector classification.",
)

COMPANY_INFO_CONTRACT = DatasetContract(
    dataset="reference.company_info",
    required_columns=["symbol", "exchange"],
    optional_columns=[
        "short_name",
        "full_name",
        "website",
        "industry",
        "industry_code",
        "company_type",
        "established_year",
        "employees",
        "foreign_percent",
        "outstanding_share",
        "issue_share",
        "stock_rating",
        "fetched_at",
        "provider",
    ],
    dtype_rules={
        "symbol": "string",
        "exchange": "string",
    },
    symbol_column="symbol",
    validator=None,
    description="Company profile and fundamental overview data.",
)
