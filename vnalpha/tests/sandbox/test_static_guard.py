from __future__ import annotations


def _evaluate(code: str):
    from vnalpha.sandbox.static_guard import SandboxStaticGuard

    return SandboxStaticGuard.evaluate(code)


def _rules(code: str) -> set[str]:
    return {violation.rule.value for violation in _evaluate(code).violations}


def test_allows_safe_statement_based_scientific_module() -> None:
    # Given
    code = "import math\nimport pandas as pd\nvalue = math.sqrt(9)\n"

    # When
    result = _evaluate(code)

    # Then
    assert result.allowed
    assert not result.violations
