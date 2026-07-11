from __future__ import annotations

from threading import RLock

from vnalpha.model_routing.models import ModelRouteDecision

_lock = RLock()
_last_route_decision: ModelRouteDecision | None = None


def set_last_route_decision(decision: ModelRouteDecision) -> None:
    global _last_route_decision
    with _lock:
        _last_route_decision = decision


def get_last_route_decision() -> ModelRouteDecision | None:
    with _lock:
        return _last_route_decision


def clear_last_route_decision() -> None:
    global _last_route_decision
    with _lock:
        _last_route_decision = None
