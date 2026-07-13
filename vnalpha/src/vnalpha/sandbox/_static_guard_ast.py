"""Policy-focused AST inspection for generated sandbox Python modules."""

from __future__ import annotations

import ast
from typing import Final, final

from typing_extensions import override

from vnalpha.policy.safety_policy import FORBIDDEN_TOOL_PREFIXES
from vnalpha.sandbox._static_guard_models import SandboxGuardRule, SandboxGuardViolation

_MAX_NODES: Final = 256
_ALLOWED_IMPORT_ROOTS: Final = frozenset(
    {
        "math",
        "statistics",
        "json",
        "csv",
        "datetime",
        "collections",
        "numpy",
        "pandas",
        "matplotlib",
    }
)
_NETWORK_IMPORT_ROOTS: Final = frozenset(
    {"requests", "httpx", "urllib", "socket", "http", "ftplib", "websocket"}
)
_SHELL_IMPORT_ROOTS: Final = frozenset({"os", "subprocess", "shutil"})
_DYNAMIC_NAMES: Final = frozenset(
    {"eval", "exec", "compile", "__import__", "globals", "locals"}
)


@final
class SandboxGuardAstVisitor(ast.NodeVisitor):
    """Reject unsafe capabilities while Docker remains the execution boundary."""

    def __init__(self) -> None:
        self.violations: list[SandboxGuardViolation] = []
        self._node_count = 0
        self._complexity_exceeded = False

    @override
    def visit(self, node: ast.AST) -> None:
        if self._complexity_exceeded:
            return
        self._node_count += 1
        if self._node_count > _MAX_NODES:
            self._complexity_exceeded = True
            self._add(SandboxGuardRule.COMPLEXITY_LIMIT, node)
            return
        super().visit(node)

    @override
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._check_import(alias.name, node)

    @override
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self._check_import(node.module or "", node)

    @override
    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, (bool, complex)):
            self._add(SandboxGuardRule.UNSUPPORTED_AST, node)

    @override
    def visit_Name(self, node: ast.Name) -> None:
        self._check_identifier(node.id, node)

    @override
    def visit_Attribute(self, node: ast.Attribute) -> None:
        self._check_identifier(node.attr, node)
        self.generic_visit(node)

    @override
    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node.func)
        if name in _DYNAMIC_NAMES:
            self._add(SandboxGuardRule.DYNAMIC_REFLECTION, node)
        elif name == "open" and _opens_outside_output(node):
            self._add(SandboxGuardRule.FILESYSTEM_WRITE, node)
        self.generic_visit(node)

    def _check_import(self, module: str, node: ast.AST) -> None:
        root = module.split(".", 1)[0]
        if root in _NETWORK_IMPORT_ROOTS:
            self._add(SandboxGuardRule.NETWORK, node)
        elif root in _SHELL_IMPORT_ROOTS:
            self._add(SandboxGuardRule.SHELL_PROCESS, node)
        elif root not in _ALLOWED_IMPORT_ROOTS:
            self._add(SandboxGuardRule.UNSUPPORTED_AST, node)

    def _check_identifier(self, identifier: str, node: ast.AST) -> None:
        normalized = identifier.lower()
        if normalized in _DYNAMIC_NAMES:
            self._add(SandboxGuardRule.DYNAMIC_REFLECTION, node)
        elif any(term in normalized for term in FORBIDDEN_TOOL_PREFIXES):
            self._add(SandboxGuardRule.TRADING_BOUNDARY, node)
        elif normalized in {
            "system",
            "popen",
            "run",
            "call",
            "check_call",
            "check_output",
        }:
            self._add(SandboxGuardRule.SHELL_PROCESS, node)

    def _add(self, rule: SandboxGuardRule, node: ast.AST) -> None:
        self.violations.append(
            SandboxGuardViolation(
                rule=rule,
                node_type=type(node).__name__,
                line=getattr(node, "lineno", 0),
                column=getattr(node, "col_offset", 0),
            )
        )


def _call_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id.lower()
    if isinstance(node, ast.Attribute):
        return node.attr.lower()
    return ""


def _opens_outside_output(node: ast.Call) -> bool:
    if len(node.args) < 2 or not isinstance(node.args[1], ast.Constant):
        return False
    mode = node.args[1].value
    if not isinstance(mode, str) or not any(flag in mode for flag in "wax+"):
        return False
    if not node.args or not isinstance(node.args[0], ast.Constant):
        return True
    path = node.args[0].value
    return not isinstance(path, str) or not path.startswith("output/")
