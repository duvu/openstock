"""Typed errors raised while loading evaluation fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class GoldenCaseLoadError(Exception):
    """Base error for a golden-case fixture that cannot be loaded."""

    path: Path
    detail: str

    def __str__(self) -> str:
        return f"Golden case fixture {self.path}: {self.detail}"


@dataclass(frozen=True, slots=True)
class GoldenCaseYamlSyntaxError(GoldenCaseLoadError):
    """Raised when YAML syntax prevents loading a fixture."""


@dataclass(frozen=True, slots=True)
class GoldenCaseValidationError(GoldenCaseLoadError):
    """Raised when a fixture does not meet its typed schema."""


@dataclass(frozen=True, slots=True)
class DuplicateGoldenCaseIdError(GoldenCaseLoadError):
    """Raised when fixture documents reuse a case identifier."""

    case_id: str
    first_path: Path

    def __str__(self) -> str:
        return (
            f"Golden case fixture {self.path}: duplicate case_id {self.case_id!r}; "
            f"first declared in {self.first_path}"
        )
