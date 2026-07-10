from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ModelProfile(str, Enum):
    SMALL = "small"
    DEFAULT = "default"
    REASONING = "reasoning"
    LONG_CONTEXT = "long_context"


@dataclass(frozen=True, slots=True)
class ModelRouteDecision:
    profile: ModelProfile
    model_id: str
    stage: str
    task_type: str | None
    route_reason: str
