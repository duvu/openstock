from __future__ import annotations

import json
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Final

import duckdb

from vnalpha.assistant.errors import AssistantError
from vnalpha.evals.runtime_loader import load_runtime_replay_case
from vnalpha.evals.runtime_models import RuntimeReplayLoadError
from vnalpha.evals.runtime_report import (
    RuntimeCheckResult,
    RuntimeReplayCaseResult,
    RuntimeReplayReport,
)
from vnalpha.evals.runtime_runner import run_runtime_replay_case

DEFAULT_RUNTIME_CASES_ROOT: Final[Traversable] = resources.files(
    "vnalpha.evals"
).joinpath("runtime_cases")


def run_runtime_replay_corpus(root: Path | None = None) -> RuntimeReplayReport:
    if root is None:
        with resources.as_file(DEFAULT_RUNTIME_CASES_ROOT) as packaged_root:
            return _run_runtime_replay_corpus(packaged_root)
    return _run_runtime_replay_corpus(root)


def _run_runtime_replay_corpus(root: Path) -> RuntimeReplayReport:
    try:
        resolved_root = root.resolve(strict=True)
    except OSError as error:
        return RuntimeReplayReport(
            source_count=0,
            cases=(_operational_failure("corpus", "discovery", str(error)),),
        )
    if root.is_symlink() or not resolved_root.is_dir():
        return RuntimeReplayReport(
            source_count=0,
            cases=(
                _operational_failure(
                    "corpus", "discovery", "unsafe runtime corpus root"
                ),
            ),
        )
    paths = tuple(sorted(root.glob("*.json"), key=lambda path: path.name))
    if not paths:
        return RuntimeReplayReport(
            source_count=0,
            cases=(
                _operational_failure(
                    "corpus", "discovery", "no runtime JSON cases found"
                ),
            ),
        )
    results: list[RuntimeReplayCaseResult] = []
    seen_case_ids: set[str] = set()
    for path in paths:
        if path.is_symlink():
            results.append(
                _operational_failure(path.stem, "discovery", "symlink case")
            )
            continue
        try:
            path.resolve(strict=True).relative_to(resolved_root)
            case = load_runtime_replay_case(path)
            if case.case_id in seen_case_ids:
                results.append(
                    _operational_failure(
                        case.case_id,
                        "duplicate_case_id",
                        f"duplicate runtime case {case.case_id}",
                    )
                )
                continue
            seen_case_ids.add(case.case_id)
            results.append(run_runtime_replay_case(case))
        except (RuntimeReplayLoadError, AssistantError, ValueError, duckdb.Error) as error:
            results.append(_operational_failure(path.stem, "runtime", str(error)))
    return RuntimeReplayReport(source_count=len(paths), cases=tuple(results))


def _operational_failure(
    case_id: str, check_name: str, actual: str
) -> RuntimeReplayCaseResult:
    return RuntimeReplayCaseResult(
        case_id=case_id,
        checks=(
            RuntimeCheckResult(
                name=check_name,
                expected=json.dumps("successful runtime replay"),
                actual=json.dumps(actual),
            ),
        ),
    )
