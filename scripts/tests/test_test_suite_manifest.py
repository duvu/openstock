from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _load_module():
    path = Path(__file__).resolve().parents[1] / "test_suite_manifest.py"
    spec = importlib.util.spec_from_file_location("test_suite_manifest", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_manifest(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def _write_test_files(root: Path, *relative_paths: str) -> None:
    for relative_path in relative_paths:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "def test_happy() -> None:\n    pass\n\n"
            "def test_failure() -> None:\n    pass\n",
            encoding="utf-8",
        )


def test_valid_manifest_assigns_every_test_file_once_and_preserves_h_plus_one(
    tmp_path: Path,
) -> None:
    module = _load_module()
    tests_root = tmp_path / "tests"
    _write_test_files(tests_root, "test_data.py", "test_app.py")
    manifest_path = _write_manifest(
        tmp_path / "manifest.toml",
        """
version = 1

[[suite]]
name = "vnalpha-data"
paths = ["tests/test_data.py"]

[[suite.contract]]
name = "market-data-read"
happy = "tests/test_data.py::test_happy"
plus_one = "tests/test_data.py::test_failure"

[[suite]]
name = "vnalpha-application"
paths = ["tests/test_app.py"]

[[suite.contract]]
name = "application-command"
happy = "tests/test_app.py::test_happy"
plus_one = "tests/test_app.py::test_failure"
""",
    )

    manifest = module.load_manifest(manifest_path, tests_root)

    assert module.validate_manifest(manifest, tests_root) == ()
    assert module.resolve_paths(manifest, ("vnalpha-data", "vnalpha-application")) == (
        "tests/test_data.py",
        "tests/test_app.py",
    )


@pytest.mark.parametrize(
    ("manifest", "expected"),
    [
        (
            """
version = 1
[[suite]]
name = "vnalpha-data"
paths = ["tests/test_data.py"]
[[suite.contract]]
name = "market-data-read"
happy = "tests/test_data.py::test_happy"
""",
            "must define exactly one happy and one plus_one case",
        ),
        (
            """
version = 1
[[suite]]
name = "vnalpha-data"
paths = ["tests/test_data.py"]
[[suite.contract]]
name = "market-data-read"
happy = "tests/test_data.py::test_happy"
plus_one = "tests/test_data.py::test_failure"
[[suite]]
name = "vnalpha-research"
paths = ["tests/test_data.py"]
[[suite.contract]]
name = "research-read"
happy = "tests/test_data.py::test_happy"
plus_one = "tests/test_data.py::test_failure"
""",
            "assigned by multiple suites",
        ),
    ],
)
def test_manifest_rejects_missing_h_plus_one_and_duplicate_ownership(
    tmp_path: Path, manifest: str, expected: str
) -> None:
    module = _load_module()
    tests_root = tmp_path / "tests"
    _write_test_files(tests_root, "test_data.py", "test_unassigned.py")
    parsed = module.load_manifest(
        _write_manifest(tmp_path / "manifest.toml", manifest), tests_root
    )

    errors = module.validate_manifest(parsed, tests_root)

    assert any(expected in error for error in errors)


def test_resolve_paths_is_stable_deduplicated_and_rejects_unknown_suite(
    tmp_path: Path,
) -> None:
    module = _load_module()
    tests_root = tmp_path / "tests"
    _write_test_files(tests_root, "test_data.py", "test_shared.py")
    manifest = module.load_manifest(
        _write_manifest(
            tmp_path / "manifest.toml",
            """
version = 1
[[suite]]
name = "vnalpha-data"
paths = ["tests/test_data.py", "tests/test_shared.py"]
[[suite.contract]]
name = "data-read"
happy = "tests/test_data.py::test_happy"
plus_one = "tests/test_data.py::test_failure"
[[suite]]
name = "shared-smoke"
paths = ["tests/test_shared.py"]
allow_shared_paths = ["tests/test_shared.py"]
[[suite.contract]]
name = "smoke"
happy = "tests/test_shared.py::test_happy"
plus_one = "tests/test_shared.py::test_failure"
""",
        ),
        tests_root,
    )

    assert module.resolve_paths(manifest, ("vnalpha-data", "shared-smoke")) == (
        "tests/test_data.py",
        "tests/test_shared.py",
    )
    with pytest.raises(module.ManifestError, match="unknown suite"):
        module.resolve_paths(manifest, ("missing",))


def test_manifest_expands_normalized_include_patterns_with_exclusions(
    tmp_path: Path,
) -> None:
    module = _load_module()
    tests_root = tmp_path / "tests"
    _write_test_files(tests_root, "test_data.py", "test_skip.py")
    manifest = module.load_manifest(
        _write_manifest(
            tmp_path / "manifest.toml",
            """
version = 1
[[suite]]
name = "vnalpha-data"
include = ["tests/test_*.py"]
exclude = ["tests/test_skip.py"]
[[suite.contract]]
name = "data-read"
happy = "tests/test_data.py::test_happy"
plus_one = "tests/test_data.py::test_failure"
""",
        ),
        tests_root,
    )

    assert manifest.suites[0].paths == ("tests/test_data.py",)


def test_manifest_rejects_contract_cases_outside_its_suite_and_unknown_risk(
    tmp_path: Path,
) -> None:
    module = _load_module()
    tests_root = tmp_path / "tests"
    _write_test_files(tests_root, "test_data.py", "test_other.py")
    content = "\n".join(
        (
            "version = 1",
            "[[suite]]",
            'name = "vnalpha-data"',
            'paths = ["tests/test_data.py", "tests/test_other.py"]',
            "[[suite.contract]]",
            'name = "data-read"',
            'happy = "tests/test_missing.py::test_happy"',
            'plus_one = "tests/test_other.py::test_failure"',
            'risk_exceptions = ["not-an-approved-risk"]',
        )
    )
    manifest = module.load_manifest(
        _write_manifest(tmp_path / "manifest.toml", content), tests_root
    )

    errors = module.validate_manifest(manifest, tests_root)

    assert any("must belong to its suite" in error for error in errors)
    assert any("unsupported risk exception" in error for error in errors)
