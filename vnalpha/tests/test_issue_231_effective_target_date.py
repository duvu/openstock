from __future__ import annotations

import json
from datetime import date

import duckdb
import pytest

from vnalpha.assistant.app import AssistantApp
from vnalpha.assistant.errors import AssistantInputValidationError
from vnalpha.assistant.gateway import FakeLLMClient
from vnalpha.assistant.models import AssistantRequest, PreparedAssistantTurn
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    run_migrations(conn=connection)
    yield connection
    connection.close()


def _intent_response(intent: str, entities: dict[str, object]) -> str:
    return json.dumps(
        {
            "intent": intent,
            "confidence": 0.99,
            "entities": entities,
            "safety_flags": [],
        }
    )


def _prepare(
    conn: duckdb.DuckDBPyConnection,
    *,
    intent: str,
    entities: dict[str, object],
    request_date: str | None,
    request_date_is_implicit: bool = False,
) -> PreparedAssistantTurn:
    client = FakeLLMClient(responses=[(_intent_response(intent, entities), {})])
    prepared = AssistantApp(conn, llm_client=client).prepare(
        AssistantRequest(
            current_user_prompt="research request",
            date=request_date,
            date_is_implicit=request_date_is_implicit,
        )
    )
    assert isinstance(prepared, PreparedAssistantTurn)
    return prepared


def test_request_target_date_replaces_classifier_null_and_is_persisted(conn) -> None:
    # Given: the classifier emits its normal explicit null date.
    # When: the TUI/request supplies the active target date.
    prepared = _prepare(
        conn,
        intent="scan_candidates",
        entities={"date": None},
        request_date="2026-07-17",
    )

    # Then: plan, prepared request, and persisted request use one effective date.
    assert prepared.request.date == "2026-07-17"
    assert prepared.intent_result.entities["date"] == "2026-07-17"
    assert prepared.plan.steps[0].arguments["date"] == "2026-07-17"
    row = conn.execute(
        "SELECT request_json FROM prepared_assistant_turn WHERE prepared_turn_id = ?",
        [prepared.prepared_turn_id],
    ).fetchone()
    assert row is not None
    assert json.loads(row[0])["date"] == "2026-07-17"


def test_explicit_classified_date_overrides_request_target_date(conn) -> None:
    # Given: the prompt contains an explicit date and the TUI has another target.
    # When: the assistant prepares the deterministic plan.
    prepared = _prepare(
        conn,
        intent="filter_candidates",
        entities={"date": "2026-07-10", "filters": {}},
        request_date="2026-07-17",
    )

    # Then: the explicit prompt date wins everywhere.
    assert prepared.request.date == "2026-07-10"
    assert prepared.plan.steps[0].arguments["date"] == "2026-07-10"


@pytest.mark.parametrize(
    ("intent", "entities", "tool_name"),
    [
        ("filter_candidates", {"date": None, "filters": {}}, "watchlist.filter"),
        (
            "explain_symbol",
            {"date": None, "symbol": "FPT"},
            "candidate.explain",
        ),
    ],
)
def test_request_target_date_reaches_filter_and_symbol_read(
    conn,
    intent: str,
    entities: dict[str, object],
    tool_name: str,
) -> None:
    # Given: a date-bound workflow has a classifier-null date and request default.
    # When: the assistant prepares the workflow.
    prepared = _prepare(
        conn,
        intent=intent,
        entities=entities,
        request_date="2026-07-17",
    )

    # Then: the required read tool receives the same effective request date.
    step = next(item for item in prepared.plan.steps if item.tool_name == tool_name)
    assert step.arguments["date"] == "2026-07-17"


def test_invalid_classified_date_remains_an_input_validation_error(conn) -> None:
    # Given: an explicit classified date is not in the accepted date contract.
    client = FakeLLMClient(
        responses=[
            (
                _intent_response(
                    "explain_symbol", {"symbol": "FPT", "date": "not-a-date"}
                ),
                {},
            )
        ]
    )

    # When / Then: preparation rejects it at the assistant boundary.
    with pytest.raises(AssistantInputValidationError, match="Invalid date value"):
        AssistantApp(conn, llm_client=client).prepare(
            AssistantRequest(current_user_prompt="explain FPT on not-a-date")
        )


def test_no_default_resolves_and_persists_one_effective_date(conn) -> None:
    # Given: neither classifier nor request supplies a date.
    # When: the assistant prepares a date-bound plan.
    prepared = _prepare(
        conn,
        intent="scan_candidates",
        entities={"date": None},
        request_date=None,
    )

    # Then: request, entity, tool, and persisted projections share one ISO date.
    effective_date = prepared.request.date
    assert effective_date is not None
    assert date.fromisoformat(effective_date)
    assert prepared.intent_result.entities["date"] == effective_date
    assert prepared.plan.steps[0].arguments["date"] == effective_date
    row = conn.execute(
        "SELECT request_json, intent_json, plan_json "
        "FROM prepared_assistant_turn WHERE prepared_turn_id = ?",
        [prepared.prepared_turn_id],
    ).fetchone()
    assert row is not None
    assert json.loads(row[0])["date"] == effective_date
    assert json.loads(row[1])["entities"]["date"] == effective_date
    assert json.loads(row[2])["steps"][0]["arguments"]["date"] == effective_date


def test_no_default_uses_current_market_session_before_planning(
    conn, monkeypatch
) -> None:
    # Given: the current calendar day resolves to the previous market session.
    from vnalpha.assistant import effective_date as effective_date_module

    monkeypatch.setattr(
        effective_date_module,
        "resolve_market_session_date",
        lambda _value: "2026-07-17",
        raising=False,
    )

    # When: the assistant prepares a request with no explicit date.
    prepared = _prepare(
        conn,
        intent="deep_analyze_symbol",
        entities={"date": None, "symbol": "VCB"},
        request_date=None,
    )

    # Then: request and provisioning plan share the resolved market session.
    assert prepared.request.date == "2026-07-17"
    assert prepared.plan.steps[0].arguments["date"] == "2026-07-17"


def test_pre_resolved_implicit_tui_date_uses_current_symbol_session(
    conn, monkeypatch
) -> None:
    from vnalpha.assistant import effective_date as effective_date_module

    monkeypatch.setattr(
        effective_date_module,
        "resolve_market_session_date",
        lambda _value: "2026-07-17",
    )

    prepared = _prepare(
        conn,
        intent="deep_analyze_symbol",
        entities={"date": None, "symbol": "VCB"},
        request_date="2026-07-19",
        request_date_is_implicit=True,
    )

    assert prepared.request.date == "2026-07-17"
    assert prepared.plan.steps[0].arguments["date"] == "2026-07-17"


def test_fetch_data_uses_current_symbol_session(conn, monkeypatch) -> None:
    from vnalpha.assistant import effective_date as effective_date_module

    monkeypatch.setattr(
        effective_date_module,
        "resolve_market_session_date",
        lambda _value: "2026-07-17",
    )

    prepared = _prepare(
        conn,
        intent="fetch_data",
        entities={"date": None, "symbol": "VCB"},
        request_date="2026-07-19",
        request_date_is_implicit=True,
    )

    assert prepared.request.date == "2026-07-17"
    assert prepared.plan.steps[0].tool_name == "data.ensure_current_symbol"
    assert prepared.plan.steps[0].arguments["date"] == "2026-07-17"


def test_calendar_coverage_failure_is_typed_and_terminal(conn, monkeypatch) -> None:
    from vnalpha.assistant import effective_date as effective_date_module
    from vnalpha.ingestion.trading_calendar import CalendarCoverageError

    def fail_coverage(_value):
        raise CalendarCoverageError("calendar coverage unavailable")

    monkeypatch.setattr(
        effective_date_module,
        "resolve_market_session_date",
        fail_coverage,
    )
    client = FakeLLMClient(
        responses=[
            (
                _intent_response(
                    "deep_analyze_symbol", {"date": None, "symbol": "FPT"}
                ),
                {},
            )
        ]
    )

    with pytest.raises(AssistantInputValidationError, match="calendar coverage"):
        AssistantApp(conn, llm_client=client).prepare(
            AssistantRequest(current_user_prompt="research request")
        )

    assert conn.execute("SELECT status FROM assistant_session").fetchone() == (
        "VALIDATION_ERROR",
    )


def test_non_current_implicit_date_preserves_generic_resolution(
    conn, monkeypatch
) -> None:
    from vnalpha.assistant import effective_date as effective_date_module

    monkeypatch.setattr(
        effective_date_module,
        "resolve_date",
        lambda _value: "2027-01-04",
    )

    def reject_market_resolution(_value):
        raise AssertionError("non-current intent must not use market-session coverage")

    monkeypatch.setattr(
        effective_date_module,
        "resolve_market_session_date",
        reject_market_resolution,
    )

    prepared = _prepare(
        conn,
        intent="scan_candidates",
        entities={"date": None},
        request_date=None,
    )

    assert prepared.request.date == "2027-01-04"
    assert prepared.plan.steps[0].arguments["date"] == "2027-01-04"
