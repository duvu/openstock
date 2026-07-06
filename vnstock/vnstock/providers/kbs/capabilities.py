"""
KBS provider capability declarations and limitations metadata.

KBS (Knowledge-Base System) is the default vnstock provider for Vietnamese
market data. All core datasets are stable and publicly accessible.

Data-only scope: broker, order, account, and portfolio capabilities are
outside scope and must not be added here.
"""

# ---------------------------------------------------------------------------
# Capability declarations
# ---------------------------------------------------------------------------

KBS_CAPABILITIES: dict = {
    "equity.ohlcv": {
        "supported": True,
        "status": "stable",
        "auth_required": False,
        "intervals": ["1m", "5m", "15m", "30m", "1H", "1D", "1W", "1M"],
        "notes": "Default daily/intraday OHLCV provider for Vietnamese equities.",
    },
    "equity.quote": {
        "supported": True,
        "status": "stable",
        "auth_required": False,
        "intervals": [],
        "notes": "Real-time price board snapshot.",
    },
    "equity.intraday_trades": {
        "supported": True,
        "status": "stable",
        "auth_required": False,
        "intervals": [],
        "notes": "Intraday tick-by-tick trade records.",
    },
    "index.ohlcv": {
        "supported": True,
        "status": "stable",
        "auth_required": False,
        "intervals": ["1D", "1W", "1M"],
        "notes": "OHLCV bars for Vietnamese market indices.",
    },
    "reference.symbols": {
        "supported": True,
        "status": "stable",
        "auth_required": False,
        "intervals": [],
        "notes": "Full symbol listing.",
    },
    "reference.company_info": {
        "supported": True,
        "status": "stable",
        "auth_required": False,
        "intervals": [],
        "notes": "Company overview and profile.",
    },
    "fundamental.balance_sheet": {
        "supported": True,
        "status": "stable",
        "auth_required": False,
        "intervals": [],
        "notes": "Annual and quarterly balance sheet.",
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
        "notes": "Annual and quarterly cash flow statement.",
    },
    "fundamental.financial_ratio": {
        "supported": True,
        "status": "stable",
        "auth_required": False,
        "intervals": [],
        "notes": "Annual and quarterly financial ratios.",
    },
}

# ---------------------------------------------------------------------------
# Limitations metadata
# ---------------------------------------------------------------------------

KBS_LIMITATIONS: dict = {
    "provider_status": "stable_public_endpoint",
    "known_limitations": [
        "rate limit enforced — 20 requests/minute for guest tier",
        "requires API key for higher rate limits",
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
