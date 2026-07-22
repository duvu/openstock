from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final

import tomllib

ALLOWED_DOMAINS: Final = frozenset({"application", "data", "research"})


class ManifestError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Contract:
    identifier: str
    domain: str
    test: str


@dataclass(frozen=True, slots=True)
class AuthoritativeInventory:
    version: int
    target_min: int
    target_max: int
    hard_cap: int
    contracts: tuple[Contract, ...]


def _read_text(manifest_path: Path) -> str:
    try:
        return manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError(f"cannot read inventory {manifest_path}: {exc}") from exc


def _string(value, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ManifestError(f"{name} must be a non-empty string")
    return value


def _integer(value, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ManifestError(f"{name} must be an integer")
    return value


def _test_path(node: str) -> str:
    path, separator, name = node.partition("::")
    if not separator or not name:
        raise ManifestError(f"test must be an exact pytest node: {node!r}")
    normalized = PurePosixPath(path)
    if (
        normalized.is_absolute()
        or ".." in normalized.parts
        or normalized.as_posix() != path
        or not path.startswith("tests/")
        or not path.endswith(".py")
    ):
        raise ManifestError(
            f"test must be a normalized pytest node below tests/: {node!r}"
        )
    return path


def _defined_tests(tests_root: Path) -> set[tuple[str, ...]]:
    definitions: set[tuple[str, ...]] = set()
    for source_path in tests_root.rglob("*.py"):
        test_path = source_path.relative_to(tests_root.parent).as_posix()
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for child in tree.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if child.name.startswith("test_"):
                    definitions.add((test_path, child.name))
            if isinstance(child, ast.ClassDef) and child.name.startswith("Test"):
                definitions.update(
                    (test_path, child.name, method.name)
                    for method in child.body
                    if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and method.name.startswith("test_")
                )
    return definitions


def load_manifest(manifest_path: Path) -> AuthoritativeInventory:
    try:
        parsed = tomllib.loads(_read_text(manifest_path))
    except tomllib.TOMLDecodeError as exc:
        raise ManifestError(f"cannot parse inventory {manifest_path}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ManifestError("inventory root must be a table")
    raw_contracts = parsed.get("contract")
    if not isinstance(raw_contracts, list):
        raise ManifestError("inventory must contain one or more [[contract]] tables")
    contracts: list[Contract] = []
    for raw_contract in raw_contracts:
        if not isinstance(raw_contract, dict):
            raise ManifestError("contract entry must be a table")
        contracts.append(
            Contract(
                identifier=_string(raw_contract.get("id"), "contract id"),
                domain=_string(raw_contract.get("domain"), "contract domain"),
                test=_string(raw_contract.get("test"), "contract test"),
            )
        )
    return AuthoritativeInventory(
        version=_integer(parsed.get("version"), "version"),
        target_min=_integer(parsed.get("target_min"), "target_min"),
        target_max=_integer(parsed.get("target_max"), "target_max"),
        hard_cap=_integer(parsed.get("hard_cap"), "hard_cap"),
        contracts=tuple(contracts),
    )


def validate_manifest(
    inventory: AuthoritativeInventory, tests_root: Path
) -> tuple[str, ...]:
    errors: list[str] = []
    if inventory.version != 1:
        errors.append("inventory version must be 1")
    if inventory.target_min != 180 or inventory.target_max != 220:
        errors.append("inventory target range must be 180 through 220")
    if inventory.hard_cap != 250:
        errors.append("inventory hard cap must be 250")
    count = len(inventory.contracts)
    if not inventory.target_min <= count <= inventory.target_max:
        errors.append(
            f"inventory has {count} contracts; expected {inventory.target_min} through {inventory.target_max}"
        )
    if count > inventory.hard_cap:
        errors.append(
            f"inventory has {count} contracts; hard cap is {inventory.hard_cap}"
        )
    identifiers: set[str] = set()
    tests: set[str] = set()
    expected_definitions: set[tuple[str, ...]] = set()
    for contract in inventory.contracts:
        if contract.identifier in identifiers:
            errors.append(f"contract id is duplicated: {contract.identifier!r}")
        identifiers.add(contract.identifier)
        if contract.domain not in ALLOWED_DOMAINS:
            errors.append(
                f"contract {contract.identifier!r} has unsupported domain {contract.domain!r}"
            )
        if contract.test in tests:
            errors.append(f"pytest node is duplicated: {contract.test!r}")
        tests.add(contract.test)
        expected_definitions.add(tuple(contract.test.split("::")))
        try:
            test_path = _test_path(contract.test)
        except ManifestError as exc:
            errors.append(f"contract {contract.identifier!r}: {exc}")
        else:
            if not (tests_root.parent / test_path).is_file():
                errors.append(
                    f"contract {contract.identifier!r} references missing test file {test_path!r}"
                )
    defined_tests = _defined_tests(tests_root)
    for definition in sorted(defined_tests - expected_definitions):
        errors.append(f"test is unclassified: {'::'.join(definition)}")
    for definition in sorted(expected_definitions - defined_tests):
        errors.append(f"inventory node has no test definition: {'::'.join(definition)}")
    return tuple(errors)


def resolve_tests(
    inventory: AuthoritativeInventory, requested_domains: tuple[str, ...]
) -> tuple[str, ...]:
    unknown = sorted(set(requested_domains) - ALLOWED_DOMAINS)
    if unknown:
        raise ManifestError(f"unknown domain: {', '.join(unknown)}")
    selected_domains = frozenset(requested_domains)
    return tuple(
        contract.test
        for contract in inventory.contracts
        if not selected_domains or contract.domain in selected_domains
    )
