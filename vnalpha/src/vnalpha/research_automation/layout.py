"""Artifact layout helpers for research automation persistence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Final

from vnalpha.research_automation.models import ArtifactOutputs

RESEARCH_ARTIFACT_ROOT: Final = "research"
MANIFEST_FILE: Final = "manifest.json"
RESULT_FILE: Final = "result.json"
SUMMARY_FILE: Final = "summary.md"
LINEAGE_FILE: Final = "lineage.json"
VALIDATION_FILE: Final = "validation.json"
GENERATED_CODE_FILE: Final = "generated_code.py"
REPRO_MANIFEST_FILE: Final = "reproducibility_manifest.json"
METRICS_TABLE_FILE: Final = "metrics.csv"
CANDIDATES_TABLE_FILE: Final = "candidates.csv"
CHARTS_DIR: Final = "charts"


class ResearchArtifactLayoutError(ValueError):
    """Research artifact path metadata is invalid."""

    @staticmethod
    def for_artifact_id(artifact_id: str) -> "ResearchArtifactLayoutError":
        return ResearchArtifactLayoutError(
            f"Invalid artifact identifier for filesystem layout: {artifact_id!r}"
        )


@dataclass(frozen=True, slots=True)
class ResearchArtifactLayout:
    """Stable filesystem positions for one research artifact."""

    run_dir: Path
    artifact_id: str

    def __post_init__(self) -> None:
        if not self.artifact_id:
            raise ResearchArtifactLayoutError.for_artifact_id(self.artifact_id)
        if self.artifact_id in {".", ".."}:
            raise ResearchArtifactLayoutError.for_artifact_id(self.artifact_id)
        posix = PurePosixPath(self.artifact_id)
        windows = PureWindowsPath(self.artifact_id)
        if posix.is_absolute() or windows.is_absolute():
            raise ResearchArtifactLayoutError.for_artifact_id(self.artifact_id)
        if ".." in posix.parts or ".." in windows.parts:
            raise ResearchArtifactLayoutError.for_artifact_id(self.artifact_id)

    @property
    def root(self) -> Path:
        return self.run_dir / RESEARCH_ARTIFACT_ROOT / self.artifact_id

    @property
    def manifest(self) -> Path:
        return self.root / MANIFEST_FILE

    @property
    def result_json(self) -> Path:
        return self.root / RESULT_FILE

    @property
    def summary_md(self) -> Path:
        return self.root / SUMMARY_FILE

    @property
    def lineage_json(self) -> Path:
        return self.root / LINEAGE_FILE

    @property
    def validation_json(self) -> Path:
        return self.root / VALIDATION_FILE

    @property
    def reproducibility_manifest(self) -> Path:
        return self.root / REPRO_MANIFEST_FILE

    @property
    def generated_code(self) -> Path:
        return self.root / GENERATED_CODE_FILE

    @property
    def metrics_csv(self) -> Path:
        return self.root / METRICS_TABLE_FILE

    @property
    def candidates_csv(self) -> Path:
        return self.root / CANDIDATES_TABLE_FILE

    @property
    def charts_dir(self) -> Path:
        return self.root / CHARTS_DIR

    def chart_path(self, name: str) -> Path:
        return self.charts_dir / f"{name}.png"

    def outputs(self) -> ArtifactOutputs:
        return ArtifactOutputs(
            manifest=self.manifest,
            result_json=self.result_json,
            summary_md=self.summary_md,
            lineage_json=self.lineage_json,
            validation_json=self.validation_json,
            reproducibility_manifest=self.reproducibility_manifest,
            generated_code_path=self.generated_code,
            metrics_csv=self.metrics_csv,
            candidates_csv=self.candidates_csv,
            charts=(),
            extra_paths={},
        )

    def ensure_root(self) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        self.charts_dir.mkdir(parents=True, exist_ok=True)
        return self.root
