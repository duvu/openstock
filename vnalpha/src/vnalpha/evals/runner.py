"""Deterministic, offline-only discovery and execution of golden fixtures."""

from __future__ import annotations

from pathlib import Path

from vnalpha.evals.adapter import adapt_observation
from vnalpha.evals.checks import evaluate_case
from vnalpha.evals.contracts import InvalidEvaluationObservationError
from vnalpha.evals.errors import GoldenCaseLoadError
from vnalpha.evals.loader import load_golden_case
from vnalpha.evals.models import GoldenCase
from vnalpha.evals.report import EvaluatedCase, EvaluationRunReport, RunFailure

DEFAULT_GOLDENS_ROOT = Path(__file__).resolve().parents[3] / "evals" / "goldens"
_FAMILY_DIRECTORIES = {
    "research_answers": "research_answer",
    "scenario_plans": "scenario_plan",
    "policy_refusals": "policy_refusal",
    "historical_evidence": "historical_evidence",
    "shortlist": "shortlist",
}


def run_golden_corpus(root: Path = DEFAULT_GOLDENS_ROOT) -> EvaluationRunReport:
    """Evaluate every safe YAML fixture below a fixed or privately supplied root."""

    paths, discovery_failures, source_count = _discover_paths(root)
    failures: list[RunFailure] = list(discovery_failures)
    loaded_cases: list[tuple[Path, GoldenCase]] = []
    for path in paths:
        try:
            case = load_golden_case(path)
        except GoldenCaseLoadError as error:
            failures.append(
                _failure(path, None, "load", "valid YAML golden case", str(error))
            )
            continue
        family_failure = _family_failure(path, case.family)
        if family_failure is not None:
            failures.append(family_failure)
            continue
        loaded_cases.append((path, case))
    failures.extend(_duplicate_failures(loaded_cases))
    evaluations: list[EvaluatedCase] = []
    for path, case in loaded_cases:
        try:
            observation = adapt_observation(case)
        except InvalidEvaluationObservationError as error:
            failures.append(
                _failure(path, case.case_id, "adapter", "valid observation", str(error))
            )
            continue
        evaluations.append(
            EvaluatedCase(
                path=path, case_id=case.case_id, result=evaluate_case(case, observation)
            )
        )
    return EvaluationRunReport(
        source_count=source_count,
        evaluations=tuple(evaluations),
        failures=tuple(failures),
    )


def _discover_paths(root: Path) -> tuple[tuple[Path, ...], tuple[RunFailure, ...], int]:
    try:
        resolved_root = root.resolve(strict=True)
    except OSError as error:
        return (
            (),
            (_failure(root, None, "discovery", "readable corpus root", str(error)),),
            0,
        )
    if root.is_symlink() or not resolved_root.is_dir():
        return (
            (),
            (
                _failure(
                    root,
                    None,
                    "discovery",
                    "non-symlink directory",
                    "unsafe corpus root",
                ),
            ),
            0,
        )
    search_roots = (
        tuple(root / directory for directory in _FAMILY_DIRECTORIES)
        if root == DEFAULT_GOLDENS_ROOT
        else (root,)
    )
    candidates = tuple(
        sorted(
            (
                path
                for search_root in search_roots
                if search_root.is_dir()
                for path in search_root.rglob("*")
                if path.suffix in {".yaml", ".yml"}
            ),
            key=lambda path: path.relative_to(root).as_posix(),
        )
    )
    if not candidates:
        return (
            (),
            (
                _failure(
                    root,
                    None,
                    "discovery",
                    "non-empty YAML corpus",
                    "no YAML files found",
                ),
            ),
            0,
        )
    safe_paths: list[Path] = []
    failures: list[RunFailure] = []
    for path in candidates:
        if path.is_symlink():
            failures.append(
                _failure(path, None, "discovery", "non-symlink corpus file", "symlink")
            )
            continue
        try:
            path.resolve(strict=True).relative_to(resolved_root)
        except (OSError, ValueError) as error:
            failures.append(
                _failure(path, None, "discovery", "path within corpus root", str(error))
            )
            continue
        safe_paths.append(path)
    return tuple(safe_paths), tuple(failures), len(candidates)


def _family_failure(path: Path, family: str) -> RunFailure | None:
    expected_family = _FAMILY_DIRECTORIES.get(path.parent.name)
    if expected_family is None or expected_family != family:
        return _failure(
            path,
            None,
            "family",
            expected_family or "known golden family directory",
            family,
        )
    return None


def _duplicate_failures(
    loaded_cases: list[tuple[Path, GoldenCase]],
) -> tuple[RunFailure, ...]:
    paths_by_case_id: dict[str, list[Path]] = {}
    for path, case in loaded_cases:
        paths_by_case_id.setdefault(case.case_id, []).append(path)
    return tuple(
        _failure(
            path,
            case_id,
            "duplicate_case_id",
            "unique case_id",
            f"duplicate case_id {case_id}",
        )
        for case_id, case_paths in paths_by_case_id.items()
        if len(case_paths) > 1
        for path in case_paths
    )


def _failure(
    path: Path, case_id: str | None, check_name: str, expected: str, actual: str
) -> RunFailure:
    return RunFailure(
        path=path,
        case_id=case_id,
        check_name=check_name,
        expected=expected,
        actual=actual,
    )
