from __future__ import annotations

from vnalpha.tui.responsive_layout import (
    ResponsiveLayoutController,
)


def test_height_policy_has_compact_medium_and_full_suggestion_limits() -> None:
    controller = ResponsiveLayoutController()

    assert controller.suggestion_limit(20) == 4
    assert controller.suggestion_limit(24) == 6
    assert controller.suggestion_limit(30) == 10
