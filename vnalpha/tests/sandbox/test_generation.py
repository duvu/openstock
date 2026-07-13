from __future__ import annotations

import math

import pytest

from vnalpha.sandbox.execution_service import SandboxGeneratedProgram
from vnalpha.sandbox.execution_types import SandboxGeneratedProgram as ExtractedProgram
from vnalpha.sandbox.generation import (
    SandboxPurposeUnsupportedError,
    generate_numeric_research_program,
    parse_numeric_research_purpose,
)


@pytest.mark.parametrize(
    ("purpose", "expected"),
    (
        ("mean of 1, 2, 3", 2.0),
        ("median of 1, 9, 3", 3.0),
        ("sum of 1, 2, 3", 6.0),
        ("minimum of -2, 4, 8", -2.0),
        ("maximum of -2, 4, 8", 8.0),
        ("range of -2, 4, 8", 10.0),
        ("population standard deviation of 1, 2, 3", math.sqrt(2 / 3)),
    ),
)
def test_numeric_research_purpose_calculates_supported_statistic(
    purpose: str, expected: float
) -> None:
    # Given: a bounded purpose in the supported numeric-research grammar
    specification = parse_numeric_research_purpose(purpose)

    # When: its deterministic result is calculated
    result = specification.calculate()

    # Then: the requested statistic is computed from the supplied literals
    assert result == pytest.approx(expected)


def test_generated_program_depends_on_approved_numeric_literals() -> None:
    # Given: two supported purposes with different approved values
    first = generate_numeric_research_program("mean of 1, 2, 3")
    second = generate_numeric_research_program("mean of 10, 20, 30")

    # When: their generated programs are compared
    # Then: both the source and described result depend on the input values
    assert first.code != second.code
    assert "VALUES = [1.0, 2.0, 3.0]" in first.code
    assert "VALUES = [10.0, 20.0, 30.0]" in second.code
    assert "2" in first.summary
    assert "20" in second.summary


@pytest.mark.parametrize(
    "purpose",
    (
        "compare persisted datasets",
        "calculate something useful",
        "mean",
        "mean of nan, 1",
        "mean of inf, 1",
        "mean and median of 1, 2, 3",
        "mean of " + ", ".join("1" for _ in range(1_001)),
    ),
)
def test_unsupported_or_unbounded_purpose_fails_closed(purpose: str) -> None:
    # Given: prose outside the closed numeric-research grammar
    # When / Then: generation rejects it instead of claiming completion
    with pytest.raises(SandboxPurposeUnsupportedError):
        _ = generate_numeric_research_program(purpose)


def test_execution_service_preserves_program_type_import_compatibility() -> None:
    # Given / When: callers import the DTO through either supported module
    # Then: both paths identify the same immutable type
    assert SandboxGeneratedProgram is ExtractedProgram
