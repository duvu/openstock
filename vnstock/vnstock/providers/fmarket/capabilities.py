"""
FMarket provider capability declarations and limitations metadata.

FMarket is the primary provider for Vietnamese open-end fund data (NAV,
holdings, etc.).

Data-only scope: broker, order, account, and portfolio capabilities are
outside scope and must not be added here.
"""

# ---------------------------------------------------------------------------
# Capability declarations
# ---------------------------------------------------------------------------

FMARKET_CAPABILITIES: dict = {
    "fund.nav": {
        "supported": True,
        "status": "stable",
        "auth_required": False,
        "intervals": ["1D"],
        "notes": "NAV report and holdings for Vietnamese open-end funds.",
    },
    "reference.symbols": {
        "supported": True,
        "status": "stable",
        "auth_required": False,
        "intervals": [],
        "notes": "Fund listing and search via FMarket.",
    },
}

# ---------------------------------------------------------------------------
# Limitations metadata
# ---------------------------------------------------------------------------

FMARKET_LIMITATIONS: dict = {
    "provider_status": "stable_public_endpoint",
    "known_limitations": [
        "fund-only provider; no equity OHLCV or company data",
    ],
    "coverage_gaps": [
        "no equity data",
        "no fundamental data",
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
