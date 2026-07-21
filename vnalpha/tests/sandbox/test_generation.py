from __future__ import annotations

from vnalpha.sandbox.generation import (
    generate_numeric_research_program,
)


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
