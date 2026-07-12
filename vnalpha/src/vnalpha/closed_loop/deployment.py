from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from vnalpha.closed_loop.deployment_support import (
    candidate_is_safe,
    manifest_type,
    safe_identifier,
    verified_artifact_root,
    write_promotion_marker,
)
from vnalpha.closed_loop.errors import (
    ClosedLoopBoundaryError,
    ClosedLoopNotFoundError,
    PromotionGateError,
)
from vnalpha.closed_loop.models import (
    DeploymentState,
    LifecycleRecord,
    LifecycleState,
    PromotableArtifactType,
    PromotionVerification,
    now_iso,
)
from vnalpha.closed_loop.store import ClosedLoopStore
from vnalpha.closed_loop.validation import artifact_digest, resolve_artifact_root


def verify_research_artifact(
    store: ClosedLoopStore,
    candidate: str,
    artifact_root: Path | None = None,
    candidate_type: PromotableArtifactType | None = None,
    deployment_id: str | None = None,
) -> PromotionVerification:
    candidate = safe_identifier(candidate, "candidate")
    deployment = deployment_id or f"deployment-{uuid4().hex}"
    deployment = safe_identifier(deployment, "deployment_id")
    root = artifact_root or resolve_artifact_root(store.root, candidate)
    if root is not None:
        try:
            root = store.scoped_directory(root, "artifact root")
            digest = artifact_digest(root)
        except (ClosedLoopBoundaryError, OSError, UnicodeDecodeError):
            root = None
            digest = ""
    else:
        digest = ""
    report = _load_report(store, candidate)
    artifact_type = manifest_type(root)
    resolved_type = candidate_type or artifact_type
    type_matches = artifact_type is not None and (
        candidate_type is None or candidate_type is artifact_type
    )
    passed = (
        report is not None
        and report.passed
        and report.artifact_id == candidate
        and root is not None
        and root.is_dir()
        and report.artifact_digest == digest
        and bool(digest)
        and report.artifact_root == str(root)
        and resolved_type is not None
        and type_matches
        and candidate_is_safe(root, candidate)
    )
    correlation_id = (
        report.correlation_id if report is not None else f"artifact-{candidate}"
    )
    verification = PromotionVerification(
        candidate=candidate,
        deployment_id=deployment,
        correlation_id=correlation_id,
        candidate_type=resolved_type or PromotableArtifactType.FEATURE_DEFINITION,
        validation_report_id=report.artifact_id if report is not None else "missing",
        artifact_digest=digest,
        artifact_root=str(root) if root is not None else None,
        passed=passed,
        created_at=now_iso(),
    )
    store.save_verification(verification)
    store.emit(
        "DEPLOY_VERIFY_COMPLETED",
        correlation_id=verification.correlation_id,
        artifact_id=candidate,
        status="PASSED" if passed else "FAILED",
        detail="research artifact promotion readiness checked",
        metadata={
            "deployment_id": deployment,
            "candidate_type": verification.candidate_type.value,
        },
    )
    return verification


def promote_research_artifact(
    store: ClosedLoopStore,
    candidate: str,
    deployment_id: str,
    previous_candidate: str | None = None,
) -> DeploymentState:
    candidate = safe_identifier(candidate, "candidate")
    deployment_id = safe_identifier(deployment_id, "deployment_id")
    try:
        verification = store.load_verification(deployment_id)
    except ClosedLoopNotFoundError as exc:
        raise PromotionGateError(
            "validation verification is required before promotion"
        ) from exc
    if verification.candidate != candidate or not verification.passed:
        raise PromotionGateError(
            "validation gate or read-only boundary check has not passed"
        )
    root = verified_artifact_root(store, verification)
    if root is None:
        raise PromotionGateError("verified research artifact root is unavailable")
    try:
        report = store.load_validation_report(candidate)
    except ClosedLoopNotFoundError as exc:
        raise PromotionGateError("validation report is unavailable") from exc
    if (
        not report.passed
        or report.artifact_digest != verification.artifact_digest
        or report.correlation_id != verification.correlation_id
    ):
        raise PromotionGateError("validation evidence is stale or no longer passing")
    try:
        current_digest = artifact_digest(root)
    except (ClosedLoopBoundaryError, OSError, UnicodeDecodeError) as exc:
        raise PromotionGateError(
            "research artifact evidence could not be rechecked"
        ) from exc
    if current_digest != verification.artifact_digest or not candidate_is_safe(
        root, candidate
    ):
        raise PromotionGateError(
            "research artifact changed or crossed the read-only boundary"
        )
    state = DeploymentState(
        deployment_id=deployment_id,
        candidate=candidate,
        candidate_type=verification.candidate_type,
        correlation_id=verification.correlation_id,
        validation_report_id=verification.validation_report_id,
        artifact_root=verification.artifact_root,
        previous_candidate=previous_candidate,
        status="PROMOTED",
        created_at=verification.created_at,
        updated_at=now_iso(),
    )
    store.save_deployment(state)
    write_promotion_marker(store, state, "PROMOTED", "")
    store.emit(
        "RESEARCH_ARTIFACT_PROMOTED",
        correlation_id=state.correlation_id,
        artifact_id=candidate,
        status="PROMOTED",
        detail="research artifact promoted",
        metadata={
            "deployment_id": deployment_id,
            "artifact_type": state.candidate_type.value,
        },
    )
    store.record_lifecycle(
        LifecycleRecord(
            repair_id=f"artifact:{candidate}",
            state=LifecycleState.PROMOTED,
            correlation_id=state.correlation_id,
            artifact_id=candidate,
            created_at=state.updated_at,
            detail="research artifact promotion recorded",
        )
    )
    return state


def rollback_research_artifact(
    store: ClosedLoopStore, deployment_id: str, reason: str = ""
) -> DeploymentState:
    try:
        state = store.load_deployment(deployment_id)
    except ClosedLoopNotFoundError as exc:
        raise PromotionGateError("deployment state was not found") from exc
    rolled_back = state.model_copy(
        update={
            "status": "ROLLED_BACK",
            "updated_at": now_iso(),
            "rollback_reason": reason,
        }
    )
    store.save_deployment(rolled_back)
    write_promotion_marker(store, rolled_back, "ROLLED_BACK", reason)
    store.emit(
        "RESEARCH_ARTIFACT_ROLLED_BACK",
        correlation_id=rolled_back.correlation_id,
        artifact_id=rolled_back.candidate,
        status="ROLLED_BACK",
        detail="research artifact promotion rolled back",
        metadata={"deployment_id": deployment_id, "reason": reason},
    )
    store.record_lifecycle(
        LifecycleRecord(
            repair_id=f"artifact:{rolled_back.candidate}",
            state=LifecycleState.ROLLED_BACK,
            correlation_id=rolled_back.correlation_id,
            artifact_id=rolled_back.candidate,
            created_at=rolled_back.updated_at,
            detail=reason,
        )
    )
    return rolled_back


def _load_report(store: ClosedLoopStore, artifact_id: str):
    try:
        return store.load_validation_report(artifact_id)
    except ClosedLoopNotFoundError:
        return None
