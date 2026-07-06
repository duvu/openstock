"""
DNSE provider capability declarations and limitations metadata.

DNSE (Entrade) provides OHLCV and price board data for Vietnamese equities.
Known limitation: geographic IP restriction — may return empty data outside
Vietnam.

Data-only scope: broker, order, account, and portfolio capabilities are
outside scope and must not be added here.
"""

# ---------------------------------------------------------------------------
# Capability declarations
# ---------------------------------------------------------------------------

DNSE_CAPABILITIES: dict = {
    "equity.ohlcv": {
        "supported": True,
        "status": "stable",
        "auth_required": False,
        "intervals": ["1m", "5m", "15m", "30m", "1H", "1D", "1W", "1M"],
        "notes": "OHLCV bars via DNSE/Entrade. May require Vietnamese IP.",
    },
    "equity.quote": {
        "supported": True,
        "status": "stable",
        "auth_required": False,
        "intervals": [],
        "notes": "Price board snapshot via DNSE.",
    },
    "index.ohlcv": {
        "supported": False,
        "status": "unsupported",
        "auth_required": False,
        "intervals": [],
        "notes": "Index OHLCV not available via DNSE.",
    },
}

# ---------------------------------------------------------------------------
# Limitations metadata
# ---------------------------------------------------------------------------

DNSE_LIMITATIONS: dict = {
    "provider_status": "stable_public_endpoint",
    "known_limitations": [
        "returns empty data outside Vietnamese IP range",
        "intraday data limited to current trading session",
    ],
    "coverage_gaps": [
        "no fundamental data",
        "no company reference data",
        "no fund data",
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
