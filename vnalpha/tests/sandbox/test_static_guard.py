from __future__ import annotations

import hashlib

import pytest


def _evaluate(code: str):
    from vnalpha.sandbox.static_guard import SandboxStaticGuard

    return SandboxStaticGuard.evaluate(code)


def _rules(code: str) -> set[str]:
    return {violation.rule.value for violation in _evaluate(code).violations}


@pytest.mark.parametrize(
    "code",
    [
        "1",
        "-1.5 + 2 * 3",
        "sqrt(9)",
        "sin(1) + floor(2.2) - log(8, 2)",
    ],
)
def test_allows_finite_numeric_math_expressions(code: str) -> None:
    # Given / When
    result = _evaluate(code)

    # Then
    assert result.allowed
    assert not result.violations


def test_allows_safe_statement_based_scientific_module() -> None:
    # Given
    code = "import math\nimport pandas as pd\nvalue = math.sqrt(9)\n"

    # When
    result = _evaluate(code)

    # Then
    assert result.allowed
    assert not result.violations


@pytest.mark.parametrize(
    ("code", "rule"),
    [
        ("import requests", "network"),
        ("import subprocess", "shell_process"),
        ("open('outside.txt', 'w')", "filesystem_write"),
        ("open('outside.txt', mode='w')", "filesystem_write"),
        ("open('output/../../outside.txt', 'w')", "filesystem_write"),
        ("open('output/../outside.txt', mode='a')", "filesystem_write"),
        ("eval('1')", "dynamic_reflection"),
        ("place_order()", "trading_boundary"),
    ],
)
def test_rejects_denied_module_patterns(code: str, rule: str) -> None:
    # Given / When
    result = _evaluate(code)

    # Then
    assert not result.allowed
    assert rule in _rules(code)


@pytest.mark.parametrize("code", ["True", "1j"])
def test_rejects_non_finite_or_unsupported_numeric_forms(code: str) -> None:
    # Given / When
    result = _evaluate(code)

    # Then
    assert not result.allowed
    assert "unsupported_ast" in _rules(code)


def test_binds_deterministic_redacted_evidence_to_the_code_digest() -> None:
    # Given
    code = "eval('do-not-persist-this-literal')"

    # When
    first = _evaluate(code)
    second = _evaluate(code)
    evidence = first.to_json_bytes().decode("utf-8")

    # Then
    assert first == second
    assert first.code_digest == hashlib.sha256(code.encode("utf-8")).hexdigest()
    assert first.to_json_bytes().endswith(b"\n")
    assert "do-not-persist-this-literal" not in evidence
    assert "Traceback" not in evidence


def test_denies_expression_exceeding_the_static_complexity_limit() -> None:
    # Given
    code = " + ".join("1" for _ in range(300))

    # When
    result = _evaluate(code)

    # Then
    assert not result.allowed
    assert "complexity_limit" in _rules(code)


def test_denies_huge_hexadecimal_literal_as_an_analysis_failure() -> None:
    # Given
    code = "0x" + "f" * 10_000

    # When
    result = _evaluate(code)

    # Then
    assert not result.allowed
    assert "analysis_failure" in _rules(code)


def test_denies_unpaired_surrogate_with_deterministic_redacted_evidence() -> None:
    # Given
    code = "\ud800"

    # When
    first = _evaluate(code)
    second = _evaluate(code)

    # Then
    assert first == second
    assert not first.allowed
    assert "analysis_failure" in _rules(code)
    assert "\\ud800" not in first.to_json_bytes().decode("utf-8")


def test_denies_deeply_nested_expression_as_a_parse_compile_failure() -> None:
    # Given
    code = "-" * 10_000 + "1"

    # When
    result = _evaluate(code)

    # Then
    assert not result.allowed
    assert "parse_compile" in _rules(code)


def test_limits_large_intrinsic_call_to_one_bounded_complexity_violation() -> None:
    # Given
    code = "sqrt(" + ",".join("1" for _ in range(1_000)) + ")"

    # When
    result = _evaluate(code)

    # Then
    limit_violations = [
        violation
        for violation in result.violations
        if violation.rule.value == "complexity_limit"
    ]
    assert not result.allowed
    assert len(limit_violations) == 1
    assert len(result.to_json_bytes()) < 500
