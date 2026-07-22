"""Default local tool registry for policy-governed execution paths."""

from __future__ import annotations

from pathlib import Path

from vnalpha.data_availability.deep_readiness_models import ContextRequirement
from vnalpha.policy.tool_policy import TOOL_PERMISSIONS_BY_NAME
from vnalpha.provisioning_queue import DEFAULT_QUEUE_PATH
from vnalpha.tools.current_symbol_research import current_symbol_research
from vnalpha.tools.ensure_current_symbol import ensure_current_symbol
from vnalpha.tools.errors import ToolExecutionError
from vnalpha.tools.fetch import fetch_symbol_data
from vnalpha.tools.lineage import get_symbol_lineage
from vnalpha.tools.models import ToolPermission, ToolSpec
from vnalpha.tools.notes import create_note, list_sessions
from vnalpha.tools.quality import get_many_quality_status, get_quality_status
from vnalpha.tools.registry import LocalToolRegistry
from vnalpha.tools.research_automation import (
    create_feature,
    run_event_study,
    run_indicator,
    scan_pattern,
    test_hypothesis,
    validate_feature,
)
from vnalpha.tools.research_context import (
    get_market_regime,
    get_sector_strength,
    get_symbol_alignment,
)
from vnalpha.tools.research_intelligence import (
    deep_symbol_analysis,
    generate_research_scenario,
    generate_shortlist,
    get_setup_history,
    summarize_watchlist_deep,
)
from vnalpha.tools.scoring import compare_candidates, explain_candidate
from vnalpha.tools.watchlist import filter_watchlist, scan_watchlist

TOOL_PERMISSIONS: dict[str, ToolPermission] = dict(TOOL_PERMISSIONS_BY_NAME)


def build_local_tool_registry(
    conn,
    *,
    warehouse_path: Path | str | None = None,
    queue_path: Path | None = DEFAULT_QUEUE_PATH,
) -> LocalToolRegistry:
    """Build a LocalToolRegistry wired to a live DuckDB connection."""
    registry = LocalToolRegistry()

    research_tools = (
        (
            "research.indicator.run",
            "Run a deterministic indicator experiment",
            run_indicator,
        ),
        (
            "research.feature.create",
            "Persist a research feature definition",
            create_feature,
        ),
        (
            "research.feature.validate",
            "Validate a persisted research feature",
            validate_feature,
        ),
        (
            "research.hypothesis.test",
            "Test a bounded historical hypothesis",
            test_hypothesis,
        ),
        (
            "research.pattern.scan",
            "Scan persisted features for a research pattern",
            scan_pattern,
        ),
        (
            "research.event_study.run",
            "Run an offline research event study",
            run_event_study,
        ),
    )
    for name, description, implementation in research_tools:
        registry.register(
            ToolSpec(
                name=name,
                description=description,
                permission=ToolPermission.WRITE_DATA,
            ),
            lambda implementation=implementation, **kwargs: implementation(
                conn, **kwargs
            ),
        )

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
            name="watchlist.summarize_deep",
            description="Summarize persisted watchlist structure and context",
            permission=ToolPermission.READ_WATCHLIST,
        ),
        lambda **kwargs: summarize_watchlist_deep(
            conn, date=kwargs.get("date"), top=kwargs.get("top")
        ),
    )
    registry.register(
        ToolSpec(
            name="shortlist.generate",
            description="Generate a deterministic research shortlist from persisted artifacts",
            permission=ToolPermission.READ_WATCHLIST,
        ),
        lambda **kwargs: generate_shortlist(
            conn,
            date=kwargs.get("date"),
            top=kwargs.get("top"),
            min_score=kwargs.get("min_score"),
        ),
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
            name="analysis.deep_symbol",
            description="Compose a deep warehouse-grounded symbol research payload",
            permission=ToolPermission.READ_SCORE,
        ),
        lambda **kwargs: _deep_analysis(deep_symbol_analysis, conn, **kwargs),
    )
    registry.register(
        ToolSpec(
            name="scenario.generate_research_plan",
            description="Generate a conditional research-only scenario from persisted data",
            permission=ToolPermission.READ_SCORE,
        ),
        lambda **kwargs: _scenario(generate_research_scenario, conn, **kwargs),
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
            name="market.get_regime",
            description="Read a persisted market regime research snapshot",
            permission=ToolPermission.READ_FEATURES,
        ),
        lambda **kwargs: get_market_regime(conn, date=kwargs.get("date")),
    )
    registry.register(
        ToolSpec(
            name="sector.get_strength",
            description="Read persisted ranked sector strength research snapshots",
            permission=ToolPermission.READ_FEATURES,
        ),
        lambda **kwargs: get_sector_strength(
            conn, date=kwargs.get("date"), top=kwargs.get("top")
        ),
    )
    registry.register(
        ToolSpec(
            name="sector.get_symbol_alignment",
            description="Read a symbol's persisted sector research alignment",
            permission=ToolPermission.READ_FEATURES,
        ),
        lambda **kwargs: _alignment(get_symbol_alignment, conn, **kwargs),
    )
    registry.register(
        ToolSpec(
            name="evidence.get_setup_history",
            description="Read persisted outcome evidence for a setup type",
            permission=ToolPermission.READ_HISTORY,
        ),
        lambda **kwargs: _setup_history(get_setup_history, conn, **kwargs),
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
    registry.register(
        ToolSpec(
            name="data.ensure_current_symbol",
            description="Provision and validate the minimum current-symbol analysis inputs",
            permission=ToolPermission.WRITE_DATA,
        ),
        lambda **kwargs: _ensure_current_symbol(ensure_current_symbol, conn, **kwargs),
    )
    registry.register(
        ToolSpec(
            name="data.fetch",
            description="Fetch OHLCV data for a symbol from vnstock-service into the warehouse",
            permission=ToolPermission.WRITE_DATA,
        ),
        lambda **kwargs: _fetch_data(fetch_symbol_data, conn, **kwargs),
    )
    registry.register(
        ToolSpec(
            name="analysis.current_symbol",
            description="Provision current-symbol evidence once and compose permitted research context",
            permission=ToolPermission.READ_SCORE,
        ),
        lambda **kwargs: current_symbol_research(
            warehouse_path=warehouse_path,
            queue_path=queue_path,
            **kwargs,
        ),
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


def _deep_analysis(impl, conn, **kwargs):
    symbol = kwargs.get("symbol")
    if symbol is None:
        raise ToolExecutionError("analysis.deep_symbol requires 'symbol'.")
    return impl(conn, symbol=symbol, date=kwargs.get("date"))


def _scenario(impl, conn, **kwargs):
    symbol = kwargs.get("symbol")
    if symbol is None:
        raise ToolExecutionError("scenario.generate_research_plan requires 'symbol'.")
    return impl(conn, symbol=symbol, date=kwargs.get("date"))


def _lineage(impl, conn, **kwargs):
    symbol = kwargs.get("symbol")
    date = kwargs.get("date")
    if symbol is None or date is None:
        raise ToolExecutionError(
            "lineage.get_symbol_lineage requires 'symbol' and 'date'."
        )
    return impl(conn, symbol=symbol, date=date)


def _alignment(impl, conn, **kwargs):
    symbol = kwargs.get("symbol")
    if symbol is None:
        raise ToolExecutionError("sector.get_symbol_alignment requires 'symbol'.")
    return impl(conn, symbol=symbol, date=kwargs.get("date"))


def _setup_history(impl, conn, **kwargs):
    setup_type = kwargs.get("setup_type")
    if setup_type is None:
        raise ToolExecutionError("evidence.get_setup_history requires 'setup_type'.")
    return impl(
        conn,
        setup_type=setup_type,
        horizon_sessions=kwargs.get("horizon_sessions"),
        date=kwargs.get("date"),
    )


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


def _fetch_data(impl, conn, **kwargs):
    symbol = kwargs.get("symbol")
    if symbol is None:
        raise ToolExecutionError("data.fetch requires 'symbol' argument.")
    return impl(
        conn,
        symbol=symbol,
        start=kwargs.get("start"),
        end=kwargs.get("end"),
        interval=kwargs.get("interval", "1D"),
    )


def _ensure_current_symbol(impl, conn, **kwargs):
    symbol = kwargs.get("symbol")
    if symbol is None:
        raise ToolExecutionError(
            "data.ensure_current_symbol requires 'symbol' argument."
        )
    return impl(
        conn,
        symbol=symbol,
        date=kwargs.get("date"),
        data_only=kwargs.get("data_only", False),
        refresh=kwargs.get("refresh", False),
        market_regime_requirement=kwargs.get(
            "market_regime_requirement", ContextRequirement.NOT_REQUESTED
        ),
        sector_strength_requirement=kwargs.get(
            "sector_strength_requirement", ContextRequirement.NOT_REQUESTED
        ),
        correlation_id=kwargs.get("correlation_id"),
    )
