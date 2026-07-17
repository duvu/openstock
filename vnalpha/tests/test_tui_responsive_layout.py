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


def test_debug_drawer_height_is_bounded_across_supported_viewports() -> None:
    controller = ResponsiveLayoutController()

    assert controller.debug_drawer_height(20) == 6
    assert controller.debug_drawer_height(24) == 7
    assert controller.debug_drawer_height(30) == 9
    assert controller.debug_drawer_height(50) == 14
