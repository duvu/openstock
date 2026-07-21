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
def test_no_buy_sell_language_in_tui():
    import inspect

    import vnalpha.tui.app as app_mod
    import vnalpha.tui.screens.detail as detail_mod
    import vnalpha.tui.screens.home as home_mod
    import vnalpha.tui.screens.watchlist as wl_mod

    forbidden = ["buy", "sell", "order", "portfolio", "recommend"]
    for mod in [app_mod, wl_mod, detail_mod, home_mod]:
        src = inspect.getsource(mod).lower()
        for word in forbidden:
            assert word not in src, f"Forbidden word '{word}' found in {mod.__name__}"


def test_tui_source_files_have_no_forbidden_terms():
    """Check TUI source files for forbidden terms without importing (no textual dep)."""
    import os

    tui_dir = os.path.join(os.path.dirname(__file__), "..", "src", "vnalpha", "tui")
    forbidden = [
        "buy signal",
        "sell signal",
        "buy order",
        "sell order",
        "place order",
        "execute order",
        "portfolio",
        "investment advice",
    ]

    for root, _dirs, files in os.walk(tui_dir):
        # Skip __pycache__
        _dirs[:] = [d for d in _dirs if d != "__pycache__"]
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
        os.path.dirname(__file__),
        "..",
        "src",
        "vnalpha",
        "tui",
        "screens",
        "watchlist.py",
    )
    with open(wl_path) as f:
        src = f.read()
    assert "Research Candidates" in src or "research candidate" in src.lower()


def test_experiment_catalog_advertises_the_enabled_event_study_path():
    from vnalpha.tui.command_catalog import find_command

    experiment = find_command("experiment")

    assert experiment is not None
    assert "event-study" in experiment.usage
    assert "dataset-extension" in experiment.usage
    assert "backtest" not in experiment.usage
    assert any("event-study" in example for example in experiment.examples)
    assert any("dataset-extension" in example for example in experiment.examples)


def test_catalog_command_suggestions_are_alphabetical():
    from vnalpha.tui.command_catalog import command_names, commands_for_prefix

    names = command_names()

    assert names == sorted(names)
    assert [command.name for command in commands_for_prefix("")] == sorted(
        command.name for command in commands_for_prefix("")
    )


@skip_if_no_textual
def test_composer_input_css_allows_suggestion_expansion():
    from vnalpha.tui.app import VnAlphaApp

    css = VnAlphaApp.CSS
    assert "ComposerInput {" in css
    assert "height: auto;" in css
    assert "max-height: 16;" in css


@skip_if_no_textual
@pytest.mark.asyncio
async def test_composer_input_focused_at_launch_shows_slash_suggestions():
    """Typing '/' must reveal the command list when the composer input is focused.

    Regression guard: if focus lands on the (previously focusable) output log
    instead of the composer Input, printable keystrokes never reach the Input,
    on_input_changed never fires, and the suggestion list is never shown.
    """
    from textual.widgets import Input, Static

    from vnalpha.tui.app import VnAlphaApp

    app = VnAlphaApp()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        inp = app.query_one("#composer-input-field", Input)
        # The composer Input must own focus at launch (AUTO_FOCUS).
        assert inp.has_focus is True

        await pilot.press("/")
        await pilot.pause()
        panel = app.query_one("#composer-suggestions", Static)
        assert panel.display is True
        assert "/analyze" in str(panel.render())

        await pilot.press("h")
        await pilot.pause()
        assert str(panel.render()).splitlines() == ["/help", "/history", "/hypothesis"]

        inp.value = "/co"
        await pilot.pause()
        assert "/copy" in str(panel.render()).splitlines()


@skip_if_no_textual
@pytest.mark.asyncio
async def test_composer_suggestion_list_not_clipped():
    """All matched suggestions must be visible, not clipped by the composer height."""
    from textual.widgets import Static

    from vnalpha.tui.app import VnAlphaApp

    app = VnAlphaApp()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        panel = app.query_one("#composer-suggestions", Static)
        # The suggestion panel must be tall enough to show the matched commands
        # (up to _max_suggestions = 10) without being clipped by its own CSS.
        from vnalpha.tui.widgets.composer_input import ComposerInput

        assert "max-height: 12;" in ComposerInput.DEFAULT_CSS
        assert panel.display is True


@skip_if_no_textual
def test_composer_input_shows_and_filters_command_suggestions():
    from vnalpha.tui.widgets.composer_input import ComposerInput

    class _FakePanel:
        def __init__(self) -> None:
            self.display = True
            self.text = ""

        def update(self, value: str) -> None:
            self.text = value

    panel = _FakePanel()
    composer = ComposerInput()
    composer._command_names = ["scan", "sandbox", "help", "status", "history"]
    composer.query_one = lambda selector, _type=None: panel

    composer._render_suggestions("/")
    assert panel.display is True
    assert panel.text == "/scan\n/sandbox\n/help\n/status\n/history"

    composer._render_suggestions("/sc")
    assert panel.display is True
    assert panel.text == "/scan"

    composer._render_suggestions("/help now")
    assert panel.display is True
    assert panel.text == "/help"

    composer._render_suggestions("random text")
    assert panel.display is False


@skip_if_no_textual
def test_composer_input_submission_still_works_when_suggestions_enabled():
    from types import SimpleNamespace
    from unittest.mock import Mock

    from vnalpha.tui.widgets.composer_input import ComposerInput

    class _FakePanel:
        def __init__(self) -> None:
            self.display = True
            self.text = ""

        def update(self, value: str) -> None:
            self.text = value

    panel = _FakePanel()
    composer = ComposerInput()
    composer._command_names = ["scan", "help"]
    composer.query_one = lambda selector, _type=None: panel

    messages: list[object] = []

    def _capture(message: object) -> None:
        messages.append(message)

    composer.post_message = _capture

    composer._render_suggestions("/s")
    assert panel.display is True

    event = SimpleNamespace(
        value=" /scan now ",
        input=Mock(),
        stop=lambda: None,
    )
    composer.on_input_submitted(event)

    assert len(messages) == 1
    assert isinstance(messages[0], ComposerInput.ComposerSubmitted)
    assert messages[0].text == "/scan now"
    assert panel.display is False


@skip_if_no_textual
def test_composer_input_uses_ui_catalog_for_root_suggestions():
    from vnalpha.tui.widgets.composer_input import ComposerInput

    class _FakePanel:
        def __init__(self) -> None:
            self.display = True
            self.text = ""

        def update(self, value: str) -> None:
            self.text = value

    panel = _FakePanel()
    composer = ComposerInput()

    assert "copy" in composer._command_names
    assert composer._command_names == sorted(composer._command_names)

    composer.query_one = lambda selector, _type=None: panel
    composer._render_suggestions("/")
    assert panel.display is True
    assert panel.text.splitlines() == [
        f"/{name}" for name in composer._root_command_suggestions()
    ]
