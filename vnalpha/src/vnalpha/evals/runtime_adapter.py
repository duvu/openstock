from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from unittest.mock import patch

import duckdb

from vnalpha.assistant.models import ToolPlanStep
from vnalpha.evals.runtime_models import JsonValue, RuntimeReplayCase, SeededToolOutput
from vnalpha.tools.models import ToolOutput, ToolSpec
from vnalpha.tools.registry import LocalToolRegistry
from vnalpha.tools.setup import TOOL_PERMISSIONS


@dataclass(frozen=True, slots=True)
class SeededToolArgumentsError(RuntimeError):
    tool_name: str
    expected: dict[str, JsonValue]
    actual: dict[str, JsonValue]

    def __str__(self) -> str:
        return (
            f"seeded tool {self.tool_name} arguments differ: "
            f"expected={self.expected!r} actual={self.actual!r}"
        )


def build_seeded_tool_registry(case: RuntimeReplayCase) -> LocalToolRegistry:
    registry = LocalToolRegistry()
    for seed in case.tool_outputs:
        registry.register(
            ToolSpec(
                name=seed.tool_name,
                description=f"Runtime replay seed for {seed.tool_name}",
                permission=TOOL_PERMISSIONS[seed.tool_name],
            ),
            _seeded_implementation(seed),
        )
    return registry


def _seeded_implementation(seed: SeededToolOutput):
    def execute(**arguments: JsonValue) -> ToolOutput:
        if arguments != seed.arguments:
            raise SeededToolArgumentsError(
                tool_name=seed.tool_name,
                expected=seed.arguments,
                actual=arguments,
            )
        data = dict(seed.data)
        data["artifact_refs"] = list(seed.artifact_refs)
        return ToolOutput(
            data=data,
            summary=seed.summary,
            warnings=list(seed.warnings),
        )

    return execute


def _skip_data_ensure(
    _conn: duckdb.DuckDBPyConnection, _step: ToolPlanStep
) -> None:
    return None


@contextmanager
def seeded_assistant_executor(case: RuntimeReplayCase) -> Iterator[None]:
    from vnalpha.assistant import executor as executor_module

    registry = build_seeded_tool_registry(case)

    def build_registry(_conn: duckdb.DuckDBPyConnection) -> LocalToolRegistry:
        return registry

    with (
        patch.object(executor_module, "_build_tool_registry", build_registry),
        patch.object(executor_module, "_ensure_data_for_step", _skip_data_ensure),
    ):
        yield
