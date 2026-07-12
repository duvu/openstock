from __future__ import annotations

from importlib import resources
from pathlib import Path
import subprocess
import sys
import zipfile


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
    assert len(golden_entries) == 10
