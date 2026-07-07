"""Safety and product boundary tests for Phase 5.8 command layer (Tasks 8.1-8.5)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

COMMANDS_DIR = Path(__file__).parent.parent / "src" / "vnalpha" / "commands"
TOOLS_DIR = Path(__file__).parent.parent / "src" / "vnalpha" / "tools"

FORBIDDEN_WORDS = [
    "order",
    "portfolio",
    "broker",
    "account",
    "trade",
    "buy",
    "sell",
    "position",
    "recommendation",
    "signal",
]

# Words that are clearly trading execution (not just research labels)
TRADING_EXECUTION_TERMS = [
    "place_order",
    "execute_trade",
    "broker_connect",
    "account_balance",
    "portfolio_value",
    "open_position",
    "close_position",
]


def _get_python_files(directory: Path) -> list[Path]:
    return [f for f in directory.rglob("*.py") if not f.name.startswith("_")]


class TestNoBrokerBehavior:
    """8.1: Command handlers must not include broker/order/account/portfolio behavior."""

    def test_no_broker_imports_in_handlers(self):
        for py_file in _get_python_files(COMMANDS_DIR / "handlers"):
            source = py_file.read_text()
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        base = alias.name.split(".")[0]
                        assert base not in {
                            "broker",
                            "orders",
                            "account",
                            "vntrader",
                        }, f"{py_file.name} imports broker module '{alias.name}'"

    def test_no_trading_execution_functions_in_handlers(self):
        for py_file in _get_python_files(COMMANDS_DIR / "handlers"):
            source = py_file.read_text().lower()
            for term in TRADING_EXECUTION_TERMS:
                assert term not in source, (
                    f"{py_file.name} contains trading execution term '{term}'"
                )

    def test_no_trading_execution_in_tools(self):
        for py_file in _get_python_files(TOOLS_DIR):
            source = py_file.read_text().lower()
            for term in TRADING_EXECUTION_TERMS:
                assert term not in source, (
                    f"{py_file.name} contains trading execution term '{term}'"
                )


class TestNoRecommendationLanguage:
    """8.2: Command outputs must avoid buy/sell/recommendation language."""

    def test_command_handler_result_strings_no_buy_sell(self):
        """Handler source code must not contain buy/sell recommendation strings."""
        forbidden_strings = ['"buy"', "'buy'", '"sell"', "'sell'", '"recommendation"']
        for py_file in _get_python_files(COMMANDS_DIR / "handlers"):
            source = py_file.read_text()
            for s in forbidden_strings:
                assert s not in source, f"{py_file.name} contains '{s}'"

    def test_scan_result_no_recommendation_language(self):
        """The /scan command description/title must not say 'buy/sell/recommend'."""
        from vnalpha.commands.setup import build_default_registry

        reg = build_default_registry()
        scan_meta = reg.get("scan")
        for forbidden in ["buy", "sell", "recommend", "order"]:
            assert forbidden not in scan_meta.description.lower()
            assert forbidden not in scan_meta.usage.lower()

    def test_explain_result_language(self):
        """The /explain command must use research language (score, evidence, lineage)."""
        from vnalpha.commands.setup import build_default_registry

        reg = build_default_registry()
        explain_meta = reg.get("explain")
        assert (
            "score" in explain_meta.description.lower()
            or "explain" in explain_meta.description.lower()
        )


class TestPermissions:
    """8.3: Phase 5.8 permissions must exclude forbidden capabilities."""

    def test_no_forbidden_permissions_in_registry(self):
        from vnalpha.commands.setup import build_default_registry
        from vnalpha.tools.models import FORBIDDEN_PERMISSIONS

        reg = build_default_registry()
        for meta in reg.all():
            for perm in meta.permissions:
                assert perm not in FORBIDDEN_PERMISSIONS, (
                    f"Command '/{meta.name}' has forbidden permission '{perm}'"
                )

    def test_tool_permission_enum_excludes_forbidden(self):
        from vnalpha.tools.models import FORBIDDEN_PERMISSIONS, ToolPermission

        allowed_vals = {p.value for p in ToolPermission}
        overlap = allowed_vals & FORBIDDEN_PERMISSIONS
        assert overlap == set()


class TestExplainGrounded:
    """8.4: /explain output must be grounded in persisted deterministic artifacts."""

    def test_explain_reads_from_candidate_score(self):
        """Verify explain_candidate calls get_candidate_score (not recompute)."""
        import inspect

        from vnalpha.tools.scoring import explain_candidate

        source = inspect.getsource(explain_candidate)
        assert "get_candidate_score" in source, (
            "explain_candidate must read from get_candidate_score"
        )
        # Must NOT call compute_composite_score
        assert "compute_composite_score" not in source, (
            "explain_candidate must not recompute scores"
        )

    def test_explain_handler_delegates_to_tool(self):
        """Verify explain handler delegates through tool_executor, not direct DB queries."""
        import inspect

        from vnalpha.commands.handlers.explain import handle_explain

        source = inspect.getsource(handle_explain)
        # Must use tool_executor, not call scoring tools directly
        assert "tool_executor" in source, "explain handler must use tool_executor"
        assert "explain_candidate" not in source, (
            "explain handler must not bypass tool_executor by calling explain_candidate directly"
        )


class TestUnsupportedCommandsFail:
    """8.5: Unsupported commands must fail closed."""

    def test_unknown_command_raises(self):
        from vnalpha.commands.errors import UnknownCommandError
        from vnalpha.commands.parser import parse
        from vnalpha.commands.setup import build_default_registry

        reg = build_default_registry()
        parsed = parse("/ask what should I do today")
        with pytest.raises(UnknownCommandError, match="Unknown command"):
            reg.execute(parsed)

    def test_python_command_fails_closed(self):
        from vnalpha.commands.errors import UnknownCommandError
        from vnalpha.commands.parser import parse
        from vnalpha.commands.setup import build_default_registry

        reg = build_default_registry()
        parsed = parse("/python import os; os.listdir('/')")
        with pytest.raises(UnknownCommandError):
            reg.execute(parsed)

    def test_search_command_fails_closed(self):
        from vnalpha.commands.errors import UnknownCommandError
        from vnalpha.commands.parser import parse
        from vnalpha.commands.setup import build_default_registry

        reg = build_default_registry()
        parsed = parse("/search financial news")
        with pytest.raises(UnknownCommandError):
            reg.execute(parsed)

    def test_fetch_command_fails_closed(self):
        from vnalpha.commands.errors import UnknownCommandError
        from vnalpha.commands.parser import parse
        from vnalpha.commands.setup import build_default_registry

        reg = build_default_registry()
        parsed = parse("/fetch https://example.com")
        with pytest.raises(UnknownCommandError):
            reg.execute(parsed)
