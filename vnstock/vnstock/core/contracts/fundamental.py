"""
Fundamental dataset contracts: balance sheet, income statement, cash flow, ratios.
"""

from vnstock.core.contracts.base import DatasetContract

BALANCE_SHEET_CONTRACT = DatasetContract(
    dataset="fundamental.balance_sheet",
    required_columns=["symbol", "year", "period_type"],
    optional_columns=[
        "quarter",
        "total_assets",
        "total_liabilities",
        "equity",
        "cash_and_equivalents",
        "short_term_investments",
        "receivables",
        "inventories",
        "fixed_assets",
        "fetched_at",
        "provider",
    ],
    dtype_rules={
        "symbol": "string",
        "year": "int64",
        "period_type": "string",
    },
    symbol_column="symbol",
    validator=None,
    description="Periodic balance sheet data for listed companies.",
)

INCOME_STATEMENT_CONTRACT = DatasetContract(
    dataset="fundamental.income_statement",
    required_columns=["symbol", "year", "period_type"],
    optional_columns=[
        "quarter",
        "net_revenue",
        "gross_profit",
        "operating_income",
        "net_income",
        "ebitda",
        "eps",
        "fetched_at",
        "provider",
    ],
    dtype_rules={
        "symbol": "string",
        "year": "int64",
        "period_type": "string",
    },
    symbol_column="symbol",
    validator=None,
    description="Periodic income statement data for listed companies.",
)

CASH_FLOW_CONTRACT = DatasetContract(
    dataset="fundamental.cash_flow",
    required_columns=["symbol", "year", "period_type"],
    optional_columns=[
        "quarter",
        "operating_cash_flow",
        "investing_cash_flow",
        "financing_cash_flow",
        "net_cash_change",
        "capex",
        "free_cash_flow",
        "fetched_at",
        "provider",
    ],
    dtype_rules={
        "symbol": "string",
        "year": "int64",
        "period_type": "string",
    },
    symbol_column="symbol",
    validator=None,
    description="Periodic cash flow statement data for listed companies.",
)

FINANCIAL_RATIO_CONTRACT = DatasetContract(
    dataset="fundamental.financial_ratio",
    required_columns=["symbol", "year", "period_type"],
    optional_columns=[
        "quarter",
        "pe",
        "pb",
        "roe",
        "roa",
        "debt_to_equity",
        "current_ratio",
        "gross_margin",
        "net_margin",
        "fetched_at",
        "provider",
    ],
    dtype_rules={
        "symbol": "string",
        "year": "int64",
        "period_type": "string",
    },
    symbol_column="symbol",
    validator=None,
    description="Periodic financial ratios for listed companies.",
)
