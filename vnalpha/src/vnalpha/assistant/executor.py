"""
AssistantExecutor runs deterministic ToolPlanStep lists through the canonical
policy-governed local tool registry.

Only explicitly approved tools may be called. Every call is persisted in
``tool_trace`` and no assistant tool receives raw SQL, filesystem, broker,
account, allocation, or unrestricted code-execution capability.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from vnalpha.tools.executor import TraceEvent

from vnalpha.assistant.errors import RefusalError, ToolExecutionError
from vnalpha.assistant.models import AssistantPlan, ToolPlanStep
from vnalpha.assistant.tool_policy import assert_safe_tool
from vnalpha.core.logging import get_logger
from vnalpha.data_availability.deep_readiness import ensure_deep_analysis_ready
from vnalpha.data_availability.deep_readiness_models import ContextRequirement
from vnalpha.tools.errors import ToolError
from vnalpha.tools.executor import TracedLocalToolExecutor
from vnalpha.tools.setup import TOOL_PERMISSIONS, build_local_tool_registry

_ANALYSIS_TOOLS: frozenset[str] = frozenset(
    {
        "candidate.explain",
        "candidate.compare",
        "analysis.deep_symbol",
        "scenario.generate_research_plan",
    }
)

_FAIL_CLOSED_ANALYSIS_TOOLS: frozenset[str] = frozenset(
    {"analysis.deep_symbol", "scenario.generate_research_plan"}
)

_TOOL_PERMISSIONS = TOOL_PERMISSIONS
logger = get_logger("assistant.executor")


def _build_tool_registry(conn):
    return build_local_tool_registry(conn)


def _ensure_data_for_step(conn, step: ToolPlanStep) -> None:
    """Deterministically provision one-symbol analysis prerequisites.

    Full-universe watchlist and shortlist flows deliberately do not trigger an
    implicit universe refresh. They consume persisted artifacts only.
    """
    if step.tool_name not in _ANALYSIS_TOOLS:
        return
    from vnalpha.commands.normalizers import normalize_date
    from vnalpha.data_availability import ensure_symbol_analysis_ready

    args = step.arguments
    symbols: list[str] = []
    if isinstance(args.get("symbol"), str) and args["symbol"].strip():
        symbols = [args["symbol"]]
    elif "symbols" in args:
        raw = args["symbols"]
        if isinstance(raw, (list, tuple)):
            symbols = [item for item in raw if isinstance(item, str) and item.strip()]
        elif isinstance(raw, str) and raw.strip():
            symbols = [raw]
    if not symbols:
        return
    date = normalize_date(args.get("date"))
    for symbol in symbols:
        if step.tool_name in _FAIL_CLOSED_ANALYSIS_TOOLS:
            readiness = ensure_deep_analysis_ready(
                conn,
                symbol,
                date,
                market_regime_requirement=_requirement(
                    args.get("market_regime_requirement")
                ),
                sector_strength_requirement=_requirement(
                    args.get("sector_strength_requirement")
                ),
            )
            if not readiness.is_ready:
                raise ToolExecutionError(_readiness_error_message(readiness))
        else:
            try:
                ensure_symbol_analysis_ready(conn, symbol, date)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Pre-execution data ensure failed for %s: %s", symbol, exc
                )


def _readiness_error_message(readiness) -> str:
    failed_artifact = next(
        (artifact for artifact in readiness.artifacts if artifact.error), None
    )
    remediation_steps = failed_artifact.remediation_steps if failed_artifact else ()
    remediation = failed_artifact.remediation if failed_artifact else None
    details = [readiness.failure_summary()]
    if remediation_steps:
        details.append(
            "Remediation: " + " -> ".join(step.command for step in remediation_steps)
        )
    elif remediation:
        details.append(f"Remediation: {remediation}")
    details.append(f"correlation_id={readiness.correlation_id}")
    return ". ".join(details)


def _requirement(value) -> ContextRequirement:
    if isinstance(value, ContextRequirement):
        return value
    if isinstance(value, str):
        normalized = value.strip().upper()
        return next(
            (
                requirement
                for requirement in ContextRequirement
                if requirement.value == normalized
            ),
            ContextRequirement.INVALID,
        )
    return ContextRequirement.NOT_REQUESTED


class AssistantExecutor:
    """Execute an AssistantPlan against the local tool registry."""

    def __init__(
        self,
        conn,
        assistant_session_id: str,
        on_trace_event: "Callable[[TraceEvent], None] | None" = None,
    ) -> None:
        self._conn = conn
        self._assistant_session_id = assistant_session_id
        self._registry = _build_tool_registry(conn)
        self._tool_executor = TracedLocalToolExecutor(
            conn,
            self._registry,
            session_id=None,
            assistant_session_id=assistant_session_id,
            trace_parent_type="assistant",
            trace_event_callback=on_trace_event,
        )

    def execute(self, plan: AssistantPlan) -> dict[str, Any]:
        if plan.is_refusal():
            raise RefusalError(
                reason=plan.refusal_reason or "Unsupported request",
                policy_category="UNSUPPORTED",
            )
        results: dict[str, Any] = {}
        for step in plan.steps:
            assert_safe_tool(step.tool_name)
            _ensure_data_for_step(self._conn, step)
            results[step.step_id] = self._execute_step(step)
        return results

    def _execute_step(self, step: ToolPlanStep) -> Any:
        try:
            permission = _TOOL_PERMISSIONS[step.tool_name]
            arguments = {
                key: value
                for key, value in step.arguments.items()
                if value is not ContextRequirement.NOT_REQUESTED
            }
            output = self._tool_executor.call(
                step.tool_name, {permission}, **arguments
            )
            if dataclasses.is_dataclass(output):
                return dataclasses.asdict(output)
            return output
        except ToolExecutionError:
            raise
        except ToolError as exc:
            raise ToolExecutionError(str(exc)) from exc
        except Exception as exc:
            raise ToolExecutionError(f"Step '{step.tool_name}' failed: {exc}") from exc
