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

from vnalpha.assistant.errors import (
    ActionableToolExecutionError,
    RefusalError,
    ToolExecutionError,
)
from vnalpha.assistant.models import AssistantPlan, ToolPlanStep
from vnalpha.assistant.tool_policy import assert_safe_tool
from vnalpha.commands.normalizers import normalize_date
from vnalpha.core.logging import get_logger
from vnalpha.data_availability import ensure_symbol_analysis_ready
from vnalpha.data_availability.deep_readiness import ensure_deep_analysis_ready
from vnalpha.data_availability.deep_readiness_models import ContextRequirement
from vnalpha.observability.context import get_correlation_id, set_correlation_id
from vnalpha.provisioning_queue import DEFAULT_QUEUE_PATH
from vnalpha.tools.errors import ActionableToolError, ToolError
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

# The explicit provisioning tool. When a plan already contains this step, the
# executor does not run the hidden implicit data-ensure for the same symbol,
# because provisioning is now an on-trace application step (issue #163).
_PROVISION_TOOL = "data.ensure_current_symbol"

_TOOL_PERMISSIONS = TOOL_PERMISSIONS
logger = get_logger("assistant.executor")


def _build_tool_registry(conn, warehouse_path=None, queue_path=DEFAULT_QUEUE_PATH):
    return build_local_tool_registry(
        conn, warehouse_path=warehouse_path, queue_path=queue_path
    )


def _ensure_data_for_step(
    conn, step: ToolPlanStep, *, explicitly_provisioned: bool = False
) -> None:
    """Deterministically provision one-symbol analysis prerequisites.

    Full-universe watchlist and shortlist flows deliberately do not trigger an
    implicit universe refresh. They consume persisted artifacts only.

    When the plan already carries an explicit ``data.ensure_current_symbol``
    step (``explicitly_provisioned``), the implicit pre-step is skipped so
    provisioning is represented once, on-trace (issue #163).
    """
    if step.tool_name not in _ANALYSIS_TOOLS:
        return
    if explicitly_provisioned:
        return
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


def _assert_provisioning_ready(step: ToolPlanStep, result: Any) -> None:
    """Stop the plan when explicit provisioning did not reach a ready state.

    Provisioning is fail-closed: a failed or partial provisioning turn must not
    let a downstream analysis step run against incomplete or corrupt data.
    """
    data = result.get("data") if isinstance(result, dict) else None
    outcome = data.get("outcome") if isinstance(data, dict) else None
    ready_outcomes = {"READY", "REUSED", "REFRESHED"}
    if outcome in ready_outcomes:
        return
    errors = data.get("errors") if isinstance(data, dict) else None
    remediation = data.get("remediation") if isinstance(data, dict) else None
    details = []
    if isinstance(errors, list) and errors:
        details.append(str(errors[0]))
    else:
        details.append("Current-symbol data could not be provisioned.")
    if isinstance(remediation, list) and remediation:
        details.append("Remediation: " + " -> ".join(str(cmd) for cmd in remediation))
    correlation_id = data.get("correlation_id") if isinstance(data, dict) else None
    if correlation_id:
        details.append(f"correlation_id={correlation_id}")
    raise ToolExecutionError(". ".join(details))


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


def _normalize_tool_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    """Normalize typed requirement arguments before invoking a local tool."""
    normalized: dict[str, Any] = {}
    for key, value in arguments.items():
        if key.endswith("_requirement"):
            requirement = _requirement(value)
            if requirement is not ContextRequirement.NOT_REQUESTED:
                normalized[key] = requirement
            continue
        if value is not ContextRequirement.NOT_REQUESTED:
            normalized[key] = value
    return normalized


class AssistantExecutor:
    """Execute an AssistantPlan against the local tool registry."""

    def __init__(
        self,
        conn,
        assistant_session_id: str,
        on_trace_event: "Callable[[TraceEvent], None] | None" = None,
        deferred_traces: bool = False,
        prestarted_trace_ids: tuple[str, ...] = (),
        *,
        warehouse_path=None,
        queue_path=DEFAULT_QUEUE_PATH,
    ) -> None:
        self._conn = conn
        self._assistant_session_id = assistant_session_id
        self._registry = _build_tool_registry(
            conn, warehouse_path=warehouse_path, queue_path=queue_path
        )
        self._tool_executor = TracedLocalToolExecutor(
            conn,
            self._registry,
            session_id=None,
            assistant_session_id=assistant_session_id,
            trace_parent_type="assistant",
            trace_event_callback=on_trace_event,
            deferred=deferred_traces,
            prestarted_trace_ids=prestarted_trace_ids,
        )

    def flush_traces(self, conn) -> None:
        self._tool_executor.flush(conn)

    def execute(
        self,
        plan: AssistantPlan,
        *,
        explicitly_provisioned: bool | None = None,
    ) -> dict[str, Any]:
        if plan.is_refusal():
            raise RefusalError(
                reason=plan.refusal_reason or "Unsupported request",
                policy_category="UNSUPPORTED",
            )
        correlation_id = get_correlation_id()
        if not correlation_id or correlation_id == "unset":
            correlation_id = set_correlation_id()

        if explicitly_provisioned is None:
            explicitly_provisioned = any(
                step.tool_name == _PROVISION_TOOL for step in plan.steps
            )
        results: dict[str, Any] = {}
        for step_index, step in enumerate(plan.steps):
            assert_safe_tool(step.tool_name)
            _ensure_data_for_step(
                self._conn,
                step,
                explicitly_provisioned=explicitly_provisioned,
            )
            results[step.step_id] = self._execute_step(
                step, correlation_id=correlation_id
            )
            if step.tool_name == _PROVISION_TOOL:
                _assert_provisioning_ready(step, results[step.step_id])
                _apply_provisioned_date(
                    plan.steps[step_index + 1 :],
                    step,
                    results[step.step_id],
                )
        return results

    def _execute_step(
        self, step: ToolPlanStep, *, correlation_id: str | None = None
    ) -> Any:
        try:
            permission = _TOOL_PERMISSIONS[step.tool_name]
            arguments = _normalize_tool_arguments(step.arguments)
            if step.tool_name == _PROVISION_TOOL and correlation_id is not None:
                arguments["correlation_id"] = correlation_id
            output = self._tool_executor.call(
                step.tool_name,
                {permission},
                **arguments,
            )
            if dataclasses.is_dataclass(output):
                return dataclasses.asdict(output)
            return output
        except ToolExecutionError:
            raise
        except ActionableToolError as exc:
            raise ActionableToolExecutionError(exc.failure) from exc
        except ToolError as exc:
            raise ToolExecutionError(str(exc)) from exc
        except Exception as exc:
            raise ToolExecutionError(str(exc)) from exc


def _apply_provisioned_date(
    downstream_steps: list[ToolPlanStep],
    provisioning_step: ToolPlanStep,
    provisioning_result: Any,
) -> None:
    data = (
        provisioning_result.get("data")
        if isinstance(provisioning_result, dict)
        else None
    )
    resolved_date = data.get("resolved_date") if isinstance(data, dict) else None
    symbol = provisioning_step.arguments.get("symbol")
    if not isinstance(resolved_date, str) or not isinstance(symbol, str):
        return
    for step in downstream_steps:
        if step.tool_name not in _ANALYSIS_TOOLS:
            continue
        if step.arguments.get("symbol") != symbol:
            continue
        if step.arguments.get("date") in (None, "today"):
            step.arguments["date"] = resolved_date
