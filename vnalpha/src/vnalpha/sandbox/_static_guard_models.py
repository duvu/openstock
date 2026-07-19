"""Immutable, canonical static-guard evidence values."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import TypedDict, final


class SandboxGuardRule(StrEnum):
    """Stable categories for static sandbox policy violations."""

    PARSE_COMPILE = "parse_compile"
    ANALYSIS_FAILURE = "analysis_failure"
    COMPLEXITY_LIMIT = "complexity_limit"
    UNSUPPORTED_AST = "unsupported_ast"
    SHELL_PROCESS = "shell_process"
    NETWORK = "network"
    DEPENDENCY_INSTALL = "dependency_install"
    ENVIRONMENT_SECRET = "environment_secret"
    DYNAMIC_REFLECTION = "dynamic_reflection"
    FILESYSTEM_WRITE = "filesystem_write"
    TRADING_BOUNDARY = "trading_boundary"


class _ViolationPayload(TypedDict):
    column: int
    line: int
    node_type: str
    rule: str


class _ResultPayload(TypedDict):
    allowed: bool
    code_digest: str
    schema_version: int
    violations: list[_ViolationPayload]


@final
@dataclass(frozen=True, slots=True, order=True)
class SandboxGuardViolation:
    """A redacted, location-only static policy finding."""

    rule: SandboxGuardRule
    node_type: str
    line: int
    column: int

    def to_payload(self) -> _ViolationPayload:
        """Return canonical JSON-compatible violation evidence."""

        return {
            "column": self.column,
            "line": self.line,
            "node_type": self.node_type,
            "rule": self.rule.value,
        }


@final
@dataclass(frozen=True, slots=True)
class SandboxGuardResult:
    """Immutable static safety decision bound to the examined code digest."""

    schema_version: int
    code_digest: str
    allowed: bool
    violations: tuple[SandboxGuardViolation, ...]

    def to_json_bytes(self) -> bytes:
        """Serialize deterministic redacted evidence as canonical UTF-8 JSON."""

        payload: _ResultPayload = {
            "allowed": self.allowed,
            "code_digest": self.code_digest,
            "schema_version": self.schema_version,
            "violations": [violation.to_payload() for violation in self.violations],
        }
        return (
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
