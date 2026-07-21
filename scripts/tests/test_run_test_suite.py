from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[1] / "run_test_suite.py"
    spec = importlib.util.spec_from_file_location("run_test_suite", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _manifest() -> str:
    return "\n".join(
        (
            "version = 1",
            "[[suite]]",
            'name = "vnalpha-data"',
            'paths = ["tests/test_data.py"]',
            "[[suite.contract]]",
            'name = "data"',
            'happy = "tests/test_data.py::test_happy"',
            'plus_one = "tests/test_data.py::test_failure"',
            "[[suite]]",
            'name = "shared-smoke"',
            'paths = ["tests/test_shared.py"]',
            "[[suite.contract]]",
            'name = "shared"',
            'happy = "tests/test_shared.py::test_happy"',
            'plus_one = "tests/test_shared.py::test_failure"',
        )
    )


def _write_test(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "def test_happy() -> None:\n    pass\n\n"
        "def test_failure() -> None:\n    pass\n",
        encoding="utf-8",
    )


def test_runner_resolves_overlapping_suites_to_one_stable_pytest_call(
    tmp_path: Path,
) -> None:
    module = _load_module()
    tests_root = tmp_path / "tests"
    _write_test(tests_root / "test_data.py")
    _write_test(tests_root / "test_shared.py")
    manifest_path = tmp_path / "manifest.toml"
    manifest_path.write_text(_manifest(), encoding="utf-8")
    calls: list[tuple[str, ...]] = []

    exit_code = module.run_suites(
        manifest_path=manifest_path,
        tests_root=tests_root,
        suite_names=("vnalpha-data", "vnalpha-data", "shared-smoke"),
        pytest_runner=lambda paths: calls.append(paths) or 7,
    )

    assert exit_code == 7
    assert calls == [("tests/test_data.py", "tests/test_shared.py")]


def test_runner_rejects_unknown_suites_before_invoking_pytest(tmp_path: Path) -> None:
    module = _load_module()
    tests_root = tmp_path / "tests"
    _write_test(tests_root / "test_data.py")
    _write_test(tests_root / "test_shared.py")
    manifest_path = tmp_path / "manifest.toml"
    manifest_path.write_text(_manifest(), encoding="utf-8")

    exit_code = module.run_suites(
        manifest_path=manifest_path,
        tests_root=tests_root,
        suite_names=("missing",),
        pytest_runner=lambda _: 0,
    )

    assert exit_code == 2
