from __future__ import annotations

ALLOWED_MEMBER_NAMES = frozenset(
    {
        "FiinSession",
        "TickerList",
        "BasicInfor",
        "Fetch_Trading_Data",
        "PriceStatistics",
        "MarketDepth",
        "MarketBreadth",
        "FundamentalAnalysis",
    }
)

FORBIDDEN_MEMBER_NAMES = frozenset(
    {
        "broker",
        "account",
        "cash",
        "buying_power",
        "loan",
        "funding",
        "margin",
        "order",
        "orders",
        "position",
        "positions",
        "portfolio",
        "allocation",
        "transfer",
        "execution",
    }
)

DOCUMENTED_DATASETS = frozenset(
    {
        "equity.ohlcv",
        "foreign_flow.daily",
        "foreign_ownership.daily",
        "fundamental.balance_sheet",
        "fundamental.cash_flow",
        "fundamental.financial_ratio",
        "fundamental.income_statement",
        "index.ohlcv",
        "investor_flow.daily",
        "market.breadth_snapshot",
        "market.depth_snapshot",
        "market.liquidity_daily",
        "market.market_cap_daily",
        "market.price_limits_daily",
        "reference.company_info",
        "reference.free_float_observation",
        "reference.index_membership_snapshot",
        "reference.sector_membership_snapshot",
        "reference.symbols",
        "valuation.index_observation",
        "valuation.sector_observation",
        "valuation.stock_observation",
    }
)

IMPLEMENTED_DATASETS = frozenset(
    {
        "equity.ohlcv",
        "index.ohlcv",
        "reference.index_membership_snapshot",
        "reference.sector_membership_snapshot",
    }
)
