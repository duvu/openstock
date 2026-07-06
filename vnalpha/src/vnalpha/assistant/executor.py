"""
AssistantExecutor: runs ToolPlanStep list through the Phase 5.8 local tool registry.

Rules:
- Only tools in ASSISTANT_TOOL_ALLOWLIST may be called.
- Every call is persisted in tool_trace (linked to assistant_session_id).
- Network, Python exec, MCP, raw SQL, filesystem, broker/order/allocation are forbidden.
"""
from __future__ import annotations

from typing import Any

from vnalpha.assistant.errors import RefusalError, ToolExecutionError
from vnalpha.assistant.models import AssistantPlan, ToolPlanStep
from vnalpha.tools.models import ToolPermission, ToolSpec
from vnalpha.tools.registry import LocalToolRegistry
from vnalpha.warehouse.session_repo import create_tool_trace, finish_tool_trace

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

# Map tool_name -> ToolPermission for allowed tools
_TOOL_PERMISSIONS: dict[str, ToolPermission] = {
    "watchlist.scan": ToolPermission.READ_WATCHLIST,
    "watchlist.filter": ToolPermission.READ_WATCHLIST,
    "candidate.explain": ToolPermission.READ_SCORE,
    "candidate.compare": ToolPermission.READ_SCORE,
    "quality.get_status": ToolPermission.READ_QUALITY,
    "lineage.get_symbol_lineage": ToolPermission.READ_LINEAGE,
    "note.create": ToolPermission.WRITE_NOTE,
    "history.list_sessions": ToolPermission.READ_HISTORY,
}


def _build_tool_registry(conn) -> LocalToolRegistry:
    """Build a LocalToolRegistry wired to the live DuckDB connection."""
    from vnalpha.tools.lineage import get_symbol_lineage
    from vnalpha.tools.notes import create_note, list_sessions
    from vnalpha.tools.quality import get_quality_status
    from vnalpha.tools.scoring import compare_candidates, explain_candidate
    from vnalpha.tools.watchlist import filter_watchlist, scan_watchlist

    registry = LocalToolRegistry()

    # --- watchlist.scan ---
    spec_scan = ToolSpec(
        name="watchlist.scan",
        description="Scan watchlist candidates for a date",
        permission=ToolPermission.READ_WATCHLIST,
    )

    def _scan(**kwargs):
        date = kwargs.get("date")
        min_score = kwargs.get("min_score", 0.0)
        if date is None:
            raise ToolExecutionError("watchlist.scan requires 'date' argument.")
        return scan_watchlist(conn, date=date, min_score=min_score)

    registry.register(spec_scan, _scan)

    # --- watchlist.filter ---
    spec_filter = ToolSpec(
        name="watchlist.filter",
        description="Filter watchlist candidates by conditions",
        permission=ToolPermission.READ_WATCHLIST,
    )

    def _filter(**kwargs):
        date = kwargs.get("date")
        filters = kwargs.get("filters", [])
        if date is None:
            raise ToolExecutionError("watchlist.filter requires 'date' argument.")
        return filter_watchlist(conn, date=date, filters=filters)

    registry.register(spec_filter, _filter)

    # --- candidate.explain ---
    spec_explain = ToolSpec(
        name="candidate.explain",
        description="Explain a candidate's score for a date",
        permission=ToolPermission.READ_SCORE,
    )

    def _explain(**kwargs):
        symbol = kwargs.get("symbol")
        date = kwargs.get("date")
        if symbol is None or date is None:
            raise ToolExecutionError("candidate.explain requires 'symbol' and 'date'.")
        return explain_candidate(conn, symbol=symbol, date=date)

    registry.register(spec_explain, _explain)

    # --- candidate.compare ---
    spec_compare = ToolSpec(
        name="candidate.compare",
        description="Compare multiple candidates on a date",
        permission=ToolPermission.READ_SCORE,
    )

    def _compare(**kwargs):
        symbols = kwargs.get("symbols")
        date = kwargs.get("date")
        if symbols is None or date is None:
            raise ToolExecutionError("candidate.compare requires 'symbols' and 'date'.")
        return compare_candidates(conn, symbols=symbols, date=date)

    registry.register(spec_compare, _compare)

    # --- quality.get_status ---
    spec_quality = ToolSpec(
        name="quality.get_status",
        description="Get data quality status for a symbol or watchlist",
        permission=ToolPermission.READ_QUALITY,
    )

    def _quality(**kwargs):
        return get_quality_status(
            conn,
            symbol=kwargs.get("symbol"),
            date=kwargs.get("date"),
        )

    registry.register(spec_quality, _quality)

    # --- lineage.get_symbol_lineage ---
    spec_lineage = ToolSpec(
        name="lineage.get_symbol_lineage",
        description="Get data lineage for a symbol on a date",
        permission=ToolPermission.READ_LINEAGE,
    )

    def _lineage(**kwargs):
        symbol = kwargs.get("symbol")
        date = kwargs.get("date")
        if symbol is None or date is None:
            raise ToolExecutionError("lineage.get_symbol_lineage requires 'symbol' and 'date'.")
        return get_symbol_lineage(conn, symbol=symbol, date=date)

    registry.register(spec_lineage, _lineage)

    # --- note.create ---
    spec_note = ToolSpec(
        name="note.create",
        description="Create a research note linked to a symbol",
        permission=ToolPermission.WRITE_NOTE,
    )

    def _create_note(**kwargs):
        symbol = kwargs.get("symbol")
        note_text = kwargs.get("note_text")
        tags = kwargs.get("tags")
        session_id = kwargs.get("session_id")
        if symbol is None or note_text is None:
            raise ToolExecutionError("note.create requires 'symbol' and 'note_text'.")
        return create_note(conn, symbol=symbol, note_text=note_text, session_id=session_id, tags=tags)

    registry.register(spec_note, _create_note)

    # --- history.list_sessions ---
    spec_history = ToolSpec(
        name="history.list_sessions",
        description="List recent research sessions",
        permission=ToolPermission.READ_HISTORY,
    )

    def _list_sessions(**kwargs):
        limit = kwargs.get("limit", 20)
        return list_sessions(conn, limit=limit)

    registry.register(spec_history, _list_sessions)

    return registry


class AssistantExecutor:
    """Executes an AssistantPlan against the local tool registry."""

    def __init__(self, conn, assistant_session_id: str) -> None:
        self._conn = conn
        self._assistant_session_id = assistant_session_id
        self._registry = _build_tool_registry(conn)

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
        trace_id = create_tool_trace(
            self._conn,
            session_id=self._assistant_session_id,
            tool_name=step.tool_name,
            input_data=step.arguments,
        )
        try:
            permission = _TOOL_PERMISSIONS[step.tool_name]
            granted = {permission}
            output = self._registry.call(step.tool_name, granted, **step.arguments)
            finish_tool_trace(
                self._conn,
                trace_id,
                status="SUCCESS",
                output_summary={"result": str(output)[:200]},
            )
            # Return as dict for synthesizer
            if hasattr(output, "__dict__"):
                import dataclasses

                if dataclasses.is_dataclass(output):
                    return dataclasses.asdict(output)
            return output
        except ToolExecutionError as exc:
            finish_tool_trace(
                self._conn,
                trace_id,
                status="FAILED",
                error={"message": str(exc)},
            )
            raise
        except Exception as exc:
            finish_tool_trace(
                self._conn,
                trace_id,
                status="FAILED",
                error={"message": str(exc)},
            )
            raise ToolExecutionError(f"Step '{step.tool_name}' failed: {exc}") from exc
