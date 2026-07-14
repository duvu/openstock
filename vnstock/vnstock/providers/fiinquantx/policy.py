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
        "index.ohlcv",
        "reference.company_info",
        "reference.index_membership_snapshot",
        "reference.sector_membership_snapshot",
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
