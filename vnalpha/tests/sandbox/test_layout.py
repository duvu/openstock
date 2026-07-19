from __future__ import annotations

from pathlib import PurePosixPath


def test_layout_defines_exact_canonical_job_relative_artifacts_without_creating_files() -> (
    None
):
    from vnalpha.sandbox.layout import SandboxArtifactLayout

    layout = SandboxArtifactLayout()

    assert layout.artifact_paths == (
        PurePosixPath("request.json"),
        PurePosixPath("generated_code.py"),
        PurePosixPath("inputs/references.json"),
        PurePosixPath("guard.json"),
        PurePosixPath("execution.json"),
        PurePosixPath("validation.json"),
        PurePosixPath("lifecycle.jsonl"),
        PurePosixPath("manifest.json"),
        PurePosixPath("output/result.json"),
        PurePosixPath("output/summary.md"),
        PurePosixPath("output/stdout.txt"),
        PurePosixPath("output/stderr.txt"),
        PurePosixPath("output/charts"),
        PurePosixPath("output/tables"),
    )
    assert layout.sandbox_writable_directory == PurePosixPath("output")
    assert all(
        not path.is_absolute() and path.as_posix() == str(path)
        for path in layout.artifact_paths
    )
