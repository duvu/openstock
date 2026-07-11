"""YAML loader for typed local golden-case fixtures."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import yaml
from pydantic import TypeAdapter, ValidationError

from vnalpha.evals.errors import (
    DuplicateGoldenCaseIdError,
    GoldenCaseLoadError,
    GoldenCaseValidationError,
    GoldenCaseYamlSyntaxError,
)
from vnalpha.evals.models import GoldenCase

_CASE_ADAPTER = TypeAdapter(GoldenCase)


def load_golden_cases(paths: Sequence[Path]) -> tuple[GoldenCase, ...]:
    """Load one strict golden case from every YAML fixture path."""

    cases: list[GoldenCase] = []
    case_paths: dict[str, Path] = {}
    for path in paths:
        case = load_golden_case(path)
        first_path = case_paths.get(case.case_id)
        if first_path is not None:
            raise DuplicateGoldenCaseIdError(
                path=path,
                detail="case identifiers must be unique",
                case_id=case.case_id,
                first_path=first_path,
            )
        case_paths[case.case_id] = path
        cases.append(case)
    return tuple(cases)


def load_golden_case(path: Path) -> GoldenCase:
    """Load one strict golden case from one YAML fixture path."""

    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise GoldenCaseYamlSyntaxError(path=path, detail=str(error)) from error
    except (OSError, UnicodeError) as error:
        raise GoldenCaseLoadError(path=path, detail=str(error)) from error

    if document is None:
        raise GoldenCaseValidationError(path=path, detail="document is empty")

    try:
        return _CASE_ADAPTER.validate_python(document)
    except ValidationError as error:
        raise GoldenCaseValidationError(path=path, detail=str(error)) from error
