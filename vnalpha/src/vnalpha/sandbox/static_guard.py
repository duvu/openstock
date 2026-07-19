"""Deterministic, non-executing static safety evidence for sandbox code."""

from __future__ import annotations

import ast
from hashlib import sha256
from typing import Final, final

from vnalpha.sandbox._static_guard_models import (
    SandboxGuardResult,
    SandboxGuardRule,
    SandboxGuardViolation,
)

__all__ = [
    "SandboxGuardResult",
    "SandboxGuardRule",
    "SandboxGuardViolation",
    "SandboxStaticGuard",
]
_SCHEMA_VERSION: Final = 1


@final
class SandboxStaticGuard:
    """Assess generated Python with AST parsing and compilation only, never execution."""

    @staticmethod
    def evaluate(code: str) -> SandboxGuardResult:
        """Return deterministic allow or deny evidence for UTF-8 source text."""

        try:
            digest = sha256(code.encode("utf-8")).hexdigest()
        except UnicodeEncodeError:
            digest = sha256(code.encode("utf-8", errors="surrogatepass")).hexdigest()
            return _denied(digest, SandboxGuardRule.ANALYSIS_FAILURE, "Module")
        try:
            tree = ast.parse(code, mode="eval")
            _ = compile(tree, "<sandbox-static-guard>", "eval")
        except (
            MemoryError,
            OverflowError,
            RecursionError,
            SyntaxError,
            TypeError,
            ValueError,
        ):
            return _denied(digest, SandboxGuardRule.PARSE_COMPILE, "Module")
        from vnalpha.sandbox._static_guard_ast import SandboxGuardAstVisitor

        visitor = SandboxGuardAstVisitor()
        try:
            visitor.visit(tree)
        except (OverflowError, RecursionError):
            return _denied(digest, SandboxGuardRule.ANALYSIS_FAILURE, "Module")
        violations = tuple(sorted(set(visitor.violations)))
        return SandboxGuardResult(
            schema_version=_SCHEMA_VERSION,
            code_digest=digest,
            allowed=not violations,
            violations=violations,
        )


def _denied(digest: str, rule: SandboxGuardRule, node_type: str) -> SandboxGuardResult:
    violation = SandboxGuardViolation(rule, node_type, 0, 0)
    return SandboxGuardResult(_SCHEMA_VERSION, digest, False, (violation,))
