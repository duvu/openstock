from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pytest

from vnalpha.commands.errors import CommandValidationError
from vnalpha.commands.models import CommandStatus
from vnalpha.commands.parser import parse
from vnalpha.commands.setup import build_default_registry
from vnalpha.observability.context import init_run_context, reset_run_context
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def research_connection(tmp_path: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    reset_run_context()
    _ = init_run_context(surface="test", actor="pytest", log_root=tmp_path)
    with in_memory_connection() as conn:
        run_migrations(conn=conn)
        conn.execute(
            "INSERT INTO feature_snapshot "
            "(symbol, date, close, return_20d, rs_20d_vs_vnindex, base_range_30d, "
            "volatility_20d, volume_ratio, feature_data_status, as_of_bar_date, "
            "benchmark_as_of_bar_date, feature_build_version, lineage_json) VALUES "
            "('FPT', DATE '2026-07-01', 100, 0.12, 0.04, 0.10, 0.02, 0.60, "
            "'EXACT_DATE', DATE '2026-07-01', DATE '2026-07-01', 'v1', "
            '\'{"feature_status_contract_version":"feature-data-status-v1"}\'), '
            "('VNM', DATE '2026-07-01', 80, 0.08, 0.01, 0.20, 0.05, 1.10, "
            "'EXACT_DATE', DATE '2026-07-01', DATE '2026-07-01', 'v1', "
            '\'{"feature_status_contract_version":"feature-data-status-v1"}\')'
        )
        start = date(2026, 7, 1)
        for symbol, base in (("FPT", 100.0), ("VNM", 80.0)):
            for offset in range(15):
                trading_date = start + timedelta(days=offset)
                close = base + offset
                conn.execute(
                    "INSERT INTO canonical_ohlcv "
                    "(symbol, time, interval, open, high, low, close, volume, "
                    "selected_provider, quality_status, ingestion_run_id) "
                    "VALUES (?, ?, '1D', ?, ?, ?, ?, 1000, 'FIXTURE', 'pass', 'run-1')",
                    [
                        symbol,
                        trading_date,
                        close - 0.5,
                        close + 1.0,
                        close - 1.0,
                        close,
                    ],
                )
        conn.execute(
            "INSERT INTO candidate_outcome "
            "(symbol, watchlist_date, horizon_sessions, forward_return, "
            "outcome_status) VALUES "
            "('FPT', DATE '2026-07-01', 20, 0.12, 'COMPLETE'), "
            "('VNM', DATE '2026-07-01', 20, 0.08, 'COMPLETE')"
        )
        yield conn
    reset_run_context()


def _execute(text: str, conn: duckdb.DuckDBPyConnection):
    return build_default_registry().execute(
        parse(text), conn=conn, session_id="session-123"
    )


def test_feature_create_persists_definition_and_reproducibility_artifacts(
    research_connection: duckdb.DuckDBPyConnection,
) -> None:
    result = _execute(
        "/feature create rs_20 = rs_20d_vs_vnindex --universe VN30",
        research_connection,
    )

    assert result.status is CommandStatus.SUCCESS
    row = research_connection.execute(
        "SELECT feature_name, feature_expression, universe FROM research_feature"
    ).fetchone()
    assert row == ("RS_20", "rs_20d_vs_vnindex", "VN30")

    artifact = research_connection.execute(
        "SELECT status, lineage_json, caveats_json, outputs_json FROM research_artifact"
    ).fetchone()
    assert artifact is not None
    assert artifact[0] == "created"
    assert json.loads(artifact[1])["definition_source"] == "slash_command"
    assert json.loads(artifact[2])
    outputs = json.loads(artifact[3])
    for key in (
        "manifest",
        "result_json",
        "summary_md",
        "lineage_json",
        "validation_json",
    ):
        assert Path(outputs[key]).is_file()
    assert (
        "research-only"
        in Path(outputs["summary_md"]).read_text(encoding="utf-8").lower()
    )


def test_feature_validate_reports_schema_and_dataset_coverage(
    research_connection: duckdb.DuckDBPyConnection,
) -> None:
    created = _execute(
        "/feature create rs_20 = rs_20d_vs_vnindex --universe VN30",
        research_connection,
    )
    assert created.status is CommandStatus.SUCCESS

    result = _execute("/feature validate rs_20", research_connection)

    assert result.status is CommandStatus.SUCCESS
    assert result.panels
    content = result.panels[0].content
    assert isinstance(content, dict)
    assert content["schema_valid"] is True
    assert content["symbol_count"] == 2
    assert content["row_count"] == 2
    assert content["period_start"] == "2026-07-01"
    assert content["period_end"] == "2026-07-01"
    assert content["quality_status"] == "good"
    status = research_connection.execute(
        "SELECT status FROM research_artifact"
    ).fetchone()
    assert status == ("validated",)


@pytest.mark.parametrize(
    "definition",
    (
        "leak = future_return_10d",
        "trade_signal = place_order(close)",
        "next_close = lead(close, 1)",
    ),
)
def test_feature_create_rejects_future_data_and_execution_actions(
    definition: str,
    research_connection: duckdb.DuckDBPyConnection,
) -> None:
    with pytest.raises(CommandValidationError):
        _ = _execute(f"/feature create {definition}", research_connection)

    assert research_connection.execute(
        "SELECT count(*) FROM research_feature"
    ).fetchone() == (0,)


@pytest.mark.parametrize(
    "text",
    (
        "/feature",
        "/feature unsupported x",
        "/feature create",
        "/feature create invalid-expression",
        "/feature validate",
        "/feature validate missing",
    ),
)
def test_feature_rejects_unsupported_or_invalid_commands(
    text: str,
    research_connection: duckdb.DuckDBPyConnection,
) -> None:
    with pytest.raises(CommandValidationError):
        _ = _execute(text, research_connection)


def test_feature_help_uses_vietnamese_market_example() -> None:
    meta = build_default_registry().get("feature")

    assert "FPT" in " ".join(meta.examples) or "VN30" in " ".join(meta.examples)
    assert "/feature create" in meta.usage
    assert "/feature validate" in meta.usage


@pytest.mark.parametrize(
    ("command", "artifact_type", "event_type"),
    (
        (
            "/experiment indicator relative strength 20 sessions vs VNINDEX --universe VN30",
            "indicator_experiment",
            "RESEARCH_EXPERIMENT_SUCCEEDED",
        ),
        (
            "/pattern scan accumulation base with volatility contraction and volume dry-up --universe VN30 --date 2026-07-01",
            "pattern_scan",
            "PATTERN_SCAN_COMPLETED",
        ),
        (
            "/hypothesis test symbols with rs_20 > 0 have better 20-session return",
            "hypothesis_test",
            "RESEARCH_HYPOTHESIS_TESTED",
        ),
        (
            "/experiment event-study rs_20d_vs_vnindex > 0 --horizon 10",
            "offline_event_study",
            "OFFLINE_EVENT_STUDY_COMPLETED",
        ),
    ),
)
def test_research_workflows_persist_validated_research_only_artifacts(
    command: str,
    artifact_type: str,
    event_type: str,
    research_connection: duckdb.DuckDBPyConnection,
) -> None:
    result = _execute(command, research_connection)

    assert result.status is CommandStatus.SUCCESS
    row = research_connection.execute(
        "SELECT artifact_type, status, lineage_json, caveats_json, outputs_json, "
        "sandbox_job_id, generated_code_path FROM research_artifact "
        "ORDER BY created_at_ts DESC LIMIT 1"
    ).fetchone()
    assert row is not None
    assert row[0] == artifact_type
    assert row[1] in {"succeeded", "validated"}
    assert json.loads(row[2])["computation"] == "approved_deterministic_tool"
    assert json.loads(row[3])
    assert row[5] is None
    assert row[6] is None
    outputs = json.loads(row[4])
    assert Path(outputs["manifest"]).is_file()
    summary = Path(outputs["summary_md"]).read_text(encoding="utf-8").lower()
    assert "research-only" in summary
    audit = init_run_context(surface="test").audit_path.read_text(encoding="utf-8")
    assert event_type in audit


def test_pattern_scan_persists_candidate_table(
    research_connection: duckdb.DuckDBPyConnection,
) -> None:
    result = _execute(
        "/pattern scan accumulation base with volatility contraction and volume dry-up --universe VN30",
        research_connection,
    )

    assert result.status is CommandStatus.SUCCESS
    assert result.tables[0].rows == [["FPT", 0.1, 0.02, 0.6]]
    outputs = json.loads(
        research_connection.execute(
            "SELECT outputs_json FROM research_artifact ORDER BY created_at_ts DESC LIMIT 1"
        ).fetchone()[0]
    )
    assert Path(outputs["candidates_csv"]).is_file()


@pytest.mark.parametrize(
    ("condition", "horizon"),
    (
        ("rs_20d_vs_vnindex > 0", 5),
        ("volume_ratio >= 0.6", 10),
    ),
)
def test_event_study_executes_condition_and_requested_horizon(
    condition: str,
    horizon: int,
    research_connection: duckdb.DuckDBPyConnection,
) -> None:
    result = _execute(
        f"/experiment event-study {condition} --horizon {horizon}",
        research_connection,
    )

    assert result.status is CommandStatus.SUCCESS
    content = result.panels[0].content
    assert content["metrics"]["horizon_sessions"] == horizon
    assert content["metrics"]["sample_size"] == 2
    lineage = content["lineage"]
    assert lineage["specification_hash"]
    assert lineage["price_basis"] == "canonical_raw_unadjusted"
    assert lineage["future_feature_selection"] is False
    assert str(horizon) in lineage["outcome_definition"]


def test_event_study_rejects_ambiguous_condition_and_backtest_alias(
    research_connection: duckdb.DuckDBPyConnection,
) -> None:
    with pytest.raises(CommandValidationError, match="ambiguous"):
        _execute(
            "/experiment event-study breakout after accumulation base --horizon 10",
            research_connection,
        )
    with pytest.raises(CommandValidationError, match="alias is disabled"):
        _execute(
            "/experiment backtest rs_20d_vs_vnindex > 0 --horizon 10",
            research_connection,
        )


def test_offline_event_study_refuses_live_execution(
    research_connection: duckdb.DuckDBPyConnection,
) -> None:
    with pytest.raises(CommandValidationError):
        _execute(
            "/experiment event-study deploy live trades through broker",
            research_connection,
        )


@pytest.mark.parametrize(
    "text",
    (
        "/experiment",
        "/experiment unknown x",
        "/pattern",
        "/pattern unknown x",
        "/hypothesis",
        "/hypothesis unknown x",
    ),
)
def test_research_workflows_render_unsupported_subcommands_inline(
    text: str,
    research_connection: duckdb.DuckDBPyConnection,
) -> None:
    with pytest.raises(CommandValidationError):
        _ = _execute(text, research_connection)


def test_insufficient_dataset_coverage_warns_without_claiming_success(
    tmp_path: Path,
) -> None:
    reset_run_context()
    _ = init_run_context(surface="test", actor="pytest", log_root=tmp_path)
    with in_memory_connection() as conn:
        run_migrations(conn=conn)
        result = _execute(
            "/experiment indicator relative strength 20 sessions vs VNINDEX",
            conn,
        )

        assert result.status is CommandStatus.PARTIAL
        assert any("insufficient" in warning.lower() for warning in result.warnings)
        assert conn.execute("SELECT status FROM research_artifact").fetchone() == (
            "rejected",
        )
    reset_run_context()


def test_missing_hypothesis_outcome_is_partial_on_public_command_surface(
    research_connection: duckdb.DuckDBPyConnection,
) -> None:
    research_connection.execute("DELETE FROM candidate_outcome WHERE symbol = 'VNM'")

    result = _execute(
        "/hypothesis test symbols with rs_20 > 0 have better 20-session return",
        research_connection,
    )

    assert result.status is CommandStatus.PARTIAL
    assert any("no complete later observation" in item for item in result.warnings)
    artifact = research_connection.execute(
        "SELECT status, caveats_json FROM research_artifact "
        "ORDER BY created_at_ts DESC LIMIT 1"
    ).fetchone()
    assert artifact is not None
    assert artifact[0] == "rejected"
    assert any(
        "no complete later observation" in item for item in json.loads(artifact[1])
    )
