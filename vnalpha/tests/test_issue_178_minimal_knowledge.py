from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from vnalpha.symbol_memory.projection import project_analysis_evidence
from vnalpha.symbol_memory.repository import SymbolMemoryRepository
from vnalpha.tools.research_intelligence import deep_symbol_analysis
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture(autouse=True)
def _knowledge_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VNALPHA_KNOWLEDGE_ROOT", str(tmp_path / "knowledge"))


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    run_migrations(connection)
    return connection


def _seed_analysis(
    conn: duckdb.DuckDBPyConnection,
    *,
    provider: str | None = "FIINQUANTX",
    ingestion_run_id: str | None = "run-001",
) -> None:
    conn.execute(
        "INSERT INTO symbol_master "
        "(symbol, exchange, security_type, classification_source, "
        "last_seen_source_snapshot_id, is_active) "
        "VALUES ('FPT', 'HOSE', 'COMMON_EQUITY', 'reference-fixture', "
        "'snapshot-current', TRUE)"
    )
    conn.execute(
        """
        INSERT INTO symbol_classification_history (
            symbol, effective_from, source_snapshot_id, classification_source,
            exchange, security_type, lifecycle_status, taxonomy_name,
            taxonomy_version
        ) VALUES (
            'FPT', '2026-01-01', 'snapshot-pit', 'reference-fixture',
            'HOSE', 'COMMON_EQUITY', 'ACTIVE', 'ICB', '2024'
        )
        """
    )
    for day in ("2026-07-11", "2026-07-12", "2026-07-13"):
        conn.execute(
            """
            INSERT INTO canonical_ohlcv (
                symbol, time, interval, open, high, low, close, volume,
                selected_provider, quality_status, ingestion_run_id
            ) VALUES ('FPT', ?, '1D', 100, 110, 90, 105, 1000, ?, 'pass', ?)
            """,
            [day, provider, ingestion_run_id],
        )
    conn.execute(
        """
        INSERT INTO feature_snapshot (
            symbol, date, feature_data_status, as_of_bar_date,
            source_row_count, observed_bar_count
        ) VALUES ('FPT', '2026-07-13', 'AVAILABLE', '2026-07-13', 3, 3)
        """
    )
    conn.execute(
        """
        INSERT INTO candidate_score (
            symbol, date, score, candidate_class, setup_type
        ) VALUES ('FPT', '2026-07-13', 0.82, 'WATCH_CANDIDATE',
                  'ACCUMULATION_BASE')
        """
    )


def _tool_outputs() -> dict[str, dict[str, dict[str, object]]]:
    return {
        "analysis": {
            "data": {
                "tool": "analysis.deep_symbol",
                "symbol": "FPT",
                "requested_date": "2026-07-13",
                "as_of_date": "2026-07-13",
            }
        }
    }


def test_projects_point_in_time_identity_and_raw_ohlcv_basis(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    _seed_analysis(conn)
    conn.execute(
        """
        INSERT INTO corporate_action_affected_range (
            signal_id, action_id, revision_id, symbol, affected_from_date,
            affected_to_date, reason
        ) VALUES ('signal-1', 'action-1', 'revision-1', 'FPT',
                  '2026-07-12', '2026-07-13', 'known split evidence')
        """
    )

    analysis = deep_symbol_analysis(conn, "FPT", "2026-07-13")
    assert analysis.data["price_basis"] == "RAW_UNADJUSTED"
    assert analysis.data["corporate_action_overlap"] is True
    assert any("mechanical action effects" in item for item in analysis.data["caveats"])

    result = project_analysis_evidence(
        conn,
        _tool_outputs(),
        correlation_id="turn-178",
    )

    assert not result.warnings
    claims = SymbolMemoryRepository(conn).list_claims("FPT")
    by_predicate = {claim.predicate: claim for claim in claims}
    identity = by_predicate["security_identity"].value
    assert identity == {
        "symbol": "FPT",
        "exchange": "HOSE",
        "security_type": "COMMON_EQUITY",
        "classification_source": "reference-fixture",
        "source_snapshot_id": "snapshot-pit",
        "effective_from": "2026-01-01T00:00:00+07:00",
    }
    basis = by_predicate["canonical_ohlcv_basis"].value
    assert basis["requested_as_of_date"] == "2026-07-13"
    assert basis["resolved_as_of_date"] == "2026-07-13"
    assert basis["first_bar_date"] == "2026-07-11"
    assert basis["last_bar_date"] == "2026-07-13"
    assert basis["value"] == 3
    assert basis["price_basis"] == "RAW_UNADJUSTED"
    assert basis["providers"] == ["FIINQUANTX"]
    assert basis["ingestion_run_ids"] == ["run-001"]
    assert "corporate-action" in basis["corporate_action_caveat"].lower()


def test_missing_optional_ohlcv_lineage_is_explicit(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    _seed_analysis(conn, provider=None, ingestion_run_id=None)

    project_analysis_evidence(conn, _tool_outputs(), correlation_id="turn-178")

    claims = SymbolMemoryRepository(conn).list_claims("FPT")
    basis = next(
        claim.value for claim in claims if claim.predicate == "canonical_ohlcv_basis"
    )
    assert basis["providers"] == []
    assert basis["ingestion_run_ids"] == []
    assert "missing" in basis["lineage_caveat"].lower()


def test_lifecycle_excluded_identity_is_not_replaced_by_current_projection(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    _seed_analysis(conn)
    conn.execute(
        "UPDATE symbol_classification_history "
        "SET listing_date = '2020-01-01', delisting_date = '2026-07-01' "
        "WHERE symbol = 'FPT'"
    )

    result = project_analysis_evidence(conn, _tool_outputs(), correlation_id="turn-178")

    claims = SymbolMemoryRepository(conn).list_claims("FPT")
    assert all(claim.predicate != "security_identity" for claim in claims)
    assert result.projected == ()
    assert "identity" in result.warnings[0]


def test_ambiguous_identity_is_not_projected(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    _seed_analysis(conn)
    conn.execute(
        "INSERT INTO symbol_classification_history "
        "(symbol, effective_from, source_snapshot_id, classification_source, "
        "exchange, security_type, lifecycle_status, taxonomy_name, taxonomy_version) "
        "VALUES ('FPT', '2026-01-01', 'snapshot-overlap', 'reference-fixture', "
        "'HNX', 'COMMON_EQUITY', 'ACTIVE', 'ICB', '2024')"
    )

    result = project_analysis_evidence(conn, _tool_outputs(), correlation_id="turn-178")

    claims = SymbolMemoryRepository(conn).list_claims("FPT")
    assert all(claim.predicate != "security_identity" for claim in claims)
    assert result.projected == ()


def test_mixed_missing_price_basis_fails_closed(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    _seed_analysis(conn)
    conn.execute(
        "UPDATE canonical_ohlcv SET price_basis = NULL "
        "WHERE symbol = 'FPT' AND CAST(time AS DATE) = '2026-07-12'"
    )

    analysis = deep_symbol_analysis(conn, "FPT", "2026-07-13")
    result = project_analysis_evidence(conn, _tool_outputs(), correlation_id="turn-178")

    assert analysis.data["price_basis"] is None
    assert result.projected == ()
    assert "basis" in result.warnings[0]


def test_projected_context_contains_no_bars_or_model_prose(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    _seed_analysis(conn)

    first = project_analysis_evidence(
        conn,
        _tool_outputs(),
        correlation_id="turn-178-a",
    )
    second = project_analysis_evidence(
        conn,
        _tool_outputs(),
        correlation_id="turn-178-b",
    )

    serialized = json.dumps(
        [claim.value for claim in SymbolMemoryRepository(conn).list_claims("FPT")],
        sort_keys=True,
    )
    assert '"open"' not in serialized
    assert '"high"' not in serialized
    assert '"close"' not in serialized
    assert "assistant" not in serialized.lower()
    assert all(claim.created for claim in first.projected)
    assert all(not claim.created for claim in second.projected)
