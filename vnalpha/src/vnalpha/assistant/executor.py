"""
AssistantExecutor: runs ToolPlanStep list through the Phase 5.8 local tool registry.

Rules:
- Only tools in ASSISTANT_TOOL_ALLOWLIST may be called.
- Every call is persisted in tool_trace (linked to assistant_session_id).
- Network, Python exec, MCP, raw SQL, filesystem, broker/order/allocation are forbidden.
"""
from __future__ import annotations

import dataclasses
from typing import Any

from vnalpha.assistant.errors import RefusalError, ToolExecutionError
from vnalpha.assistant.models import AssistantPlan, ToolPlanStep
from vnalpha.tools.errors import ToolError
from vnalpha.tools.executor import TracedLocalToolExecutor
from vnalpha.tools.setup import TOOL_PERMISSIONS, build_local_tool_registry

ASSISTANT_TOOL_ALLOWLIST: frozenset[str] = frozenset(
    {
        "watchlist.scan",
        "watchlist.filter",
        "candidate.compare",
        "candidate.explain",
        "quality.get_status",
        "lineage.get_symbol_lineage",
        "note.create",
        "history.list_sessions",
    }
)

# Backward-compatible module name used by tests/source checks.
_TOOL_PERMISSIONS = TOOL_PERMISSIONS


def _build_tool_registry(conn):
    """Build a LocalToolRegistry wired to the live DuckDB connection."""
    return build_local_tool_registry(conn)


class AssistantExecutor:
    """Executes an AssistantPlan against the local tool registry."""

    def __init__(self, conn, assistant_session_id: str) -> None:
        self._conn = conn
        self._assistant_session_id = assistant_session_id
        self._registry = _build_tool_registry(conn)
        self._tool_executor = TracedLocalToolExecutor(
            conn,
            self._registry,
            session_id=assistant_session_id,
            assistant_session_id=assistant_session_id,
            trace_parent_type="assistant",
        )

    def execute(self, plan: AssistantPlan) -> dict[str, Any]:
        """Execute all steps in the plan. Returns dict of step_id -> tool output dict."""
        if plan.is_refusal():
            raise RefusalError(
                reason=plan.refusal_reason or "Unsupported request",
                policy_category="UNSUPPORTED",
            )
        results: dict[str, Any] = {}
        for step in plan.steps:
            self._check_allowlist(step)
            output = self._execute_step(step)
            results[step.step_id] = output
        return results

    def _check_allowlist(self, step: ToolPlanStep) -> None:
        if step.tool_name not in ASSISTANT_TOOL_ALLOWLIST:
            raise ToolExecutionError(
                f"Tool '{step.tool_name}' is not in the assistant tool allowlist."
            )

    def _execute_step(self, step: ToolPlanStep) -> Any:
        try:
            permission = _TOOL_PERMISSIONS[step.tool_name]
            output = self._tool_executor.call(step.tool_name, {permission}, **step.arguments)
            # Return as dict for synthesizer
            if dataclasses.is_dataclass(output):
                return dataclasses.asdict(output)
            return output
        except ToolExecutionError:
            raise
        except ToolError as exc:
            raise ToolExecutionError(str(exc)) from exc
        except Exception as exc:
            raise ToolExecutionError(f"Step '{step.tool_name}' failed: {exc}") from exc
