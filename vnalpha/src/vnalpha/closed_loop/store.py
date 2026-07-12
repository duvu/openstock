from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from vnalpha.closed_loop.errors import ClosedLoopNotFoundError
from vnalpha.closed_loop.events import EventInput, emit_event, event_types
from vnalpha.closed_loop.models import (
    DeploymentState,
    JsonObject,
    LifecycleRecord,
    LifecycleState,
    PromotionVerification,
    RepairAttempt,
    RepairBundle,
    RepairProposal,
    ValidationReport,
    now_iso,
)
from vnalpha.closed_loop.paths import (
    ensure_tree_confined,
    resolve_component,
    resolve_file,
    resolve_under,
    validate_identifier,
)
from vnalpha.closed_loop.store_io import (
    append_json,
    load_model,
    read_json_lines,
    write_json,
    write_model,
)


@dataclass(frozen=True, slots=True)
class ClosedLoopStore:
    root: Path

    def scoped_path(self, path: Path, field: str = "path") -> Path:
        return resolve_under(self.root, path, field)

    def scoped_directory(self, path: Path, field: str = "directory") -> Path:
        resolved = ensure_tree_confined(self.root, path, field)
        if not resolved.is_dir():
            raise ClosedLoopNotFoundError(f"{field} was not found: {resolved}")
        return resolved

    def run_directory(self, path: Path) -> Path:
        resolved = ensure_tree_confined(self.root / "runs", path, "run directory")
        if not resolved.is_dir():
            raise ClosedLoopNotFoundError(f"run directory was not found: {resolved}")
        ensure_tree_confined(resolved, resolved, "run directory")
        return resolved

    def _bundle_dir(self, repair_id: str) -> Path:
        return resolve_component(self.root, "bundles", repair_id, "repair_id")

    def _deployment_path(self, value: str, field: str) -> Path:
        deployment_id = value
        if field == "verification":
            deployment_id = value.removesuffix("-verification.json")
        suffix = "-verification.json" if field == "verification" else ".json"
        return resolve_file(
            self.root, "deployments", deployment_id, suffix, "deployment_id"
        )

    def save_bundle(self, bundle: RepairBundle) -> Path:
        bundle_dir = self._bundle_dir(bundle.repair_id)
        write_model(self.scoped_path(bundle_dir / "repair-bundle.json"), bundle)
        write_json(
            self.scoped_path(bundle_dir / "manifest.json"),
            {
                "bundle_id": bundle.repair_id,
                "bundle_type": "repair",
                "source_run_id": bundle.run_id,
                "source_job_id": bundle.failed_job_id,
                "correlation_id": bundle.correlation_id,
                "redaction_status": bundle.redaction_status,
                "included_sections": [
                    "repair-bundle.json",
                    "static_guard_result",
                    "stdout",
                    "stderr",
                    "error_trace",
                    "input_dataset_references",
                    "artifact_manifest",
                    "output_state",
                    "validation_result",
                    "environment_summary",
                ],
            },
        )
        write_json(
            self.scoped_path(bundle_dir / "repair-state.json"),
            {"repair_status": LifecycleState.PACKAGE.value, "updated_at": now_iso()},
        )
        return bundle_dir

    def load_bundle(self, repair_id: str) -> RepairBundle:
        path = self._bundle_dir(repair_id) / "repair-bundle.json"
        return load_model(self.scoped_path(path, "repair bundle"), RepairBundle)

    def save_proposal(self, proposal: RepairProposal) -> None:
        write_model(
            self.scoped_path(
                self._bundle_dir(proposal.repair_id) / "repair-proposal.json"
            ),
            proposal,
        )

    def load_proposal(self, repair_id: str) -> RepairProposal:
        return load_model(
            self.scoped_path(self._bundle_dir(repair_id) / "repair-proposal.json"),
            RepairProposal,
        )

    def save_attempt(self, attempt: RepairAttempt) -> None:
        write_model(
            self.scoped_path(
                self._bundle_dir(attempt.repair_id)
                / "attempts"
                / f"attempt-{attempt.attempt}.json"
            ),
            attempt,
        )

    def list_attempts(self, repair_id: str) -> tuple[RepairAttempt, ...]:
        attempts_dir = self.scoped_path(
            self._bundle_dir(repair_id) / "attempts", "attempts directory"
        )
        if not attempts_dir.exists():
            return ()
        values: list[RepairAttempt] = []
        for path in sorted(attempts_dir.glob("attempt-*.json")):
            values.append(load_model(self.scoped_path(path, "attempt"), RepairAttempt))
        return tuple(values)

    def record_lifecycle(self, record: LifecycleRecord) -> None:
        path = self._lifecycle_path(record.repair_id)
        append_json(self.scoped_path(path, "lifecycle"), record.model_dump(mode="json"))
        write_json(
            self.scoped_path(self._state_path(record.repair_id), "state"),
            {"state": record.state.value, "updated_at": record.created_at},
        )

    def current_lifecycle(self, repair_id: str) -> LifecycleRecord:
        path = self._lifecycle_path(repair_id)
        records = read_json_lines(self.scoped_path(path, "lifecycle"))
        if not records:
            raise ClosedLoopNotFoundError(f"no lifecycle state for {repair_id}")
        return LifecycleRecord.model_validate_json(json.dumps(records[-1]))

    def save_validation_report(
        self, report: ValidationReport, artifact_root: Path | None = None
    ) -> None:
        path = resolve_file(
            self.root, "validations", report.artifact_id, ".json", "artifact_id"
        )
        write_model(self.scoped_path(path, "validation report"), report)
        if artifact_root is not None:
            root = self.scoped_directory(artifact_root, "artifact root")
            write_model(self.scoped_path(root / "validation-report.json"), report)

    def load_validation_report(self, artifact_id: str) -> ValidationReport:
        return load_model(
            resolve_file(
                self.root,
                "validations",
                validate_identifier(artifact_id, "artifact_id"),
                ".json",
                "validation report",
            ),
            ValidationReport,
        )

    def save_verification(self, verification: PromotionVerification) -> None:
        write_model(
            self._deployment_path(
                f"{verification.deployment_id}-verification.json", "verification"
            ),
            verification,
        )

    def load_verification(self, deployment_id: str) -> PromotionVerification:
        return load_model(
            self._deployment_path(f"{deployment_id}-verification.json", "verification"),
            PromotionVerification,
        )

    def save_deployment(self, state: DeploymentState) -> None:
        write_model(self._deployment_path(state.deployment_id, "deployment"), state)

    def load_deployment(self, deployment_id: str) -> DeploymentState:
        return load_model(
            self._deployment_path(deployment_id, "deployment"), DeploymentState
        )

    def emit(
        self,
        event_type: str,
        *,
        correlation_id: str,
        repair_id: str = "",
        artifact_id: str = "",
        run_id: str = "",
        status: str = "OK",
        detail: str = "",
        metadata: JsonObject | None = None,
    ) -> None:
        emit_event(
            self.root,
            EventInput(
                event_type=event_type,
                correlation_id=correlation_id,
                repair_id=repair_id,
                artifact_id=artifact_id,
                run_id=run_id,
                status=status,
                detail=detail,
                metadata=metadata,
            ),
        )

    def event_types(self, identifier: str) -> list[str]:
        return event_types(self.root, identifier)

    def _lifecycle_path(self, repair_id: str) -> Path:
        if repair_id.startswith("artifact:"):
            artifact_id = validate_identifier(repair_id[9:], "artifact_id")
            return resolve_file(
                self.root, "closed-loop", artifact_id, "-lifecycle.jsonl", "lifecycle"
            )
        return self._bundle_dir(repair_id) / "lifecycle.jsonl"

    def _state_path(self, repair_id: str) -> Path:
        if repair_id.startswith("artifact:"):
            artifact_id = validate_identifier(repair_id[9:], "artifact_id")
            return resolve_file(
                self.root, "closed-loop", artifact_id, "-state.json", "state"
            )
        return self._bundle_dir(repair_id) / "repair-state.json"
