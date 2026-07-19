"""Stateless expression allowlist for sandbox static safety evidence."""

from __future__ import annotations

import ast
import math
from typing import Final, final, override

from vnalpha.sandbox._static_guard_models import SandboxGuardRule, SandboxGuardViolation

_MAX_NODES: Final = 256
_MATH_INTRINSICS: Final = frozenset(
    {
        "acos",
        "asin",
        "atan",
        "ceil",
        "cos",
        "exp",
        "floor",
        "log",
        "sin",
        "sqrt",
        "tan",
    }
)
_UNARY_OPERATORS: Final = (ast.UAdd, ast.USub)
_BINARY_OPERATORS: Final = (
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
)


@final
class SandboxGuardAstVisitor(ast.NodeVisitor):
    """Accept only finite numeric expressions and direct math intrinsic calls."""

    def __init__(self) -> None:
        self.violations: list[SandboxGuardViolation] = []
        self._node_count: int = 0
        self._complexity_exceeded: bool = False

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
    def generic_visit(self, node: ast.AST) -> None:
        self._add(SandboxGuardRule.UNSUPPORTED_AST, node)

    @override
    def visit_Expression(self, node: ast.Expression) -> None:
        self.visit(node.body)

    @override
    def visit_Constant(self, node: ast.Constant) -> None:
        value = node.value
        is_finite_number = (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
        )
        if not is_finite_number:
            self._add(SandboxGuardRule.UNSUPPORTED_AST, node)

    @override
    def visit_UnaryOp(self, node: ast.UnaryOp) -> None:
        if not isinstance(node.op, _UNARY_OPERATORS):
            self._add(SandboxGuardRule.UNSUPPORTED_AST, node)
            return
        self.visit(node.operand)

    @override
    def visit_BinOp(self, node: ast.BinOp) -> None:
        if not isinstance(node.op, _BINARY_OPERATORS):
            self._add(SandboxGuardRule.UNSUPPORTED_AST, node)
            return
        self.visit(node.left)
        self.visit(node.right)

    @override
    def visit_Call(self, node: ast.Call) -> None:
        match node.func:
            case ast.Name(id=name) if name in _MATH_INTRINSICS and not node.keywords:
                for argument in node.args:
                    self.visit(argument)
            case _:
                self._add(SandboxGuardRule.UNSUPPORTED_AST, node)

    def _add(self, rule: SandboxGuardRule, node: ast.AST) -> None:
        self.violations.append(
            SandboxGuardViolation(
                rule=rule,
                node_type=type(node).__name__,
                line=getattr(node, "lineno", 0),
                column=getattr(node, "col_offset", 0),
            )
        )
