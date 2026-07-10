from __future__ import annotations

from datetime import date
from io import StringIO

import duckdb
import pytest
from rich.console import Console

from vnalpha.commands.models import CommandResult, CommandStatus, status_color
from vnalpha.commands.parser import parse
from vnalpha.commands.setup import build_default_registry
from vnalpha.data_availability.models import EnsureDataResult, EnsureDataStatus
from vnalpha.tools.executor import TracedLocalToolExecutor
from vnalpha.tools.setup import build_local_tool_registry
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import save_candidate_score


@pytest.fixture
def conn():
    connection = duckdb.connect(":memory:")
    run_migrations(conn=connection)
    yield connection
    connection.close()


def _tool_executor(conn):
    return TracedLocalToolExecutor(
        conn,
        build_local_tool_registry(conn),
        session_id="command-status-test",
    )


def _ensure_result(
    symbol: str, target_date: str, status: EnsureDataStatus
) -> EnsureDataResult:
    return EnsureDataResult(symbol=symbol, target_date=target_date, status=status)


def _save_score(conn, symbol: str, target_date: str) -> None:
    save_candidate_score(
        conn,
        symbol,
        target_date,
        {
            "score": 0.82,
            "candidate_class": "STRONG_CANDIDATE",
            "setup_type": "ACCUMULATION_BASE",
            "trend_score": 0.8,
            "relative_strength_score": 0.7,
            "volume_score": 0.6,
            "base_score": 0.5,
            "breakout_score": 0.4,
            "risk_quality_score": 0.9,
            "risk_flags": [],
            "rule_outcomes": {},
        },
    )


@pytest.mark.parametrize(
    ("status", "expected_color"),
    [
        (CommandStatus.SUCCESS, "green"),
        (CommandStatus.EMPTY_RESULT, "cyan"),
        (CommandStatus.PARTIAL, "yellow"),
        (CommandStatus.FAILED, "red"),
        (CommandStatus.VALIDATION_ERROR, "yellow"),
    ],
)
def test_command_status_is_string_compatible_and_has_deterministic_color(
    status: CommandStatus, expected_color: str
) -> None:
    result = CommandResult(status=status.value, title="Status test")

    assert result.status is status
    assert result.status == status.value
    assert status_color(result.status) == expected_color


@pytest.mark.parametrize(
    "command", ["/explain FPT --date 2000-01-01", "/compare FPT VNM --date 2000-01-01"]
)
def test_no_candidate_data_returns_empty_result(
    conn, monkeypatch, command: str
) -> None:
    from vnalpha import data_availability

    monkeypatch.setattr(
        data_availability,
        "ensure_symbol_analysis_ready",
        lambda _conn, symbol, target_date: _ensure_result(
            symbol, target_date, EnsureDataStatus.READY
        ),
    )

    result = build_default_registry().execute(
        parse(command), conn=conn, tool_executor=_tool_executor(conn)
    )

    assert result.status is CommandStatus.EMPTY_RESULT


@pytest.mark.parametrize("command", ["/explain FPT", "/compare FPT VNM"])
def test_usable_output_with_partial_provisioning_returns_partial(
    conn, monkeypatch, command: str
) -> None:
    from vnalpha import data_availability

    target_date = date.today().isoformat()
    _save_score(conn, "FPT", target_date)
    _save_score(conn, "VNM", target_date)
    monkeypatch.setattr(
        data_availability,
        "ensure_symbol_analysis_ready",
        lambda _conn, symbol, requested_date: _ensure_result(
            symbol, requested_date, EnsureDataStatus.PARTIAL
        ),
    )

    result = build_default_registry().execute(
        parse(f"{command} --date {target_date}"),
        conn=conn,
        tool_executor=_tool_executor(conn),
    )

    assert result.status is CommandStatus.PARTIAL


@pytest.mark.parametrize("status", list(CommandStatus))
def test_renderers_accept_every_command_status(status: CommandStatus) -> None:
    from vnalpha.commands.renderers.rich_renderer import render_result
    from vnalpha.commands.renderers.textual_renderer import result_to_markup

    result = CommandResult(status=status, title=f"{status.value} title", summary="body")
    output = StringIO()
    console = Console(file=output, highlight=False)

    render_result(result, console=console)
    console.print(result_to_markup(result))

    assert f"{status.value} title" in output.getvalue()


def test_executor_persists_empty_result_status_without_schema_change(
    conn, monkeypatch
) -> None:
    from vnalpha import data_availability
    from vnalpha.commands.executor import CommandExecutor

    monkeypatch.setattr(
        data_availability,
        "ensure_symbol_analysis_ready",
        lambda _conn, symbol, target_date: _ensure_result(
            symbol, target_date, EnsureDataStatus.READY
        ),
    )

    result = CommandExecutor(conn, surface="cli").execute(
        "/compare FPT VNM --date 2000-01-01"
    )
    persisted_status = conn.execute(
        "SELECT status FROM research_session ORDER BY started_at DESC LIMIT 1"
    ).fetchone()[0]

    assert result.status is CommandStatus.EMPTY_RESULT
    assert persisted_status == CommandStatus.EMPTY_RESULT.value
