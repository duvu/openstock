from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, ClassVar, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StringConstraints

JsonObject: TypeAlias = dict[str, JsonValue]
RedactionStatus: TypeAlias = Literal["redacted", "metadata", "full"]
SafeId: TypeAlias = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    ),
]


class LifecycleState(str, Enum):
    RUN = "RUN"
    OBSERVE = "OBSERVE"
    PACKAGE = "PACKAGE"
    AI_FIX = "AI_FIX"
    VALIDATE = "VALIDATE"
    PROMOTE_READY = "PROMOTE_READY"
    PROMOTED = "PROMOTED"
    REJECTED = "REJECTED"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED = "FAILED"


ClosedLoopLifecycleState = LifecycleState


class RepairScope(str, Enum):
    SANDBOX_RESEARCH_CODE = "sandbox_research_code"
    EXPERIMENT_DEFINITION = "experiment_definition"
    FEATURE_DEFINITION = "feature_definition"
    VALIDATION_SCHEMA = "validation_schema"


class PromotableArtifactType(str, Enum):
    INDICATOR_DEFINITION = "indicator_definition"
    FEATURE_DEFINITION = "feature_definition"
    EXPERIMENT_TEMPLATE = "experiment_template"
    PATTERN_SCANNER_DEFINITION = "pattern_scanner_definition"
    OFFLINE_EVENT_STUDY_TEMPLATE = "offline_event_study_template"


class _FrozenModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True, extra="forbid", strict=True
    )


class RepairBundle(_FrozenModel):
    repair_id: SafeId
    correlation_id: SafeId
    failed_job_id: SafeId
    failed_session_id: SafeId | None = None
    user_request: str = Field(default="", max_length=20_000)
    plan_summary: str = Field(default="", max_length=20_000)
    generated_code: str = Field(default="", max_length=100_000)
    static_guard_result: JsonObject
    stdout: str = Field(default="", max_length=50_000)
    stderr: str = Field(default="", max_length=50_000)
    error_trace: str = Field(default="", max_length=50_000)
    input_dataset_references: tuple[str, ...] = ()
    artifact_manifest: JsonObject
    output_state: JsonObject
    validation_result: JsonObject
    environment_summary: JsonObject
    redaction_status: RedactionStatus
    run_id: SafeId | None = None
    artifact_id: SafeId | None = None
    experiment_id: SafeId | None = None
    feature_id: SafeId | None = None
    hypothesis_id: SafeId | None = None
    pattern_id: SafeId | None = None


class RepairProposal(_FrozenModel):
    proposal_id: SafeId
    repair_id: SafeId
    correlation_id: SafeId
    scope: RepairScope
    suspected_failure_cause: str = Field(min_length=1, max_length=20_000)
    proposed_patch: str = Field(default="", max_length=100_000)
    replacement_generated_code: str = Field(default="", max_length=100_000)
    expected_validation_checks: tuple[str, ...]
    accepted: bool
    rejection_reason: str | None = Field(default=None, max_length=2_000)


class SandboxAttemptResult(_FrozenModel):
    passed: bool
    stdout: str = Field(default="", max_length=50_000)
    stderr: str = Field(default="", max_length=50_000)
    error_trace: str = Field(default="", max_length=50_000)
    artifact_id: SafeId | None = None


class RepairAttempt(_FrozenModel):
    attempt_id: SafeId
    repair_id: SafeId
    attempt: int = Field(ge=1, le=100)
    sandbox_only: Literal[True] = True
    passed: bool
    stdout: str = Field(default="", max_length=50_000)
    stderr: str = Field(default="", max_length=50_000)
    error_trace: str = Field(default="", max_length=50_000)
    artifact_id: SafeId | None = None
    created_at: str


class LifecycleRecord(_FrozenModel):
    repair_id: SafeId
    state: LifecycleState
    correlation_id: SafeId
    run_id: SafeId | None = None
    sandbox_job_id: SafeId | None = None
    research_experiment_id: SafeId | None = None
    feature_id: SafeId | None = None
    hypothesis_id: SafeId | None = None
    pattern_id: SafeId | None = None
    artifact_id: SafeId | None = None
    created_at: str
    detail: str = Field(default="", max_length=2_000)


class ValidationCheck(_FrozenModel):
    name: str = Field(min_length=1, max_length=128)
    passed: bool
    detail: str = Field(default="", max_length=2_000)


class ValidationReport(_FrozenModel):
    artifact_id: SafeId
    correlation_id: SafeId
    checks: tuple[ValidationCheck, ...]
    passed: bool
    created_at: str
    artifact_digest: str = ""
    artifact_root: str | None = None

    def check(self, name: str) -> ValidationCheck:
        for check in self.checks:
            if check.name == name:
                return check
        return ValidationCheck(name=name, passed=False, detail="check not recorded")


class PromotionVerification(_FrozenModel):
    candidate: SafeId
    deployment_id: SafeId
    correlation_id: SafeId
    candidate_type: PromotableArtifactType
    validation_report_id: SafeId
    artifact_digest: str = ""
    artifact_root: str | None = Field(default=None, max_length=1_000)
    passed: bool
    created_at: str


class DeploymentState(_FrozenModel):
    deployment_id: SafeId
    candidate: SafeId
    candidate_type: PromotableArtifactType
    correlation_id: SafeId
    validation_report_id: SafeId
    artifact_root: str | None = Field(default=None, max_length=1_000)
    previous_candidate: SafeId | None = None
    status: Literal["VERIFIED", "PROMOTED", "ROLLED_BACK"]
    created_at: str
    updated_at: str
    rollback_reason: str | None = Field(default=None, max_length=2_000)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
