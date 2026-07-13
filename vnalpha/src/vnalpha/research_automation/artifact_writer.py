"""Writers for research automation artifact files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from vnalpha.research_automation.layout import ResearchArtifactLayout
from vnalpha.research_automation.models import ArtifactOutputs, now_utc


class ResearchArtifactWriterError(ValueError):
    """Output persistence for a research artifact failed."""


@dataclass(frozen=True, slots=True)
class ResearchArtifactWriter:
    """Persist required and optional research automation outputs to disk."""

    layout: ResearchArtifactLayout

    def persist_outputs(
        self,
        *,
        result: Mapping[str, Any],
        summary: str,
        lineage: Mapping[str, Any],
        validation: Mapping[str, Any],
        manifest: Mapping[str, Any] | None = None,
        reproducibility_manifest: Mapping[str, Any] | None = None,
        generated_code: str | bytes | None = None,
        metrics_csv: str | bytes | None = None,
        candidates_csv: str | bytes | None = None,
        charts: Mapping[str, str | bytes] | None = None,
    ) -> ArtifactOutputs:
        self.layout.ensure_root()
        chart_paths: tuple[Path, ...] = ()
        extra_paths = {
            "lineage_json": str(self.layout.lineage_json),
            "validation_json": str(self.layout.validation_json),
            "manifest_json": str(self.layout.manifest),
        }

        _write_json(self.layout.result_json, result)
        _write_text(self.layout.summary_md, summary)
        _write_json(self.layout.lineage_json, lineage)
        _write_json(self.layout.validation_json, validation)

        generated_code_path = self.layout.generated_code
        reproducibility_manifest_path = self.layout.reproducibility_manifest

        if manifest is None:
            manifest = {
                "artifact_root": str(self.layout.root),
                "artifact_id": self.layout.artifact_id,
                "generated_at": now_utc().isoformat(),
                "outputs": {
                    "manifest": str(self.layout.manifest),
                    "result_json": str(self.layout.result_json),
                    "summary_md": str(self.layout.summary_md),
                    "lineage_json": str(self.layout.lineage_json),
                    "validation_json": str(self.layout.validation_json),
                },
            }
        _write_json(self.layout.manifest, manifest)

        if reproducibility_manifest is not None:
            _write_json(reproducibility_manifest_path, reproducibility_manifest)

        if generated_code is not None:
            _write_bytes(generated_code_path, generated_code)

        if metrics_csv is not None:
            _write_bytes(self.layout.metrics_csv, metrics_csv)
            extra_paths["metrics_csv"] = str(self.layout.metrics_csv)

        if candidates_csv is not None:
            _write_bytes(self.layout.candidates_csv, candidates_csv)
            extra_paths["candidates_csv"] = str(self.layout.candidates_csv)

        if charts:
            for name, content in charts.items():
                safe_name = _safe_chart_name(name)
                path = self.layout.chart_path(safe_name)
                _write_bytes(path, content)
                chart_paths = (*chart_paths, path)
                extra_paths[f"chart:{safe_name}"] = str(path)

        return ArtifactOutputs(
            manifest=self.layout.manifest,
            result_json=self.layout.result_json,
            summary_md=self.layout.summary_md,
            lineage_json=self.layout.lineage_json,
            validation_json=self.layout.validation_json,
            reproducibility_manifest=(
                reproducibility_manifest_path
                if reproducibility_manifest is not None
                else None
            ),
            generated_code_path=(
                generated_code_path if generated_code is not None else None
            ),
            metrics_csv=(self.layout.metrics_csv if metrics_csv is not None else None),
            candidates_csv=(
                self.layout.candidates_csv if candidates_csv is not None else None
            ),
            charts=chart_paths,
            extra_paths=extra_paths,
        )


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    try:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        raise ResearchArtifactWriterError(
            f"failed to write json {path}: {exc}"
        ) from exc


def _write_text(path: Path, text: str) -> None:
    try:
        path.write_text(text, encoding="utf-8")
    except Exception as exc:
        raise ResearchArtifactWriterError(
            f"failed to write text {path}: {exc}"
        ) from exc


def _write_bytes(path: Path, value: str | bytes) -> None:
    payload = value if isinstance(value, (bytes, bytearray)) else value.encode("utf-8")
    try:
        path.write_bytes(payload)
    except Exception as exc:
        raise ResearchArtifactWriterError(
            f"failed to write bytes {path}: {exc}"
        ) from exc


def _safe_chart_name(name: str) -> str:
    value = name.strip()
    if not value:
        return "chart"
    cleaned = "".join(ch for ch in value if ch.isalnum() or ch in "-_")
    return cleaned or "chart"
