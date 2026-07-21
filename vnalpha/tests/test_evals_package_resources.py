from __future__ import annotations

from importlib import resources


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
