from __future__ import annotations

from vnalpha.closed_loop.models import LifecycleState


def test_lifecycle_has_canonical_closed_loop_states() -> None:
    states = {state.value for state in LifecycleState}

    assert states == {
        "RUN",
        "OBSERVE",
        "PACKAGE",
        "AI_FIX",
        "VALIDATE",
        "PROMOTE_READY",
        "PROMOTED",
        "REJECTED",
        "ROLLED_BACK",
        "FAILED",
    }
