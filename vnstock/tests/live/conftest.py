"""
Conftest for live provider smoke tests.

Live tests are disabled by default. Enable them with:

    VNSTOCK_LIVE_TESTS=true pytest tests/live/providers -m live

Optional filtering:

    VNSTOCK_LIVE_PROVIDERS=DNSE,KBS     # comma-separated; default: all
    VNSTOCK_LIVE_SYMBOLS=FPT,VCB        # comma-separated; default: FPT,VCB,TCB

All live tests are marked with @pytest.mark.live and are automatically skipped
unless VNSTOCK_LIVE_TESTS=true is set in the environment.
"""

import os

import pytest

# ---------------------------------------------------------------------------
# Environment-driven configuration
# ---------------------------------------------------------------------------

_LIVE_TESTS_ENABLED = os.environ.get("VNSTOCK_LIVE_TESTS", "false").lower() in (
    "1",
    "true",
    "yes",
)

_LIVE_PROVIDERS_RAW = os.environ.get("VNSTOCK_LIVE_PROVIDERS", "")
LIVE_PROVIDERS: frozenset[str] = (
    frozenset(p.strip().upper() for p in _LIVE_PROVIDERS_RAW.split(",") if p.strip())
    if _LIVE_PROVIDERS_RAW
    else frozenset({"DNSE", "KBS", "VCI"})
)

_LIVE_SYMBOLS_RAW = os.environ.get("VNSTOCK_LIVE_SYMBOLS", "")
LIVE_SYMBOLS: list[str] = (
    [s.strip().upper() for s in _LIVE_SYMBOLS_RAW.split(",") if s.strip()]
    if _LIVE_SYMBOLS_RAW
    else ["FPT", "VCB", "TCB"]
)

# ---------------------------------------------------------------------------
# Session-scoped skip marker
# ---------------------------------------------------------------------------

_skip_live = pytest.mark.skipif(
    not _LIVE_TESTS_ENABLED,
    reason="Live tests disabled. Set VNSTOCK_LIVE_TESTS=true to enable.",
)


def skip_if_provider_excluded(provider: str) -> "pytest.MarkDecorator":
    """Return a skip marker if the given provider is not in LIVE_PROVIDERS."""
    return pytest.mark.skipif(
        provider.upper() not in LIVE_PROVIDERS,
        reason=f"Provider {provider} excluded by VNSTOCK_LIVE_PROVIDERS filter.",
    )


# ---------------------------------------------------------------------------
# Auto-apply live skip to every test in this subtree
# ---------------------------------------------------------------------------


def pytest_collection_modifyitems(items: list) -> None:
    """Auto-apply _skip_live to all tests under tests/live/."""
    for item in items:
        if "tests/live" in str(item.fspath):
            item.add_marker(_skip_live)
