from __future__ import annotations

import duckdb
import pytest

from vnalpha.assistant import executor as executor_module
from vnalpha.assistant.errors import ToolExecutionError
from vnalpha.assistant.executor import AssistantExecutor
from vnalpha.assistant.models import AssistantPlan, ToolPlanStep
from vnalpha.warehouse.assistant_repo import create_assistant_session
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def conn():
    connection = duckdb.connect(":memory:")
    run_migrations(conn=connection)
    yield connection
    connection.close()


def test_executor_does_not_log_data_ensure_for_missing_symbols(conn, monkeypatch):
    session_id = create_assistant_session(
        conn, surface="test", user_prompt="missing symbols"
    )
    warnings: list[str] = []
    monkeypatch.setattr(
        executor_module.logger,
        "warning",
        lambda *_args, **_kwargs: warnings.append("warning"),
    )
    step = ToolPlanStep(
        step_id="debug",
        tool_name="candidate.compare",
        arguments={"symbols": None, "date": None},
        purpose="debug",
        required_permission="READ_WATCHLIST",
    )

    with pytest.raises(ToolExecutionError):
        AssistantExecutor(conn, assistant_session_id=session_id).execute(
            AssistantPlan(intent="compare_symbols", steps=[step])
        )

    assert warnings == []
