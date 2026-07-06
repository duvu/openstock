"""
FMP (Financial Modeling Prep) provider capability declarations and limitations.

FMP provides OHLCV and fundamental data for global equities via the FMP API.
Requires a valid FMP_API_KEY environment variable.

Data-only scope: broker, order, account, and portfolio capabilities are
outside scope and must not be added here.
"""

# ---------------------------------------------------------------------------
# Capability declarations
# ---------------------------------------------------------------------------

FMP_CAPABILITIES: dict = {
    "equity.ohlcv": {
        "supported": True,
        "status": "stable",
        "auth_required": True,
        "intervals": ["1m", "5m", "15m", "30m", "1H", "1D", "1W", "1M"],
        "notes": "FMP OHLCV for global equities. Requires FMP_API_KEY.",
    },
    "equity.quote": {
        "supported": True,
        "status": "stable",
        "auth_required": True,
        "intervals": [],
        "notes": "Real-time and delayed quote snapshots. Requires FMP_API_KEY.",
    },
    "fundamental.balance_sheet": {
        "supported": True,
        "status": "stable",
        "auth_required": True,
        "intervals": [],
        "notes": "Balance sheet for global equities. Requires FMP_API_KEY.",
    },
    "fundamental.income_statement": {
        "supported": True,
        "status": "stable",
        "auth_required": True,
        "intervals": [],
        "notes": "Income statement. Requires FMP_API_KEY.",
    },
    "fundamental.cash_flow": {
        "supported": True,
        "status": "stable",
        "auth_required": True,
        "intervals": [],
        "notes": "Cash flow. Requires FMP_API_KEY.",
    },
}

# ---------------------------------------------------------------------------
# Limitations metadata
# ---------------------------------------------------------------------------

FMP_LIMITATIONS: dict = {
    "provider_status": "authenticated_commercial_api",
    "known_limitations": [
        "requires FMP_API_KEY environment variable",
        "rate limits depend on API plan tier",
        "Vietnamese stock coverage may be incomplete",
    ],
    "coverage_gaps": [
        "no fund data",
        "no price board data",
    ],
    "schema_drift_risk": "low",
    "excluded_capabilities": [
        "broker.login",
        "broker.order",
        "broker.account",
        "portfolio.management",
        "trading.signals",
        "trading.recommendations",
    ],
}
