"""Constants for TCBS data source.

SCOPE / SAFETY GATE
-------------------
Only read-only market-data endpoints are defined here.  No broker, account,
order, iCopy, margin, or transfer endpoint URLs are included.

Authenticated endpoints — all market-data APIs now require a Bearer token.
Use ``TCBSAuth`` to obtain a token, or set ``TCBS_BEARER_TOKEN`` env var.
The API contract may drift without notice.
"""

# ---------------------------------------------------------------------------
# Base URLs
# ---------------------------------------------------------------------------
# All market-data APIs migrated to apiextaws (requires Bearer token auth)
_BASE_URL = "https://apiextaws.tcbs.com.vn"

# Legacy public base (decommissioned — routes return 404 as of 2025)
_BASE_URL_PUBLIC_LEGACY = "https://apipubaws.tcbs.com.vn"

# ---------------------------------------------------------------------------
# OHLCV / Quote endpoints (fallback order: v2 stock → v2 insight → v1 insight)
# ---------------------------------------------------------------------------
_OHLCV_URL_PRIMARY = f"{_BASE_URL}/stock/v2/stock/bars-long-term"
_OHLCV_URL_FALLBACK_1 = f"{_BASE_URL}/stock-insight/v2/stock/bars-long-term"
_OHLCV_URL_FALLBACK_2 = f"{_BASE_URL}/stock-insight/v1/stock/bars-long-term"

# All OHLCV endpoints tried in order
_OHLCV_URLS = [
    _OHLCV_URL_PRIMARY,
    _OHLCV_URL_FALLBACK_1,
    _OHLCV_URL_FALLBACK_2,
]

# Intraday tick data (experimental, paged)
_INTRADAY_URL = f"{_BASE_URL}/stock/v1/intraday/{{symbol}}/his/paging"

# ---------------------------------------------------------------------------
# Price board endpoint
# ---------------------------------------------------------------------------
_PRICE_BOARD_URL = f"{_BASE_URL}/stock/v1/stock/second-tc-price"

# ---------------------------------------------------------------------------
# Company endpoints
# ---------------------------------------------------------------------------
_COMPANY_TICKER_OVERVIEW_URL = f"{_BASE_URL}/tcanalysis/v1/ticker/{{symbol}}/overview"
_COMPANY_OVERVIEW_URL = f"{_BASE_URL}/tcanalysis/v1/company/{{symbol}}/overview"
_COMPANY_SHAREHOLDERS_URL = (
    f"{_BASE_URL}/tcanalysis/v1/company/{{symbol}}/large-share-holders"
)
_COMPANY_INSIDER_DEALING_URL = (
    f"{_BASE_URL}/tcanalysis/v1/company/{{symbol}}/insider-dealing"
)
_COMPANY_SUBSIDIARIES_URL = (
    f"{_BASE_URL}/stock-insight/v1/company/{{symbol}}/subsidiaries"
)
_COMPANY_OFFICERS_URL = f"{_BASE_URL}/stock-insight/v1/company/{{symbol}}/officers"
_COMPANY_EVENTS_NEWS_URL = f"{_BASE_URL}/tcanalysis/v1/ticker/{{symbol}}/events-news"
_COMPANY_ACTIVITY_NEWS_URL = (
    f"{_BASE_URL}/tcanalysis/v1/ticker/{{symbol}}/activity-news"
)
_COMPANY_DIVIDENDS_URL = f"{_BASE_URL}/stock-insight/v1/company/{{symbol}}/dividends"

# ---------------------------------------------------------------------------
# Financial endpoints
# ---------------------------------------------------------------------------
_FINANCE_URL = f"{_BASE_URL}/stock-insight/v1/finance/{{symbol}}/{{report_type}}"

# Report type identifiers used in the URL path
_REPORT_TYPE_BALANCE_SHEET = "balance-sheet"
_REPORT_TYPE_INCOME_STATEMENT = "income-statement"
_REPORT_TYPE_CASH_FLOW = "cash-flow"
_REPORT_TYPE_RATIO = "financialratio"

# ---------------------------------------------------------------------------
# Screener endpoint (experimental)
# ---------------------------------------------------------------------------
_SCREENER_URL = f"{_BASE_URL}/ligo/v1/watchlist/preview"

# ---------------------------------------------------------------------------
# Interval map: user-friendly key → TCBS API resolution string
# ---------------------------------------------------------------------------
_INTERVAL_MAP = {
    # Minute intervals
    "1m": "1",
    "5m": "5",
    "15m": "15",
    "30m": "30",
    # Hour intervals
    "1H": "60",
    "1h": "60",
    "60m": "60",
    # Daily
    "1D": "D",
    "1d": "D",
    "D": "D",
    "d": "D",
    "daily": "D",
    # Weekly
    "1W": "W",
    "1w": "W",
    "W": "W",
    "w": "W",
    "weekly": "W",
    # Monthly
    "1M": "M",
    "M": "M",
    "monthly": "M",
}

# ---------------------------------------------------------------------------
# OHLCV column mapping
# TCBS API returns: t (time), o (open), h (high), l (low), c (close), v (volume)
# ---------------------------------------------------------------------------
_OHLC_MAP = {
    "t": "time",
    "o": "open",
    "h": "high",
    "l": "low",
    "c": "close",
    "v": "volume",
}

# Data type mapping for OHLCV data
_OHLC_DTYPE = {
    "time": "datetime64[ns]",
    "open": "float64",
    "high": "float64",
    "low": "float64",
    "close": "float64",
    "volume": "int64",
}

# ---------------------------------------------------------------------------
# Intraday column mapping (experimental)
# ---------------------------------------------------------------------------
_INTRADAY_MAP = {
    "t": "time",
    "p": "price",
    "v": "volume",
    "a": "match_type",
    "id": "id",
    "seq": "id",
    "time": "time",
    "price": "price",
    "volume": "volume",
    "side": "match_type",
}

_INTRADAY_DTYPE = {
    "time": "object",
    "price": "float64",
    "volume": "int64",
    "match_type": "object",
    "id": "object",
}

_INTRADAY_CORE_COLUMNS = ["time", "price", "volume", "match_type", "id"]

# ---------------------------------------------------------------------------
# Price board column mapping
# TCBS /stock/v1/stock/second-tc-price returns per-ticker objects
# ---------------------------------------------------------------------------
_PRICE_BOARD_MAP = {
    "t": "symbol",
    "ticker": "symbol",
    "sym": "symbol",
    "cp": "close_price",
    "c": "close_price",
    "lastPrice": "close_price",
    "fv": "floor_price",
    "cv": "ceiling_price",
    "r": "reference_price",
    "re": "reference_price",
    "o": "open_price",
    "h": "high_price",
    "l": "low_price",
    "lot": "volume_last",
    "lastVolume": "volume_last",
    "ot": "volume_accumulated",
    "totalVolume": "volume_accumulated",
    "totalVal": "total_value",
    "totalValue": "total_value",
    "ch": "price_change",
    "change": "price_change",
    "rg": "percent_change",
    "changePercent": "percent_change",
    # Bid / Ask
    "b1": "bid_price_1",
    "bv1": "bid_vol_1",
    "b2": "bid_price_2",
    "bv2": "bid_vol_2",
    "b3": "bid_price_3",
    "bv3": "bid_vol_3",
    "s1": "ask_price_1",
    "sv1": "ask_vol_1",
    "s2": "ask_price_2",
    "sv2": "ask_vol_2",
    "s3": "ask_price_3",
    "sv3": "ask_vol_3",
    # Foreign flow
    "fBuyVol": "foreign_buy_volume",
    "fSellVol": "foreign_sell_volume",
    "fRoom": "foreign_room",
    "fr": "foreign_room",
}

_PRICE_BOARD_STANDARD_COLUMNS = [
    "symbol",
    "close_price",
    "volume_accumulated",
    "ceiling_price",
    "floor_price",
    "reference_price",
    "open_price",
    "high_price",
    "low_price",
    "volume_last",
    "total_value",
    "price_change",
    "percent_change",
    "bid_price_1",
    "bid_vol_1",
    "bid_price_2",
    "bid_vol_2",
    "bid_price_3",
    "bid_vol_3",
    "ask_price_1",
    "ask_vol_1",
    "ask_price_2",
    "ask_vol_2",
    "ask_price_3",
    "ask_vol_3",
    "foreign_buy_volume",
    "foreign_sell_volume",
    "foreign_room",
]

# ---------------------------------------------------------------------------
# Company overview column mapping
# ---------------------------------------------------------------------------
_COMPANY_OVERVIEW_MAP = {
    # ticker overview fields
    "ticker": "symbol",
    "exchange": "exchange",
    "industry": "industry",
    "industryId": "industry_id",
    "industryIdV2": "industry_id_v2",
    "companyType": "company_type",
    "shortName": "short_name",
    "website": "website",
    "foreignPercent": "foreign_percent",
    "outstandingShare": "outstanding_share",
    "issueShare": "issue_share",
    "establishedYear": "established_year",
    "noEmployees": "employees",
    "stockRating": "stock_rating",
    # fallback field names
    "symbol": "symbol",
    "industryEn": "industry",
    "comTypeCode": "company_type",
}

# Normalized company overview output columns
_COMPANY_OVERVIEW_COLUMNS = [
    "symbol",
    "exchange",
    "industry",
    "industry_id",
    "industry_id_v2",
    "company_type",
    "short_name",
    "website",
    "foreign_percent",
    "outstanding_share",
    "issue_share",
    "established_year",
    "employees",
    "stock_rating",
]

# ---------------------------------------------------------------------------
# Financial report period mapping
# ---------------------------------------------------------------------------
_FINANCIAL_PERIOD_MAP = {
    "year": True,  # yearly=true
    "quarter": False,  # yearly=false
}
