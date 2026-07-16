"""
VCI provider capability declarations and limitations metadata.

VCI is a stable alternative provider for Vietnamese market data with
strong coverage of fundamental and company data.

Data-only scope: broker, order, account, and portfolio capabilities are
outside scope and must not be added here.
"""

# ---------------------------------------------------------------------------
# Capability declarations
# ---------------------------------------------------------------------------

VCI_CAPABILITIES: dict = {
    "equity.ohlcv": {
        "supported": True,
        "status": "stable",
        "auth_required": False,
        "intervals": ["1m", "5m", "15m", "30m", "1H", "1D", "1W", "1M"],
        "notes": "OHLCV bars for Vietnamese equities.",
    },
    "equity.quote": {
        "supported": True,
        "status": "stable",
        "auth_required": False,
        "intervals": [],
        "notes": "Price board snapshot via VCI.",
    },
    "equity.intraday_trades": {
        "supported": True,
        "status": "stable",
        "auth_required": False,
        "intervals": [],
        "notes": "Intraday tick records.",
    },
    "index.ohlcv": {
        "supported": True,
        "status": "stable",
        "auth_required": False,
        "intervals": ["1D", "1W", "1M"],
        "notes": "Index OHLCV bars.",
    },
    "reference.symbols": {
        "supported": True,
        "status": "stable",
        "auth_required": False,
        "intervals": [],
        "notes": "Full symbol listing with ICB industry classification.",
    },
    "reference.corporate_actions": {
        "supported": True,
        "status": "partial",
        "auth_required": False,
        "intervals": [],
        "request_modes": ["symbol_date_range"],
        "notes": "Provider event feed normalized as market-data evidence; not an official disclosure source.",
    },
    "reference.company_info": {
        "supported": True,
        "status": "stable",
        "auth_required": False,
        "intervals": [],
        "notes": "Company overview including officers, shareholders.",
    },
    "fundamental.balance_sheet": {
        "supported": True,
        "status": "stable",
        "auth_required": False,
        "intervals": [],
        "notes": "Annual and quarterly balance sheet via VCI.",
    },
    "fundamental.income_statement": {
        "supported": True,
        "status": "stable",
        "auth_required": False,
        "intervals": [],
        "notes": "Annual and quarterly income statement.",
    },
    "fundamental.cash_flow": {
        "supported": True,
        "status": "stable",
        "auth_required": False,
        "intervals": [],
        "notes": "Annual and quarterly cash flow.",
    },
    "fundamental.financial_ratio": {
        "supported": True,
        "status": "stable",
        "auth_required": False,
        "intervals": [],
        "notes": "Financial ratios.",
    },
}

# ---------------------------------------------------------------------------
# Limitations metadata
# ---------------------------------------------------------------------------

VCI_LIMITATIONS: dict = {
    "provider_status": "stable_public_endpoint",
    "known_limitations": [
        "intraday match_type returns str; contract expects object — known dtype drift",
    ],
    "coverage_gaps": [],
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
