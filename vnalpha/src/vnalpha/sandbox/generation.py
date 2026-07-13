from __future__ import annotations

import json
import math
import re
import statistics
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, assert_never

from vnalpha.sandbox.execution_types import SandboxGeneratedProgram

_MAX_LITERAL_COUNT: Final = 1_000
_MAX_ABSOLUTE_VALUE: Final = 1e100
_NUMBER_PATTERN: Final = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
_PURPOSE_PATTERN: Final = re.compile(
    r"(?P<statistic>population standard deviation|standard deviation|pstdev|"
    r"mean|average|median|sum|minimum|min|maximum|max|range)\s+of\s+"
    r"(?P<values>.+)",
    re.IGNORECASE,
)


class NumericStatistic(StrEnum):
    MEAN = "mean"
    MEDIAN = "median"
    SUM = "sum"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"
    RANGE = "range"
    POPULATION_STANDARD_DEVIATION = "population_standard_deviation"


@dataclass(frozen=True, slots=True)
class NumericResearchSpecification:
    statistic: NumericStatistic
    values: tuple[float, ...]

    def calculate(self) -> float:
        match self.statistic:
            case NumericStatistic.MEAN:
                result = statistics.fmean(self.values)
            case NumericStatistic.MEDIAN:
                result = statistics.median(self.values)
            case NumericStatistic.SUM:
                result = math.fsum(self.values)
            case NumericStatistic.MINIMUM:
                result = min(self.values)
            case NumericStatistic.MAXIMUM:
                result = max(self.values)
            case NumericStatistic.RANGE:
                result = max(self.values) - min(self.values)
            case NumericStatistic.POPULATION_STANDARD_DEVIATION:
                result = statistics.pstdev(self.values)
            case unreachable:
                assert_never(unreachable)
        if not math.isfinite(result):
            raise SandboxPurposeUnsupportedError("numeric result is not finite")
        return result


class SandboxPurposeUnsupportedError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self._reason = reason

    def __str__(self) -> str:
        return self._reason


def parse_numeric_research_purpose(purpose: str) -> NumericResearchSpecification:
    match = _PURPOSE_PATTERN.fullmatch(purpose.strip())
    if match is None:
        raise SandboxPurposeUnsupportedError(f"unsupported sandbox purpose: {purpose}")
    raw_values = tuple(part.strip() for part in match.group("values").split(","))
    if not raw_values or len(raw_values) > _MAX_LITERAL_COUNT:
        raise SandboxPurposeUnsupportedError("numeric literal count is outside bounds")
    values: list[float] = []
    for raw_value in raw_values:
        if _NUMBER_PATTERN.fullmatch(raw_value) is None:
            raise SandboxPurposeUnsupportedError(
                f"unsupported numeric literal: {raw_value}"
            )
        value = float(raw_value)
        if not math.isfinite(value) or abs(value) > _MAX_ABSOLUTE_VALUE:
            raise SandboxPurposeUnsupportedError(
                f"numeric literal is outside bounds: {raw_value}"
            )
        values.append(value)
    return NumericResearchSpecification(
        statistic=_parse_statistic(match.group("statistic")), values=tuple(values)
    )


def generate_numeric_research_program(purpose: str) -> SandboxGeneratedProgram:
    specification = parse_numeric_research_purpose(purpose)
    result = specification.calculate()
    expression = _runtime_expression(specification.statistic)
    values_literal = repr(list(specification.values))
    purpose_literal = json.dumps(purpose, ensure_ascii=False)
    statistic_literal = json.dumps(specification.statistic.value)
    code = "\n".join(
        (
            "import json",
            "import statistics",
            "",
            f"PURPOSE = {purpose_literal}",
            f"STATISTIC = {statistic_literal}",
            f"VALUES = {values_literal}",
            f"RESULT = {expression}",
            'SUMMARY = f"{STATISTIC} of {len(VALUES)} approved values: {RESULT:.12g}"',
            "",
            'with open("output/result.json", "w", encoding="utf-8") as handle:',
            '    json.dump({"schema_version": 1, "summary": SUMMARY, "artifacts": [], "purpose": PURPOSE, "statistic": STATISTIC, "value_count": len(VALUES), "result": RESULT}, handle, ensure_ascii=0)',
            '    handle.write("\\n")',
            "",
            'with open("output/summary.md", "w", encoding="utf-8") as handle:',
            '    handle.write("# Sandbox Numeric Research Result\\n\\n")',
            '    handle.write(f"{SUMMARY}\\n")',
        )
    )
    return SandboxGeneratedProgram(
        code=code,
        summary=(
            f"Computes {specification.statistic.value} from "
            f"{len(specification.values)} approved numeric literals; expected result "
            f"{result:.12g}."
        ),
    )


def _parse_statistic(raw: str) -> NumericStatistic:
    normalized = raw.lower()
    aliases = {
        "average": NumericStatistic.MEAN,
        "max": NumericStatistic.MAXIMUM,
        "min": NumericStatistic.MINIMUM,
        "population standard deviation": NumericStatistic.POPULATION_STANDARD_DEVIATION,
        "pstdev": NumericStatistic.POPULATION_STANDARD_DEVIATION,
        "standard deviation": NumericStatistic.POPULATION_STANDARD_DEVIATION,
    }
    return (
        aliases[normalized] if normalized in aliases else NumericStatistic(normalized)
    )


def _runtime_expression(statistic: NumericStatistic) -> str:
    match statistic:
        case NumericStatistic.MEAN:
            return "statistics.fmean(VALUES)"
        case NumericStatistic.MEDIAN:
            return "statistics.median(VALUES)"
        case NumericStatistic.SUM:
            return "sum(VALUES)"
        case NumericStatistic.MINIMUM:
            return "min(VALUES)"
        case NumericStatistic.MAXIMUM:
            return "max(VALUES)"
        case NumericStatistic.RANGE:
            return "max(VALUES) - min(VALUES)"
        case NumericStatistic.POPULATION_STANDARD_DEVIATION:
            return "statistics.pstdev(VALUES)"
        case unreachable:
            assert_never(unreachable)
