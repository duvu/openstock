"""Provider capability registry for vnstock.

Declares which capabilities each provider supports, and exposes a query
helper so the router and matrix generator can look up providers by
dataset type, asset class, method, and interval.

Usage::

    from vnstock.core.provider.capabilities import (
        CAPABILITIES,
        query_capabilities,
    )

    caps = query_capabilities(dataset_type="ohlcv", asset_class="equity")
    caps = query_capabilities(dataset_type="ohlcv", interval="1D")
"""

from __future__ import annotations

from typing import List, Optional

from vnstock.core.provider.models import ProviderCapability

# ---------------------------------------------------------------------------
# KBS capabilities
# ---------------------------------------------------------------------------
_KBS_OHLCV_EQUITY = ProviderCapability(
    provider="KBS",
    dataset_type="ohlcv",
    asset_class="equity",
    method="history",
    intervals=["1m", "5m", "15m", "30m", "1H", "1D", "1W", "1M"],
    supports_history=True,
    supports_intraday=True,
    is_live_testable=True,
    notes="KBS IIS/SAS historical quotes. Supports equity and index.",
)

_KBS_OHLCV_INDEX = ProviderCapability(
    provider="KBS",
    dataset_type="ohlcv",
    asset_class="index",
    method="history",
    intervals=["1D", "1W", "1M"],
    supports_history=True,
    is_live_testable=True,
    notes="KBS index OHLCV. Supported indices: VNINDEX, HNXINDEX, UPCOMINDEX, VN30, HNX30, VN100.",
)

_KBS_PRICE_BOARD_EQUITY = ProviderCapability(
    provider="KBS",
    dataset_type="price_board",
    asset_class="equity",
    method="price_board",
    intervals=[],
    supports_live_snapshot=True,
    supports_batch=True,
    is_live_testable=True,
    notes="KBS ISS price board for equity symbols.",
)

_KBS_INTRADAY_EQUITY = ProviderCapability(
    provider="KBS",
    dataset_type="intraday_trades",
    asset_class="equity",
    method="intraday",
    intervals=[],
    supports_intraday=True,
    is_live_testable=True,
    notes="KBS intraday tick data.",
)

# ---------------------------------------------------------------------------
# VCI capabilities
# ---------------------------------------------------------------------------
_VCI_OHLCV_EQUITY = ProviderCapability(
    provider="VCI",
    dataset_type="ohlcv",
    asset_class="equity",
    method="history",
    intervals=["1m", "5m", "15m", "30m", "1H", "1D", "1W", "1M"],
    supports_history=True,
    supports_intraday=True,
    is_live_testable=True,
    notes="VCI (Vietcap) chart OHLCV. VCI maps 5m/15m/30m via resampling from 1m.",
)

_VCI_OHLCV_INDEX = ProviderCapability(
    provider="VCI",
    dataset_type="ohlcv",
    asset_class="index",
    method="history",
    intervals=["1D", "1W", "1M"],
    supports_history=True,
    is_live_testable=True,
    notes="VCI index OHLCV. Resampled from daily data.",
)

_VCI_PRICE_BOARD_EQUITY = ProviderCapability(
    provider="VCI",
    dataset_type="price_board",
    asset_class="equity",
    method="price_board",
    intervals=[],
    supports_live_snapshot=True,
    supports_batch=True,
    is_live_testable=True,
    notes="VCI price board (market watch) for equity.",
)

_VCI_INTRADAY_EQUITY = ProviderCapability(
    provider="VCI",
    dataset_type="intraday_trades",
    asset_class="equity",
    method="intraday",
    intervals=[],
    supports_intraday=True,
    is_live_testable=True,
    notes="VCI intraday tick data via market-watch API.",
)

# ---------------------------------------------------------------------------
# DNSE capabilities
# ---------------------------------------------------------------------------
_DNSE_OHLCV_EQUITY = ProviderCapability(
    provider="DNSE",
    dataset_type="ohlcv",
    asset_class="equity",
    method="history",
    intervals=["1m", "5m", "15m", "30m", "1H", "1D", "1W", "1M"],
    supports_history=True,
    supports_intraday=True,
    is_live_testable=True,
    notes="DNSE (Entrade) chart-api OHLCV.",
)

_DNSE_PRICE_BOARD_EQUITY = ProviderCapability(
    provider="DNSE",
    dataset_type="price_board",
    asset_class="equity",
    method="price_board",
    intervals=[],
    supports_live_snapshot=True,
    supports_batch=True,
    is_live_testable=True,
    notes="DNSE /chart-api/v2/quotes price board.",
)

_DNSE_INTRADAY_EQUITY = ProviderCapability(
    provider="DNSE",
    dataset_type="intraday_trades",
    asset_class="equity",
    method="intraday",
    intervals=[],
    supports_intraday=True,
    requires_auth=True,
    is_live_testable=False,
    notes="DNSE intraday requires authenticated user session; not suitable for public CI.",
)

# ---------------------------------------------------------------------------
# MSN capabilities
# ---------------------------------------------------------------------------
_MSN_OHLCV_EQUITY = ProviderCapability(
    provider="MSN",
    dataset_type="ohlcv",
    asset_class="equity",
    method="history",
    intervals=["1D"],
    supports_history=True,
    is_live_testable=True,
    notes="MSN daily OHLCV only. No intraday. Useful for a few popular symbols.",
)

# ---------------------------------------------------------------------------
# FMP capabilities
# ---------------------------------------------------------------------------
_FMP_OHLCV_EQUITY = ProviderCapability(
    provider="FMP",
    dataset_type="ohlcv",
    asset_class="equity",
    method="history",
    intervals=["1D", "1W", "1M"],
    supports_history=True,
    requires_auth=True,
    is_live_testable=True,
    notes="Financial Modeling Prep API. Requires FMP API key (FMP_API_KEY env var).",
)

# ---------------------------------------------------------------------------
# FMarket capabilities
# ---------------------------------------------------------------------------
_FMARKET_FUND_NAV = ProviderCapability(
    provider="FMARKET",
    dataset_type="fund_nav",
    asset_class="fund",
    method="nav",
    intervals=["1D"],
    supports_history=True,
    is_live_testable=True,
    notes="FMarket fund NAV historical data.",
)

# ---------------------------------------------------------------------------
# TCBS capabilities
# ---------------------------------------------------------------------------
_TCBS_OHLCV_EQUITY = ProviderCapability(
    provider="TCBS",
    dataset_type="ohlcv",
    asset_class="equity",
    method="history",
    intervals=["1m", "5m", "15m", "30m", "1H", "1D", "1W", "1M"],
    supports_history=True,
    supports_intraday=True,
    requires_auth=True,
    is_live_testable=True,
    notes=(
        "TCBS bars-long-term OHLCV. Endpoint fallback order: "
        "/stock/v2/stock/bars-long-term → /stock-insight/v2 → /stock-insight/v1. "
        "Requires Bearer token — run `vnstock-tcbs-login`. "
        "Unofficial endpoint — may drift without notice."
    ),
)

_TCBS_PRICE_BOARD_EQUITY = ProviderCapability(
    provider="TCBS",
    dataset_type="price_board",
    asset_class="equity",
    method="price_board",
    intervals=[],
    supports_live_snapshot=True,
    supports_batch=True,
    requires_auth=True,
    is_live_testable=True,
    notes="TCBS /stock/v1/stock/second-tc-price price board. Requires Bearer token.",
)

_TCBS_INTRADAY_EQUITY = ProviderCapability(
    provider="TCBS",
    dataset_type="intraday_trades",
    asset_class="equity",
    method="intraday",
    intervals=[],
    supports_intraday=True,
    requires_auth=True,
    is_live_testable=True,
    notes="TCBS /stock/v1/intraday/{symbol}/his/paging. Experimental; requires Bearer token.",
)

_TCBS_COMPANY_OVERVIEW = ProviderCapability(
    provider="TCBS",
    dataset_type="company_overview",
    asset_class="equity",
    method="overview",
    intervals=[],
    supports_history=False,
    requires_auth=True,
    is_live_testable=True,
    notes="TCBS company overview via tcanalysis endpoints. Requires Bearer token.",
)

_TCBS_FINANCIAL_STATEMENTS = ProviderCapability(
    provider="TCBS",
    dataset_type="financial_statements",
    asset_class="equity",
    method="balance_sheet",
    intervals=[],
    supports_history=True,
    requires_auth=True,
    is_live_testable=True,
    notes=(
        "TCBS /stock-insight/v1/finance/{symbol}/{report_type}. "
        "Supports balance-sheet, income-statement, cash-flow, financialratio. "
        "Requires Bearer token."
    ),
)

_TCBS_SCREENER = ProviderCapability(
    provider="TCBS",
    dataset_type="screener",
    asset_class="equity",
    method="scan",
    intervals=[],
    requires_auth=True,
    is_live_testable=False,
    notes=(
        "TCBS /ligo/v1/watchlist/preview screener. EXPERIMENTAL — unofficial POST endpoint. "
        "Requires Bearer token. Vendor signal fields are raw data, not investment advice."
    ),
)

# ---------------------------------------------------------------------------
# Master capability list
# ---------------------------------------------------------------------------
CAPABILITIES: List[ProviderCapability] = [
    # KBS
    _KBS_OHLCV_EQUITY,
    _KBS_OHLCV_INDEX,
    _KBS_PRICE_BOARD_EQUITY,
    _KBS_INTRADAY_EQUITY,
    # VCI
    _VCI_OHLCV_EQUITY,
    _VCI_OHLCV_INDEX,
    _VCI_PRICE_BOARD_EQUITY,
    _VCI_INTRADAY_EQUITY,
    # DNSE
    _DNSE_OHLCV_EQUITY,
    _DNSE_PRICE_BOARD_EQUITY,
    _DNSE_INTRADAY_EQUITY,
    # TCBS
    _TCBS_OHLCV_EQUITY,
    _TCBS_PRICE_BOARD_EQUITY,
    _TCBS_INTRADAY_EQUITY,
    _TCBS_COMPANY_OVERVIEW,
    _TCBS_FINANCIAL_STATEMENTS,
    _TCBS_SCREENER,
    # MSN
    _MSN_OHLCV_EQUITY,
    # FMP
    _FMP_OHLCV_EQUITY,
    # FMarket
    _FMARKET_FUND_NAV,
]


def query_capabilities(
    *,
    provider: Optional[str] = None,
    dataset_type: Optional[str] = None,
    asset_class: Optional[str] = None,
    method: Optional[str] = None,
    interval: Optional[str] = None,
) -> List[ProviderCapability]:
    """Query the capability registry with optional filters.

    All provided filters are ANDed together.  At least one filter should be
    supplied; calling with no arguments returns all capabilities.

    Args:
        provider: Filter by provider name (case-insensitive).
        dataset_type: Filter by dataset type (e.g. ``"ohlcv"``).
        asset_class: Filter by asset class (e.g. ``"equity"``).
        method: Filter by method name.
        interval: Filter to capabilities whose ``intervals`` list contains
            this value.

    Returns:
        Filtered list of :class:`ProviderCapability` objects.  Returns an
        empty list when no match is found — never raises for unsupported
        combinations.
    """
    results = CAPABILITIES

    if provider is not None:
        needle = provider.upper()
        results = [c for c in results if c.provider.upper() == needle]

    if dataset_type is not None:
        results = [c for c in results if c.dataset_type == dataset_type]

    if asset_class is not None:
        results = [c for c in results if c.asset_class == asset_class]

    if method is not None:
        results = [c for c in results if c.method == method]

    if interval is not None:
        results = [c for c in results if interval in c.intervals]

    return results
