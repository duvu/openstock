"""
TCBS provider capability declarations and limitations metadata.

TCBS is an unofficial/experimental provider. All API endpoints now require
Bearer token authentication via the TCBS OIDC login flow with mandatory OTP.

Data-only scope: broker, order, account, and portfolio capabilities are
outside scope and must not be added here.  The vnstock-tcbs-login CLI script
is a legacy auth helper and is deferred for redesign in a later auth phase.
"""

# ---------------------------------------------------------------------------
# Capability declarations
# ---------------------------------------------------------------------------

TCBS_CAPABILITIES: dict = {
    "equity.ohlcv": {
        "supported": True,
        "status": "experimental",
        "auth_required": True,
        "intervals": ["1m", "5m", "15m", "30m", "1H", "1D", "1W", "1M"],
        "notes": (
            "Unofficial endpoint; requires Bearer token. "
            "Not default provider. Schema drift risk."
        ),
    },
    "equity.quote": {
        "supported": True,
        "status": "experimental",
        "auth_required": True,
        "intervals": [],
        "notes": "Price board snapshot. Requires auth.",
    },
    "equity.intraday_trades": {
        "supported": True,
        "status": "experimental",
        "auth_required": True,
        "intervals": [],
        "notes": "Experimental intraday endpoint. Requires auth.",
    },
    "reference.company_info": {
        "supported": True,
        "status": "partial",
        "auth_required": True,
        "intervals": [],
        "notes": "Company overview via TCBS. Requires auth.",
    },
    "fundamental.balance_sheet": {
        "supported": True,
        "status": "partial",
        "auth_required": True,
        "intervals": [],
        "notes": "Balance sheet. Contract validation to be expanded. Requires auth.",
    },
    "fundamental.income_statement": {
        "supported": True,
        "status": "partial",
        "auth_required": True,
        "intervals": [],
        "notes": "Income statement. Requires auth.",
    },
    "fundamental.cash_flow": {
        "supported": True,
        "status": "partial",
        "auth_required": True,
        "intervals": [],
        "notes": "Cash flow. Requires auth.",
    },
    "fundamental.financial_ratio": {
        "supported": True,
        "status": "partial",
        "auth_required": True,
        "intervals": [],
        "notes": "Financial ratios. Requires auth.",
    },
}

# ---------------------------------------------------------------------------
# Limitations metadata
# ---------------------------------------------------------------------------

TCBS_LIMITATIONS: dict = {
    "provider_status": "unofficial_authenticated_endpoint",
    "known_limitations": [
        "all endpoints require Bearer token (OIDC + OTP mandatory)",
        "not default provider",
        "schema drift risk — unofficial endpoints may change",
        "fundamental contracts not fully validated yet",
    ],
    "coverage_gaps": [
        "no fund data",
        "index OHLCV not available",
    ],
    "schema_drift_risk": "high",
    "excluded_capabilities": [
        "broker.login",
        "broker.order",
        "broker.account",
        "portfolio.management",
        "iCopy.subscription",
        "margin.management",
        "trading.signals",
        "trading.recommendations",
    ],
}
