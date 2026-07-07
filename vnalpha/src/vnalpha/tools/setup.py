"""Default local tool registry for Phase 5.8/5.9 execution paths."""

from __future__ import annotations

from vnalpha.tools.errors import ToolExecutionError
from vnalpha.tools.models import ToolPermission, ToolSpec
from vnalpha.tools.registry import LocalToolRegistry

TOOL_PERMISSIONS: dict[str, ToolPermission] = {
    "watchlist.scan": ToolPermission.READ_WATCHLIST,
    "watchlist.filter": ToolPermission.READ_WATCHLIST,
    "candidate.explain": ToolPermission.READ_SCORE,
    "candidate.compare": ToolPermission.READ_SCORE,
    "quality.get_status": ToolPermission.READ_QUALITY,
    "quality.get_many_status": ToolPermission.READ_QUALITY,
    "lineage.get_symbol_lineage": ToolPermission.READ_LINEAGE,
    "note.create": ToolPermission.WRITE_NOTE,
    "history.list_sessions": ToolPermission.READ_HISTORY,
}


def build_local_tool_registry(conn) -> LocalToolRegistry:
    """Build a LocalToolRegistry wired to a live DuckDB connection."""
    from vnalpha.tools.lineage import get_symbol_lineage
    from vnalpha.tools.notes import create_note, list_sessions
    from vnalpha.tools.quality import get_many_quality_status, get_quality_status
    from vnalpha.tools.scoring import compare_candidates, explain_candidate
    from vnalpha.tools.watchlist import filter_watchlist, scan_watchlist

    registry = LocalToolRegistry()

    registry.register(
        ToolSpec(
            name="watchlist.scan",
            description="Scan watchlist candidates for a date",
            permission=ToolPermission.READ_WATCHLIST,
        ),
        lambda **kwargs: _scan(scan_watchlist, conn, **kwargs),
    )
    registry.register(
        ToolSpec(
            name="watchlist.filter",
            description="Filter watchlist candidates by conditions",
            permission=ToolPermission.READ_WATCHLIST,
        ),
        lambda **kwargs: _filter(filter_watchlist, conn, **kwargs),
    )
    registry.register(
        ToolSpec(
            name="candidate.explain",
            description="Explain a candidate's score for a date",
            permission=ToolPermission.READ_SCORE,
        ),
        lambda **kwargs: _explain(explain_candidate, conn, **kwargs),
    )
    registry.register(
        ToolSpec(
            name="candidate.compare",
            description="Compare multiple candidates on a date",
            permission=ToolPermission.READ_SCORE,
        ),
        lambda **kwargs: _compare(compare_candidates, conn, **kwargs),
    )
    registry.register(
        ToolSpec(
            name="quality.get_status",
            description="Get data quality status for a symbol or watchlist",
            permission=ToolPermission.READ_QUALITY,
        ),
        lambda **kwargs: get_quality_status(
            conn,
            symbol=kwargs.get("symbol"),
            date=kwargs.get("date"),
        ),
    )
    registry.register(
        ToolSpec(
            name="quality.get_many_status",
            description="Get data quality status for multiple symbols",
            permission=ToolPermission.READ_QUALITY,
        ),
        lambda **kwargs: get_many_quality_status(
            conn,
            symbols=kwargs.get("symbols", []),
            date=kwargs.get("date"),
        ),
    )
    registry.register(
        ToolSpec(
            name="lineage.get_symbol_lineage",
            description="Get data lineage for a symbol on a date",
            permission=ToolPermission.READ_LINEAGE,
        ),
        lambda **kwargs: _lineage(get_symbol_lineage, conn, **kwargs),
    )
    registry.register(
        ToolSpec(
            name="note.create",
            description="Create a research note linked to a symbol",
            permission=ToolPermission.WRITE_NOTE,
        ),
        lambda **kwargs: _create_note(create_note, conn, **kwargs),
    )
    registry.register(
        ToolSpec(
            name="history.list_sessions",
            description="List recent research sessions",
            permission=ToolPermission.READ_HISTORY,
        ),
        lambda **kwargs: list_sessions(conn, limit=kwargs.get("limit", 20)),
    )
    return registry


def _scan(impl, conn, **kwargs):
    date = kwargs.get("date")
    if date is None:
        raise ToolExecutionError("watchlist.scan requires 'date' argument.")
    return impl(conn, date=date, min_score=kwargs.get("min_score", 0.0))


def _filter(impl, conn, **kwargs):
    date = kwargs.get("date")
    if date is None:
        raise ToolExecutionError("watchlist.filter requires 'date' argument.")
    return impl(conn, date=date, filters=kwargs.get("filters", []))


def _explain(impl, conn, **kwargs):
    symbol = kwargs.get("symbol")
    date = kwargs.get("date")
    if symbol is None or date is None:
        raise ToolExecutionError("candidate.explain requires 'symbol' and 'date'.")
    return impl(conn, symbol=symbol, date=date)


def _compare(impl, conn, **kwargs):
    symbols = kwargs.get("symbols")
    date = kwargs.get("date")
    if symbols is None or date is None:
        raise ToolExecutionError("candidate.compare requires 'symbols' and 'date'.")
    return impl(conn, symbols=symbols, date=date)


def _lineage(impl, conn, **kwargs):
    symbol = kwargs.get("symbol")
    date = kwargs.get("date")
    if symbol is None or date is None:
        raise ToolExecutionError(
            "lineage.get_symbol_lineage requires 'symbol' and 'date'."
        )
    return impl(conn, symbol=symbol, date=date)


def _create_note(impl, conn, **kwargs):
    symbol = kwargs.get("symbol")
    note_text = kwargs.get("note_text")
    if symbol is None or note_text is None:
        raise ToolExecutionError("note.create requires 'symbol' and 'note_text'.")
    return impl(
        conn,
        symbol=symbol,
        note_text=note_text,
        session_id=kwargs.get("session_id"),
        tags=kwargs.get("tags"),
    )
