"""Smoke tests for the TUI — ensure screens mount without errors."""

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
