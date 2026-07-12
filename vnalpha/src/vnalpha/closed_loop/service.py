from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from vnalpha.closed_loop.bundle import RepairPreparation, package_repair
from vnalpha.closed_loop.deployment import (
    promote_research_artifact,
    rollback_research_artifact,
    verify_research_artifact,
)
from vnalpha.closed_loop.errors import ClosedLoopBoundaryError, PromotionGateError
from vnalpha.closed_loop.models import (
    DeploymentState,
    LifecycleRecord,
    LifecycleState,
    PromotableArtifactType,
    PromotionVerification,
    RepairAttempt,
    RepairBundle,
    RepairProposal,
    RepairScope,
    SandboxAttemptResult,
    ValidationReport,
    now_iso,
)
from vnalpha.closed_loop.proposal import build_proposal
from vnalpha.closed_loop.runner import SandboxRepairRunner
from vnalpha.closed_loop.service_config import (
    MAX_REPAIR_ATTEMPTS,
    configured_max_attempts,
)
from vnalpha.closed_loop.store import ClosedLoopStore
from vnalpha.closed_loop.validation import validate_research_artifact
from vnalpha.observability.redaction import redact_str


@dataclass(frozen=True, slots=True)
class ClosedLoopService:
    store: ClosedLoopStore
    max_attempts: int = field(default_factory=configured_max_attempts)

    def __post_init__(self) -> None:
        if not 1 <= self.max_attempts <= MAX_REPAIR_ATTEMPTS:
            raise ValueError(
                f"max_attempts must be between 1 and {MAX_REPAIR_ATTEMPTS}"
            )

    def prepare_failed_run(
        self,
        run_dir: Path,
        *,
        failed_job_id: str | None = None,
        user_request: str = "",
        plan_summary: str = "",
    ) -> RepairBundle:
        bundle = package_repair(
            RepairPreparation(
                run_dir=run_dir,
                failed_job_id=failed_job_id,
                user_request=user_request,
                plan_summary=plan_summary,
            ),
            self.store,
        )
        for state in (
            LifecycleState.RUN,
            LifecycleState.OBSERVE,
            LifecycleState.PACKAGE,
        ):
            self._record_bundle_state(bundle, state)
        return bundle

    def propose(
        self,
        repair_id: str,
        *,
        scope: RepairScope = RepairScope.SANDBOX_RESEARCH_CODE,
        patch: str = "",
        suspected_cause: str = "",
        replacement_generated_code: str = "",
    ) -> RepairProposal:
        bundle = self.store.load_bundle(repair_id)
        proposal = build_proposal(
            bundle,
            scope,
            patch,
            suspected_cause,
            replacement_generated_code,
        )
        self.store.save_proposal(proposal)
        state = LifecycleState.AI_FIX if proposal.accepted else LifecycleState.REJECTED
        self._record_bundle_state(bundle, state)
        self.store.emit(
            "REPAIR_PROPOSAL_CREATED",
            correlation_id=bundle.correlation_id,
            repair_id=repair_id,
            run_id=bundle.run_id or "",
            status="ACCEPTED" if proposal.accepted else "REJECTED",
            detail=proposal.rejection_reason or "bounded repair proposal created",
            metadata={
                "proposal_id": proposal.proposal_id,
                "scope": proposal.scope.value,
            },
        )
        return proposal

    def apply(
        self, repair_id: str, *, attempt: int, runner: SandboxRepairRunner
    ) -> RepairAttempt:
        bundle = self.store.load_bundle(repair_id)
        proposal = self.store.load_proposal(repair_id)
        if not proposal.accepted:
            raise ClosedLoopBoundaryError("rejected repair proposals cannot be applied")
        if attempt < 1:
            raise ClosedLoopBoundaryError("repair attempt must be positive")
        if attempt > self.max_attempts:
            self._record_bundle_state(bundle, LifecycleState.FAILED)
            raise ClosedLoopBoundaryError("maximum repair attempts exhausted")
        lifecycle = self.store.current_lifecycle(repair_id)
        if lifecycle.state in {
            LifecycleState.FAILED,
            LifecycleState.REJECTED,
            LifecycleState.VALIDATE,
            LifecycleState.PROMOTE_READY,
            LifecycleState.PROMOTED,
            LifecycleState.ROLLED_BACK,
        }:
            raise ClosedLoopBoundaryError(
                f"repair is already in terminal state {lifecycle.state.value}"
            )
        existing_attempts = self.store.list_attempts(repair_id)
        expected_attempt = len(existing_attempts) + 1
        if attempt != expected_attempt:
            raise ClosedLoopBoundaryError(
                f"repair attempt must be the next sequential attempt ({expected_attempt})"
            )
        if getattr(runner, "is_sandbox", False) is not True:
            raise ClosedLoopBoundaryError("repair attempts must use a sandbox runner")
        self._record_bundle_state(bundle, LifecycleState.AI_FIX)
        self.store.emit(
            "REPAIR_ATTEMPT_STARTED",
            correlation_id=bundle.correlation_id,
            repair_id=repair_id,
            run_id=bundle.run_id or "",
            status="STARTED",
            detail=f"sandbox repair attempt {attempt} started",
        )
        try:
            result = runner.run(bundle, proposal, attempt)
        except Exception as exc:
            result = SandboxAttemptResult(passed=False, error_trace=str(exc))
        if not isinstance(result, SandboxAttemptResult):
            result = SandboxAttemptResult(
                passed=False,
                error_trace="sandbox runner returned an invalid result",
            )
        record = RepairAttempt(
            attempt_id=f"attempt-{uuid4().hex}",
            repair_id=repair_id,
            attempt=attempt,
            passed=result.passed,
            stdout=redact_str(result.stdout),
            stderr=redact_str(result.stderr),
            error_trace=redact_str(result.error_trace),
            artifact_id=result.artifact_id,
            created_at=now_iso(),
        )
        self.store.save_attempt(record)
        self.store.emit(
            "REPAIR_ATTEMPT_SUCCEEDED" if result.passed else "REPAIR_ATTEMPT_FAILED",
            correlation_id=bundle.correlation_id,
            repair_id=repair_id,
            run_id=bundle.run_id or "",
            status="PASSED" if result.passed else "FAILED",
            detail=f"sandbox repair attempt {attempt} completed",
        )
        if result.passed:
            self._record_bundle_state(bundle, LifecycleState.VALIDATE)
        elif attempt >= self.max_attempts:
            self._record_bundle_state(bundle, LifecycleState.FAILED)
        else:
            self._record_bundle_state(bundle, LifecycleState.AI_FIX)
        return record

    def validate(
        self,
        artifact_id: str,
        *,
        artifact_root: Path | None = None,
        correlation_id: str | None = None,
    ) -> ValidationReport:
        return validate_research_artifact(
            self.store, artifact_id, artifact_root, correlation_id
        )

    def verify(
        self,
        candidate: str,
        *,
        artifact_root: Path | None = None,
        candidate_type: PromotableArtifactType | None = None,
        deployment_id: str | None = None,
    ) -> PromotionVerification:
        return verify_research_artifact(
            self.store, candidate, artifact_root, candidate_type, deployment_id
        )

    def promote(
        self,
        candidate: str,
        *,
        deployment_id: str,
        previous_candidate: str | None = None,
    ) -> DeploymentState:
        return promote_research_artifact(
            self.store, candidate, deployment_id, previous_candidate
        )

    def rollback(self, deployment_id: str, *, reason: str = "") -> DeploymentState:
        return rollback_research_artifact(self.store, deployment_id, reason)

    def _record_bundle_state(self, bundle: RepairBundle, state: LifecycleState) -> None:
        self.store.record_lifecycle(
            LifecycleRecord(
                repair_id=bundle.repair_id,
                state=state,
                correlation_id=bundle.correlation_id,
                run_id=bundle.run_id,
                sandbox_job_id=bundle.failed_job_id,
                research_experiment_id=bundle.experiment_id,
                feature_id=bundle.feature_id,
                hypothesis_id=bundle.hypothesis_id,
                pattern_id=bundle.pattern_id,
                artifact_id=bundle.artifact_id,
                created_at=now_iso(),
            )
        )


__all__ = [
    "ClosedLoopBoundaryError",
    "ClosedLoopService",
    "PromotionGateError",
    "SandboxAttemptResult",
]
