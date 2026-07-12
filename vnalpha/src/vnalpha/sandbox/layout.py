"""Canonical job-relative artifact locations for sandbox execution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True, slots=True)
class SandboxArtifactLayout:
    """Describe artifact paths without creating files or directories."""

    request: PurePosixPath = PurePosixPath("request.json")
    generated_code: PurePosixPath = PurePosixPath("generated_code.py")
    input_references: PurePosixPath = PurePosixPath("inputs/references.json")
    guard: PurePosixPath = PurePosixPath("guard.json")
    execution: PurePosixPath = PurePosixPath("execution.json")
    validation: PurePosixPath = PurePosixPath("validation.json")
    lifecycle: PurePosixPath = PurePosixPath("lifecycle.jsonl")
    manifest: PurePosixPath = PurePosixPath("manifest.json")
    result: PurePosixPath = PurePosixPath("output/result.json")
    summary: PurePosixPath = PurePosixPath("output/summary.md")
    stdout: PurePosixPath = PurePosixPath("output/stdout.txt")
    stderr: PurePosixPath = PurePosixPath("output/stderr.txt")
    charts: PurePosixPath = PurePosixPath("output/charts")
    tables: PurePosixPath = PurePosixPath("output/tables")
    sandbox_writable_directory: PurePosixPath = PurePosixPath("output")

    @property
    def artifact_paths(self) -> tuple[PurePosixPath, ...]:
        """Return all contract artifact locations in canonical order."""

        return (
            self.request,
            self.generated_code,
            self.input_references,
            self.guard,
            self.execution,
            self.validation,
            self.lifecycle,
            self.manifest,
            self.result,
            self.summary,
            self.stdout,
            self.stderr,
            self.charts,
            self.tables,
        )
