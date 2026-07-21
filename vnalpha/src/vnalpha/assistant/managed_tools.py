from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from vnalpha.assistant.models import PreparedAssistantTurn, ToolPlanStep
    from vnalpha.tools.executor import TraceEvent

from vnalpha.assistant.executor import AssistantExecutor
from vnalpha.assistant.managed_context import ManagedAssistantContext
from vnalpha.assistant.managed_failures import finish_execution_failure
from vnalpha.tools.setup import TOOL_PERMISSIONS


def _is_write_step(step: ToolPlanStep) -> bool:
    return TOOL_PERMISSIONS[step.tool_name].value.startswith("WRITE_")


class ManagedAssistantToolExecution(ManagedAssistantContext):
    def _execute_managed_tools(
        self,
        prepared: PreparedAssistantTurn,
        trace_ids: tuple[str, ...],
        *,
        on_trace_event: Callable[[TraceEvent], None] | None,
    ) -> dict[str, Any]:
        from vnalpha.warehouse.connection import read_connection

        results: dict[str, Any] = {}
        events: list[TraceEvent] = []
        explicitly_provisioned = any(
            step.tool_name == "data.ensure_current_symbol"
            for step in prepared.plan.steps
        )
        for index, (step, trace_id) in enumerate(
            zip(prepared.plan.steps, trace_ids, strict=True)
        ):
            step_plan = replace(prepared.plan, steps=[step])
            executor: AssistantExecutor | None = None
            try:
                if _is_write_step(step):
                    with self._coordinator.transaction() as connection:
                        executor = AssistantExecutor(
                            connection,
                            assistant_session_id=prepared.assistant_session_id,
                            on_trace_event=events.append,
                            deferred_traces=True,
                            prestarted_trace_ids=(trace_id,),
                        )
                        results.update(
                            executor.execute(
                                step_plan,
                                explicitly_provisioned=explicitly_provisioned,
                            )
                        )
                        executor.flush_traces(connection)
                else:
                    with read_connection(path=self._warehouse_path) as connection:
                        executor = AssistantExecutor(
                            connection,
                            assistant_session_id=prepared.assistant_session_id,
                            on_trace_event=events.append,
                            deferred_traces=True,
                            prestarted_trace_ids=(trace_id,),
                        )
                        results.update(
                            executor.execute(
                                step_plan,
                                explicitly_provisioned=explicitly_provisioned,
                            )
                        )
                    with self._coordinator.transaction() as connection:
                        executor.flush_traces(connection)
            except Exception as exc:  # noqa: BROAD_EXCEPT_OK
                with self._coordinator.transaction() as connection:
                    if executor is not None:
                        executor.flush_traces(connection)
                    finish_execution_failure(
                        connection,
                        prepared,
                        exc,
                        trace_ids=trace_ids[index + 1 :],
                    )
                self._replay_trace_events(events, on_trace_event)
                raise
        self._replay_trace_events(events, on_trace_event)
        return results

    @staticmethod
    def _replay_trace_events(
        events: list[TraceEvent],
        callback: Callable[[TraceEvent], None] | None,
    ) -> None:
        if callback is not None:
            for event in events:
                callback(event)
