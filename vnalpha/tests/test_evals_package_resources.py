from __future__ import annotations

import os
import subprocess
import sys
import zipfile
from importlib import resources
from pathlib import Path


def test_default_golden_corpus_when_package_is_imported_uses_package_data() -> None:
    # Given: the installed-package resource namespace for vnalpha.evals
    packaged_root = resources.files("vnalpha.evals").joinpath("goldens")

    # When: the public default fixture runner evaluates its corpus
    from vnalpha.evals.runner import DEFAULT_GOLDENS_ROOT, run_golden_corpus

    report = run_golden_corpus()

    # Then: discovery originates in package data and emits stable relative paths
    assert packaged_root.is_dir()
    assert DEFAULT_GOLDENS_ROOT == packaged_root
    assert report.source_count == 5
    assert all(not evaluation.path.is_absolute() for evaluation in report.evaluations)


def test_wheel_when_built_contains_the_complete_golden_corpus(tmp_path: Path) -> None:
    # Given: the real vnalpha build configuration and a clean wheel output directory
    project_root = Path(__file__).resolve().parents[1]

    # When: setuptools builds the distributable wheel
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(tmp_path),
            str(project_root),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = next(tmp_path.glob("vnalpha-*.whl"))

    # Then: all positive and regression YAML resources are inside the wheel
    with zipfile.ZipFile(wheel) as archive:
        golden_entries = {
            name
            for name in archive.namelist()
            if name.startswith("vnalpha/evals/goldens/") and name.endswith(".yaml")
        }
        runtime_entries = {
            name
            for name in archive.namelist()
            if name.startswith("vnalpha/evals/runtime_cases/")
            and name.endswith(".json")
        }
    assert len(golden_entries) == 10
    assert len(runtime_entries) == 16


def test_installed_wheel_when_cli_runs_both_offline_evals(tmp_path: Path) -> None:
    # Given: a wheel installed into an isolated target directory with no source checkout on sys.path
    project_root = Path(__file__).resolve().parents[1]
    wheel_dir = tmp_path / "wheel"
    wheel_dir.mkdir()
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheel_dir),
            str(project_root),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = next(wheel_dir.glob("vnalpha-*.whl"))
    install_root = tmp_path / "installed"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--target",
            str(install_root),
            str(wheel),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    # When: the installed package's real CLI entry point runs both deterministic eval modes
    env = dict(os.environ)
    env["PYTHONPATH"] = str(install_root)
    for command in (
        ("eval", "research-answers", "--ci"),
        ("eval", "research-runtime", "--ci"),
    ):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from vnalpha.cli import app; app()",
                *command,
            ],
            cwd=tmp_path,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )

        # Then: package resources are discoverable without repository-relative paths
        assert result.returncode == 0, result.stdout + result.stderr
