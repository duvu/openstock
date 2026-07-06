"""Smoke tests for the TUI — ensure screens mount without errors."""
import sys
import pytest

textual_available = True
try:
    import textual  # noqa: F401
except ImportError:
    textual_available = False

skip_if_no_textual = pytest.mark.skipif(
    not textual_available, reason="textual not installed"
)


@skip_if_no_textual
@pytest.mark.asyncio
async def test_app_can_be_created():
    """VnAlphaApp can be instantiated without errors."""
    from vnalpha.tui.app import VnAlphaApp
    app = VnAlphaApp()
    assert app is not None
    assert app.TITLE == "vnalpha | Research Discovery"


@skip_if_no_textual
def test_watchlist_screen_exists():
    """WatchlistScreen is importable."""
    from vnalpha.tui.screens.watchlist import WatchlistScreen
    assert WatchlistScreen.TITLE == "Daily Watchlist"


@skip_if_no_textual
def test_detail_screen_exists():
    """DetailScreen is importable."""
    from vnalpha.tui.screens.detail import DetailScreen
    s = DetailScreen(symbol="FPT")
    assert s._symbol == "FPT"


@skip_if_no_textual
def test_rejected_screen_exists():
    from vnalpha.tui.screens.rejected import RejectedScreen
    assert RejectedScreen.TITLE == "Rejected Symbols"


@skip_if_no_textual
def test_quality_screen_exists():
    from vnalpha.tui.screens.quality import QualityScreen
    assert QualityScreen.TITLE == "Data Quality"


@skip_if_no_textual
def test_score_table_widget_exists():
    from vnalpha.tui.widgets.score_table import ScoreTable


@skip_if_no_textual
def test_risk_panel_widget_exists():
    from vnalpha.tui.widgets.risk_panel import RiskPanel


@skip_if_no_textual
def test_no_buy_sell_language_in_tui():
    import inspect
    import vnalpha.tui.app as app_mod
    import vnalpha.tui.screens.watchlist as wl_mod
    import vnalpha.tui.screens.detail as detail_mod
    import vnalpha.tui.screens.home as home_mod

    forbidden = ["buy", "sell", "order", "portfolio", "recommend"]
    for mod in [app_mod, wl_mod, detail_mod, home_mod]:
        src = inspect.getsource(mod).lower()
        for word in forbidden:
            assert word not in src, f"Forbidden word '{word}' found in {mod.__name__}"


def test_tui_source_files_have_no_forbidden_terms():
    """Check TUI source files for forbidden terms without importing (no textual dep)."""
    import os
    import re

    tui_dir = os.path.join(
        os.path.dirname(__file__), "..", "src", "vnalpha", "tui"
    )
    forbidden = ["buy signal", "sell signal", "buy order", "sell order",
                 "place order", "execute order", "portfolio", "investment advice"]

    for root, dirs, files in os.walk(tui_dir):
        for fname in files:
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(root, fname)
            with open(fpath) as f:
                src = f.read().lower()
            for term in forbidden:
                assert term not in src, f"Forbidden term '{term}' in {fpath}"


def test_tui_source_has_research_language():
    """Watchlist source file contains 'research' language."""
    import os
    wl_path = os.path.join(
        os.path.dirname(__file__), "..", "src", "vnalpha", "tui", "screens", "watchlist.py"
    )
    with open(wl_path) as f:
        src = f.read()
    assert "Research Candidates" in src or "research candidate" in src.lower()
