"""Deterministic point-in-time ranking replay (issue #262).

Replays one fixed historical ranking specification using point-in-time evidence
already stored in the warehouse. Identical inputs reproduce identical results;
future-data contamination fails closed.
"""

from vnalpha.replay.engine import (
    ReplayContaminationError,
    ReplayResult,
    ReplaySpec,
    get_replay,
    run_replay,
)

__all__ = [
    "ReplayContaminationError",
    "ReplayResult",
    "ReplaySpec",
    "get_replay",
    "run_replay",
]
