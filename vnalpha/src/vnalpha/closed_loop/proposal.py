from __future__ import annotations

from uuid import uuid4

from vnalpha.closed_loop.models import RepairBundle, RepairProposal, RepairScope
from vnalpha.closed_loop.policy import allowed_proposal_text

_EXPECTED_CHECKS = (
    "static_guard",
    "sandbox_execution",
    "output_schema",
    "artifact_manifest",
    "lineage",
    "quality_status",
    "caveats",
    "read_only_boundary",
)


def build_proposal(
    bundle: RepairBundle,
    scope: RepairScope,
    patch: str = "",
    suspected_cause: str = "",
    replacement_generated_code: str = "",
) -> RepairProposal:
    cause = suspected_cause.strip() or _default_cause(bundle)
    proposed_patch = patch.strip() or _default_patch(bundle, cause)
    accepted, findings = allowed_proposal_text(
        proposed_patch, replacement_generated_code
    )
    rejection_reason = (
        f"proposal includes prohibited trading/execution boundary behavior: {', '.join(findings)}"
        if not accepted
        else None
    )
    return RepairProposal(
        proposal_id=f"proposal-{uuid4().hex}",
        repair_id=bundle.repair_id,
        correlation_id=bundle.correlation_id,
        scope=scope,
        suspected_failure_cause=cause,
        proposed_patch=proposed_patch,
        replacement_generated_code=replacement_generated_code,
        expected_validation_checks=_EXPECTED_CHECKS,
        accepted=accepted,
        rejection_reason=rejection_reason,
    )


def _default_cause(bundle: RepairBundle) -> str:
    return (
        bundle.error_trace[:2_000]
        or "The failed research run requires bounded repair review."
    )


def _default_patch(bundle: RepairBundle, cause: str) -> str:
    return (
        f"Review {bundle.failed_job_id} in the sandbox; suspected cause: {cause[:500]}"
    )
