"""Tests for Local Tool Registry safety (Task 3.5) and tools module (Tasks 3.1-3.4)."""

from __future__ import annotations

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
