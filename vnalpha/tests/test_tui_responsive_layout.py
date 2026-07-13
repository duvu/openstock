from __future__ import annotations

from vnalpha.tui.responsive_layout import (
    ResponsiveLayoutController,
    ResponsiveLayoutPolicy,
)


def test_height_policy_has_compact_medium_and_full_suggestion_limits() -> None:
    controller = ResponsiveLayoutController()

    assert controller.suggestion_limit(20) == 4
    assert controller.suggestion_limit(24) == 6
    assert controller.suggestion_limit(30) == 10


def test_height_policy_hides_footer_only_below_its_supported_minimum() -> None:
    controller = ResponsiveLayoutController(
        ResponsiveLayoutPolicy(footer_hidden_below_height=20)
    )

    assert controller.should_show_footer(19) is False
    assert controller.should_show_footer(20) is True
