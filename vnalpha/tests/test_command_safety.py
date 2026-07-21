"""Safety and product boundary tests for Phase 5.8 command layer (Tasks 8.1-8.5)."""

from __future__ import annotations

import ast
from pathlib import Path

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
