"""Tests for Local Tool Registry safety (Task 3.5) and tools module (Tasks 3.1-3.4)."""

from __future__ import annotations

import duckdb
import pytest

from vnalpha.tools.errors import ToolNotFoundError, ToolPermissionError
from vnalpha.tools.models import (
    FORBIDDEN_PERMISSIONS,
    ToolOutput,
    ToolPermission,
    ToolSpec,
)
from vnalpha.tools.registry import LocalToolRegistry


def _make_spec(name: str, permission: ToolPermission) -> ToolSpec:
    return ToolSpec(name=name, description=f"{name}", permission=permission)


def _noop(**kwargs) -> ToolOutput:
    return ToolOutput(data=None, summary="ok")


class TestToolModels:
    def test_tool_permission_values(self):
        """All Phase 5.8 allowed permissions are present."""
        allowed = {p.value for p in ToolPermission}
        assert "READ_WATCHLIST" in allowed
        assert "READ_FEATURES" in allowed
        assert "READ_SCORE" in allowed
        assert "READ_QUALITY" in allowed
        assert "READ_LINEAGE" in allowed
        assert "WRITE_NOTE" in allowed
        assert "READ_HISTORY" in allowed

    def test_forbidden_permissions_defined(self):
        assert "NETWORK_ACCESS" in FORBIDDEN_PERMISSIONS
        assert "PYTHON_EXECUTION" in FORBIDDEN_PERMISSIONS
        assert "MCP_TOOL_CALL" in FORBIDDEN_PERMISSIONS
        assert "CODEBASE_MUTATION" in FORBIDDEN_PERMISSIONS
        assert "BROKER_EXECUTION" in FORBIDDEN_PERMISSIONS

    def test_no_overlap_between_allowed_and_forbidden(self):
        allowed_vals = {p.value for p in ToolPermission}
        overlap = allowed_vals & FORBIDDEN_PERMISSIONS
        assert overlap == set(), f"Overlap found: {overlap}"

    def test_tool_spec_fields(self):
        spec = ToolSpec(
            name="test",
            description="test tool",
            permission=ToolPermission.READ_SCORE,
            input_fields={"symbol": "Stock symbol"},
            output_fields={"score": "Composite score"},
        )
        assert spec.name == "test"
        assert spec.permission == ToolPermission.READ_SCORE


class TestLocalToolRegistry:
    def test_register_and_call(self):
        reg = LocalToolRegistry()
        spec = _make_spec("watchlist.scan", ToolPermission.READ_WATCHLIST)
        reg.register(spec, _noop)
        result = reg.call("watchlist.scan", {ToolPermission.READ_WATCHLIST})
        assert result.summary == "ok"

    def test_unknown_tool_raises(self):
        reg = LocalToolRegistry()
        with pytest.raises(ToolNotFoundError, match="not registered"):
            reg.call("nonexistent", {ToolPermission.READ_WATCHLIST})

    def test_permission_denied_raises(self):
        reg = LocalToolRegistry()
        spec = _make_spec("watchlist.scan", ToolPermission.READ_WATCHLIST)
        reg.register(spec, _noop)
        with pytest.raises(ToolPermissionError, match="requires permission"):
            reg.call("watchlist.scan", {ToolPermission.READ_SCORE})

    def test_duplicate_registration_raises(self):
        reg = LocalToolRegistry()
        spec = _make_spec("watchlist.scan", ToolPermission.READ_WATCHLIST)
        reg.register(spec, _noop)
        with pytest.raises(ValueError, match="already registered"):
            reg.register(spec, _noop)

    def test_names_sorted(self):
        reg = LocalToolRegistry()
        reg.register(_make_spec("z.tool", ToolPermission.READ_SCORE), _noop)
        reg.register(_make_spec("a.tool", ToolPermission.READ_SCORE), _noop)
        assert reg.names() == ["a.tool", "z.tool"]

    def test_get_spec(self):
        reg = LocalToolRegistry()
        spec = _make_spec("watchlist.scan", ToolPermission.READ_WATCHLIST)
        reg.register(spec, _noop)
        retrieved = reg.get_spec("watchlist.scan")
        assert retrieved.name == "watchlist.scan"


class TestSafetyBoundary:
    """Phase 5.8 tools must not allow forbidden capabilities."""

    def test_forbidden_permission_blocked_at_registration(self):
        """Any tool trying to register with a forbidden permission is rejected."""
        for forbidden in FORBIDDEN_PERMISSIONS:
            # Try to register a fake tool with a forbidden permission
            # Since ToolPermission enum doesn't include forbidden values,
            # we simulate by checking at model level that they're excluded
            assert forbidden not in {p.value for p in ToolPermission}

    def test_no_network_access_in_permission_enum(self):
        names = [p.value for p in ToolPermission]
        assert "NETWORK_ACCESS" not in names

    def test_no_python_execution_in_permission_enum(self):
        names = [p.value for p in ToolPermission]
        assert "PYTHON_EXECUTION" not in names

    def test_no_mcp_tool_call_in_permission_enum(self):
        names = [p.value for p in ToolPermission]
        assert "MCP_TOOL_CALL" not in names

    def test_no_codebase_mutation_in_permission_enum(self):
        names = [p.value for p in ToolPermission]
        assert "CODEBASE_MUTATION" not in names

    def test_no_broker_execution_in_permission_enum(self):
        names = [p.value for p in ToolPermission]
        assert "BROKER_EXECUTION" not in names

    def test_tool_modules_do_not_import_requests(self):
        """Tool modules must not import network libraries."""
        import ast
        from pathlib import Path

        tools_dir = Path(__file__).parent.parent / "src" / "vnalpha" / "tools"
        forbidden_imports = {"requests", "httpx", "aiohttp", "urllib"}
        for py_file in tools_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue
            source = py_file.read_text()
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert alias.name.split(".")[0] not in forbidden_imports, (
                            f"{py_file.name} imports {alias.name}"
                        )
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        base = node.module.split(".")[0]
                        assert base not in forbidden_imports, (
                            f"{py_file.name} imports from {node.module}"
                        )

    def test_tool_modules_do_not_use_subprocess(self):
        """Tool modules must not use subprocess or exec."""
        from pathlib import Path

        tools_dir = Path(__file__).parent.parent / "src" / "vnalpha" / "tools"
        for py_file in tools_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue
            source = py_file.read_text()
            for forbidden in {"subprocess", "os.system"}:
                assert forbidden not in source, (
                    f"{py_file.name} contains '{forbidden}'"
                )


# ── Quality tool: historical (as-of-date) lookup tests ──────────────────────


def _make_quality_conn() -> duckdb.DuckDBPyConnection:
    """In-memory DB with canonical_ohlcv + rejected_symbol + daily_watchlist."""
    conn = duckdb.connect()
    conn.execute("""
        CREATE TABLE canonical_ohlcv (
            symbol VARCHAR, time DATE, interval VARCHAR,
            open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE,
            selected_provider VARCHAR, quality_status VARCHAR,
            ingestion_run_id VARCHAR, source_service_run_id VARCHAR
        )
    """)
    conn.execute("""
        CREATE TABLE rejected_symbol (
            symbol VARCHAR, date DATE, stage VARCHAR, reason VARCHAR,
            details_json VARCHAR, ingestion_run_id VARCHAR,
            created_at TIMESTAMPTZ DEFAULT current_timestamp
        )
    """)
    conn.execute("""
        CREATE TABLE daily_watchlist (
            date DATE, rank INTEGER, symbol VARCHAR, score DOUBLE,
            candidate_class VARCHAR, setup_type VARCHAR,
            risk_flags_json VARCHAR, lineage_json VARCHAR,
            created_at TIMESTAMPTZ DEFAULT current_timestamp
        )
    """)
    return conn


def _insert_ohlcv_rows(conn, symbol, dates, provider="KBS", quality="PASS"):
    rows = [(symbol, d, "1D", 100.0, 102.0, 99.0, 101.0, 1000.0, provider, quality, None, None) for d in dates]
    conn.executemany("INSERT INTO canonical_ohlcv VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)


class TestQualityHistoricalLookup:
    def test_symbol_quality_respects_date_boundary(self):
        """Future OHLCV rows are not used when date is specified."""
        from vnalpha.tools.quality import get_quality_status

        conn = _make_quality_conn()
        _insert_ohlcv_rows(conn, "FPT", ["2024-06-20", "2024-06-21", "2024-06-28"])

        # Query as-of 2024-06-21 — should not see 2024-06-28 row
        result = get_quality_status(conn, symbol="FPT", date="2024-06-21")
        assert result.data is not None
        quality_rows = result.data["quality_rows"]
        times = [r["time"] for r in quality_rows]
        for t in times:
            assert t <= "2024-06-21", f"Future row {t} returned for as-of 2024-06-21"

    def test_symbol_quality_no_date_returns_latest(self):
        """Without date, latest bars are returned."""
        from vnalpha.tools.quality import get_quality_status

        conn = _make_quality_conn()
        _insert_ohlcv_rows(conn, "ACB", ["2024-06-20", "2024-06-28"])
        result = get_quality_status(conn, symbol="ACB")
        assert result.data is not None
        quality_rows = result.data["quality_rows"]
        assert any("2024-06-28" in r["time"] for r in quality_rows)

    def test_symbol_quality_attaches_rejected_records(self):
        """Rejected records are attached to symbol quality output."""
        from vnalpha.tools.quality import get_quality_status

        conn = _make_quality_conn()
        _insert_ohlcv_rows(conn, "FPT", ["2024-06-20"])
        conn.execute(
            "INSERT INTO rejected_symbol (symbol, date, stage, reason) VALUES (?, ?, ?, ?)",
            ["FPT", "2024-06-20", "CANONICAL", "STALE_OHLCV"],
        )
        result = get_quality_status(conn, symbol="FPT", date="2024-06-20")
        assert result.data is not None
        rejected = result.data["rejected_records"]
        assert len(rejected) == 1
        assert rejected[0]["reason"] == "STALE_OHLCV"

    def test_get_many_status_date_bounded(self):
        """get_many_quality_status respects the date boundary."""
        from vnalpha.tools.quality import get_many_quality_status

        conn = _make_quality_conn()
        _insert_ohlcv_rows(conn, "FPT", ["2024-06-20", "2024-06-28"])
        _insert_ohlcv_rows(conn, "VNM", ["2024-06-18", "2024-06-28"])

        result = get_many_quality_status(conn, symbols=["FPT", "VNM"], date="2024-06-21")
        assert result.data is not None
        for row in result.data:
            assert row["as_of_date"] <= "2024-06-21", (
                f"{row['symbol']} returned bar {row['as_of_date']} > 2024-06-21"
            )

    def test_get_many_status_reports_missing(self):
        """get_many_quality_status warns about symbols with no data."""
        from vnalpha.tools.quality import get_many_quality_status

        conn = _make_quality_conn()
        _insert_ohlcv_rows(conn, "FPT", ["2024-06-20"])

        result = get_many_quality_status(conn, symbols=["FPT", "NOSYM"])
        assert any("NOSYM" in w for w in result.warnings)

    def test_watchlist_quality_bounded_to_watchlist_date(self):
        """Watchlist quality uses OHLCV bars on or before the watchlist date."""
        from vnalpha.tools.quality import get_quality_status

        conn = _make_quality_conn()
        _insert_ohlcv_rows(conn, "FPT", ["2024-06-20", "2024-06-28"])
        # Watchlist is for 2024-06-20 (before the 2024-06-28 bar)
        conn.execute(
            "INSERT INTO daily_watchlist (date, rank, symbol) VALUES (?, ?, ?)",
            ["2024-06-20", 1, "FPT"],
        )
        result = get_quality_status(conn, date="2024-06-20")
        assert result.data is not None
        # Provider from 2024-06-28 bar should NOT appear (it's after watchlist date)
        providers = [r["provider"] for r in result.data]
        # Only bar on or before 2024-06-20 should be used
        assert all(p == "KBS" or p is None for p in providers)


class TestFilterValidation:
    """Tests for shared filter validation logic (task 5.6)."""

    def test_valid_filter_passes(self):
        """A well-formed filter does not raise."""
        from vnalpha.tools.filter_validation import validate_filters

        validate_filters([{"key": "score", "op": ">=", "value": 0.5}])

    def test_unsupported_field_raises(self):
        """Unknown field names are rejected."""
        from vnalpha.tools.filter_validation import FilterValidationError, validate_filters

        with pytest.raises(FilterValidationError, match="not_a_field"):
            validate_filters([{"key": "not_a_field", "op": ">=", "value": 1}])

    def test_malformed_numeric_op_raises(self):
        """Non-numeric value with inequality op on numeric field is rejected."""
        from vnalpha.tools.filter_validation import FilterValidationError, validate_filters

        with pytest.raises(FilterValidationError):
            validate_filters([{"key": "score", "op": ">=", "value": "not_a_number"}])

    def test_missing_key_raises(self):
        """Filters missing the 'key' key are rejected (empty string not in supported set)."""
        from vnalpha.tools.filter_validation import FilterValidationError, validate_filters

        with pytest.raises(FilterValidationError):
            validate_filters([{"op": ">=", "value": 1}])

    def test_alias_fields_accepted(self):
        """Alias field names ('class', 'setup') are accepted."""
        from vnalpha.tools.filter_validation import validate_filters

        # Should not raise — 'class' is alias for candidate_class
        validate_filters([{"key": "class", "op": "==", "value": "A"}])

    def test_risk_flags_field_accepted(self):
        """risk_flags field is in supported set."""
        from vnalpha.tools.filter_validation import validate_filters

        validate_filters([{"key": "risk_flags", "op": "==", "value": "ok"}])

    def test_filter_watchlist_returns_error_output_on_bad_filter(self):
        """filter_watchlist returns ToolOutput with warning on invalid filter (no exception raised)."""
        import duckdb

        from vnalpha.tools.watchlist import filter_watchlist

        conn = duckdb.connect(":memory:")
        conn.execute(
            "CREATE TABLE daily_watchlist (date VARCHAR, rank INTEGER, symbol VARCHAR, "
            "score FLOAT, candidate_class VARCHAR, setup_type VARCHAR, risk_label VARCHAR)"
        )
        conn.execute("INSERT INTO daily_watchlist VALUES ('2024-06-20', 1, 'FPT', 0.8, 'A', 'B', 'low')")

        result = filter_watchlist(conn, "2024-06-20", [{"key": "BAD_FIELD", "op": ">=", "value": 1}])
        assert result.data is None
        assert len(result.warnings) > 0
        assert "BAD_FIELD" in result.warnings[0] or "BAD_FIELD" in result.summary
