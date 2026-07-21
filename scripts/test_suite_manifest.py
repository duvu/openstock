from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final

ALLOWED_SUITES: Final = frozenset(
    {
        "vnalpha-data",
        "vnalpha-research",
        "vnalpha-application",
        "shared-smoke",
        "migration",
    }
)
APPROVED_RISK_EXCEPTIONS: Final = frozenset(
    {
        "point-in-time/no-lookahead",
        "corporate-action adjustment/invalidation",
        "provider provenance conflict",
        "transaction/crash/recovery",
        "queue lease/idempotency/writer exclusion",
        "security/fail-closed",
        "migration upgrade/rollback",
        "package state preservation",
        "policy promotion/rejection/rollback",
        "cross-version compatibility",
    }
)


class ManifestError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Contract:
    name: str
    happy: str | None
    plus_one: str | None
    risk_exceptions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Suite:
    name: str
    paths: tuple[str, ...]
    contracts: tuple[Contract, ...]


@dataclass(frozen=True, slots=True)
class SuiteManifest:
    version: int | None
    suites: tuple[Suite, ...]


def _string_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ManifestError(f"{field_name} must be a list of strings")
    return tuple(value)


def _normalize_path(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise ManifestError(
            f"path must be normalized and repository-relative: {value!r}"
        )
    if not value.startswith("tests/") or not value.endswith(".py"):
        raise ManifestError(f"path must name a pytest file below tests/: {value!r}")
    return value


def _normalize_pattern(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise ManifestError(
            f"pattern must be normalized and repository-relative: {value!r}"
        )
    if not value.startswith("tests/") or not value.endswith(".py"):
        raise ManifestError(f"pattern must target pytest files below tests/: {value!r}")
    return value


def _expand_patterns(
    repository_root: Path,
    include_patterns: tuple[str, ...],
    exclude_patterns: tuple[str, ...],
) -> tuple[str, ...]:
    included = {
        path.relative_to(repository_root).as_posix()
        for pattern in include_patterns
        for path in repository_root.glob(pattern)
        if path.is_file()
    }
    excluded = {
        path.relative_to(repository_root).as_posix()
        for pattern in exclude_patterns
        for path in repository_root.glob(pattern)
        if path.is_file()
    }
    return tuple(sorted(included - excluded))


def _read_contract(value: object, suite_name: str) -> Contract:
    if not isinstance(value, dict):
        raise ManifestError(f"suite {suite_name!r} contract must be a table")
    name = value.get("name")
    if not isinstance(name, str) or not name:
        raise ManifestError(
            f"suite {suite_name!r} contract name must be a non-empty string"
        )
    happy = value.get("happy")
    plus_one = value.get("plus_one")
    if happy is not None and not isinstance(happy, str):
        raise ManifestError(f"contract {name!r} happy must be a string")
    if plus_one is not None and not isinstance(plus_one, str):
        raise ManifestError(f"contract {name!r} plus_one must be a string")
    risk_exceptions = _string_tuple(value.get("risk_exceptions", []), "risk_exceptions")
    return Contract(name, happy, plus_one, risk_exceptions)


def load_manifest(manifest_path: Path, tests_root: Path) -> SuiteManifest:
    try:
        parsed = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ManifestError(f"cannot load manifest {manifest_path}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ManifestError("manifest root must be a table")
    raw_suites = parsed.get("suite")
    if not isinstance(raw_suites, list):
        raise ManifestError("manifest must contain one or more [[suite]] tables")
    suites: list[Suite] = []
    for raw_suite in raw_suites:
        if not isinstance(raw_suite, dict):
            raise ManifestError("suite entry must be a table")
        name = raw_suite.get("name")
        if not isinstance(name, str) or not name:
            raise ManifestError("suite name must be a non-empty string")
        raw_paths = raw_suite.get("paths")
        raw_include = raw_suite.get("include")
        if raw_paths is not None and raw_include is not None:
            raise ManifestError(f"suite {name!r} must use paths or include, not both")
        if raw_paths is not None:
            paths = tuple(
                _normalize_path(item) for item in _string_tuple(raw_paths, "paths")
            )
        elif raw_include is not None:
            include_patterns = tuple(
                _normalize_pattern(item)
                for item in _string_tuple(raw_include, "include")
            )
            exclude_patterns = tuple(
                _normalize_pattern(item)
                for item in _string_tuple(raw_suite.get("exclude", []), "exclude")
            )
            paths = _expand_patterns(
                tests_root.parent, include_patterns, exclude_patterns
            )
        else:
            raise ManifestError(f"suite {name!r} must define paths or include")
        raw_contracts = raw_suite.get("contract", [])
        if not isinstance(raw_contracts, list):
            raise ManifestError(f"suite {name!r} contract must be a list")
        suites.append(
            Suite(
                name=name,
                paths=paths,
                contracts=tuple(_read_contract(item, name) for item in raw_contracts),
            )
        )
    version = parsed.get("version")
    return SuiteManifest(
        version=version if isinstance(version, int) else None, suites=tuple(suites)
    )


def _discovered_test_paths(tests_root: Path) -> tuple[str, ...]:
    repository_root = tests_root.parent
    return tuple(
        path.relative_to(repository_root).as_posix()
        for path in sorted(tests_root.rglob("test_*.py"))
    )


def _case_path(case: str) -> str | None:
    path, separator, test_name = case.partition("::")
    if not separator or not test_name:
        return None
    try:
        return _normalize_path(path)
    except ManifestError:
        return None


def validate_manifest(manifest: SuiteManifest, tests_root: Path) -> tuple[str, ...]:
    errors: list[str] = []
    if manifest.version != 1:
        errors.append("manifest version must be 1")
    owners: dict[str, list[str]] = {}
    suite_names: set[str] = set()
    repository_root = tests_root.parent
    for suite in manifest.suites:
        if suite.name not in ALLOWED_SUITES:
            errors.append(f"unsupported suite {suite.name!r}")
        if suite.name in suite_names:
            errors.append(f"suite {suite.name!r} is declared more than once")
        suite_names.add(suite.name)
        if not suite.contracts:
            errors.append(f"suite {suite.name!r} must define at least one contract")
        for path in suite.paths:
            owners.setdefault(path, []).append(suite.name)
            if not (repository_root / path).is_file():
                errors.append(
                    f"suite {suite.name!r} references missing test file {path!r}"
                )
        for contract in suite.contracts:
            if contract.happy is None or contract.plus_one is None:
                errors.append(
                    f"contract {contract.name!r} must define exactly one happy and one plus_one case"
                )
            elif contract.happy == contract.plus_one:
                errors.append(
                    f"contract {contract.name!r} happy and plus_one cases must be distinct"
                )
            for case in (contract.happy, contract.plus_one):
                if case is None:
                    continue
                case_path = _case_path(case)
                if case_path not in suite.paths:
                    errors.append(
                        f"contract {contract.name!r} case {case!r} must belong to its suite"
                    )
            for risk_exception in contract.risk_exceptions:
                if risk_exception not in APPROVED_RISK_EXCEPTIONS:
                    errors.append(
                        f"contract {contract.name!r} has unsupported risk exception {risk_exception!r}"
                    )
    for path, assigned_suites in sorted(owners.items()):
        if len(assigned_suites) > 1:
            errors.append(
                f"test file {path!r} is assigned by multiple suites: {assigned_suites}"
            )
    for path in _discovered_test_paths(tests_root):
        if path not in owners:
            errors.append(f"test file {path!r} is unassigned")
    return tuple(errors)


def resolve_paths(
    manifest: SuiteManifest, requested_suites: tuple[str, ...]
) -> tuple[str, ...]:
    by_name = {suite.name: suite for suite in manifest.suites}
    resolved: list[str] = []
    seen: set[str] = set()
    for suite_name in requested_suites:
        suite = by_name.get(suite_name)
        if suite is None:
            raise ManifestError(f"unknown suite: {suite_name}")
        for path in suite.paths:
            if path not in seen:
                seen.add(path)
                resolved.append(path)
    return tuple(resolved)
