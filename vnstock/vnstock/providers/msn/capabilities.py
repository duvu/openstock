"""
MSN (Microsoft Network) provider capability declarations and limitations.

MSN provides OHLCV data for Vietnamese and global equities via a public
reverse-engineered endpoint. Symbol resolution is required before querying.

Data-only scope: broker, order, account, and portfolio capabilities are
outside scope and must not be added here.
"""

# ---------------------------------------------------------------------------
# Capability declarations
# ---------------------------------------------------------------------------

MSN_CAPABILITIES: dict = {
    "equity.ohlcv": {
        "supported": True,
        "status": "experimental",
        "auth_required": False,
        "intervals": ["1D", "1W", "1M"],
        "notes": (
            "Unofficial MSN endpoint. Requires resolving symbol_id via "
            "Listing.search_symbol() before calling history(). "
            "Schema drift risk."
        ),
    },
}

# ---------------------------------------------------------------------------
# Limitations metadata
# ---------------------------------------------------------------------------

MSN_LIMITATIONS: dict = {
    "provider_status": "unofficial_public_endpoint",
    "known_limitations": [
        "requires symbol_id lookup before OHLCV fetch",
        "unofficial endpoint — may change without notice",
        "limited to daily/weekly/monthly resolution",
    ],
    "coverage_gaps": [
        "no price board data",
        "no fundamental data",
        "no company reference data",
        "no fund data",
        "no intraday data",
    ],
    "schema_drift_risk": "medium",
    "excluded_capabilities": [
        "broker.login",
        "broker.order",
        "broker.account",
        "portfolio.management",
        "trading.signals",
        "trading.recommendations",
    ],
}
