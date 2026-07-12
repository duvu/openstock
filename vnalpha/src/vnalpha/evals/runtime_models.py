from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TypeAlias

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StrictBool,
    StrictFloat,
    StrictStr,
    field_validator,
    model_validator,
)

from vnalpha.assistant.tool_policy import is_safe_tool
from vnalpha.evals.identifiers import ArtifactId, parse_fixture_uri

JsonObject: TypeAlias = dict[str, JsonValue]


class RuntimeOutcome(str, Enum):
    ANSWER = "answer"
    REFUSAL = "refusal"
    VALIDATION_ERROR = "validation_error"


class AuditExpectation(str, Enum):
    PERSISTED = "persisted"
    ABSENT = "absent"


class ValidationStatus(str, Enum):
    PASS = "PASS"
    PARTIAL = "PARTIAL"
    FAIL = "FAIL"


class RuntimeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class RuntimeRequest(RuntimeModel):
    current_user_prompt: StrictStr = Field(min_length=1)
    workspace_context: StrictStr | None = None
    date: StrictStr | None = None


class RuntimeClassifierResponse(RuntimeModel):
    intent: StrictStr = Field(min_length=1)
    confidence: StrictFloat = Field(ge=0.0, le=1.0)
    entities: JsonObject
    needs_clarification: StrictBool
    clarification_question: StrictStr | None
    safety_flags: tuple[StrictStr, ...]


class RuntimeSynthesisResponse(RuntimeModel):
    summary: StrictStr
    basis: StrictStr
    risks_caveats: StrictStr
    tool_trace_summary: StrictStr
    missing_data: tuple[StrictStr, ...]
    grounded_source_refs: tuple[StrictStr, ...]
    research_metadata: JsonObject
    raw_tool_outputs: JsonObject = Field(default_factory=dict)


class SeededToolOutput(RuntimeModel):
    tool_name: StrictStr = Field(min_length=1)
    arguments: JsonObject
    data: JsonObject
    artifact_refs: tuple[ArtifactId, ...]
    summary: StrictStr
    warnings: tuple[StrictStr, ...]

    @field_validator("tool_name")
    @classmethod
    def _validate_tool_name(cls, tool_name: str) -> str:
        if not is_safe_tool(tool_name):
            msg = f"runtime replay tool is not policy-approved: {tool_name}"
            raise ValueError(msg)
        return tool_name

    @field_validator("artifact_refs")
    @classmethod
    def _validate_artifact_refs(
        cls, artifact_refs: tuple[ArtifactId, ...]
    ) -> tuple[ArtifactId, ...]:
        for artifact_ref in artifact_refs:
            parse_fixture_uri(artifact_ref)
        if len(set(artifact_refs)) != len(artifact_refs):
            msg = "runtime replay artifact_refs must be unique"
            raise ValueError(msg)
        return artifact_refs


class ExpectedPlanStep(RuntimeModel):
    tool_name: StrictStr = Field(min_length=1)
    arguments: JsonObject


class ExpectedRuntimeOutcome(RuntimeModel):
    outcome: RuntimeOutcome
    intent: StrictStr = Field(min_length=1)
    plan: tuple[ExpectedPlanStep, ...]
    successful_trace_tools: tuple[StrictStr, ...]
    groundedness_status: ValidationStatus | None
    policy_status: ValidationStatus | None
    fallback_used: StrictBool | None
    audit_status: AuditExpectation
    required_missing_data: tuple[StrictStr, ...]
    forbidden_source_refs: tuple[StrictStr, ...]
    claim_source_refs: dict[StrictStr, tuple[ArtifactId, ...]]
    validation_error_contains: StrictStr | None = None

    @field_validator("claim_source_refs")
    @classmethod
    def _validate_claim_source_refs(
        cls, claim_source_refs: dict[str, tuple[ArtifactId, ...]]
    ) -> dict[str, tuple[ArtifactId, ...]]:
        for artifact_refs in claim_source_refs.values():
            for artifact_ref in artifact_refs:
                parse_fixture_uri(artifact_ref)
        return claim_source_refs


class RuntimeReplayCase(RuntimeModel):
    case_id: StrictStr = Field(pattern=r"[a-z][a-z0-9_-]*\z")
    request: RuntimeRequest
    classifier_response: RuntimeClassifierResponse | None
    synthesis_response: RuntimeSynthesisResponse | None
    tool_outputs: tuple[SeededToolOutput, ...]
    expected: ExpectedRuntimeOutcome

    @model_validator(mode="after")
    def _validate_replay_graph(self) -> RuntimeReplayCase:
        tool_names = tuple(seed.tool_name for seed in self.tool_outputs)
        if len(set(tool_names)) != len(tool_names):
            msg = "runtime replay tool_outputs must use unique tool names"
            raise ValueError(msg)
        expected_tools = tuple(step.tool_name for step in self.expected.plan)
        if expected_tools != tool_names:
            msg = "expected plan tools must match seeded tool output order"
            raise ValueError(msg)
        if self.expected.outcome is RuntimeOutcome.ANSWER:
            if self.classifier_response is None or self.synthesis_response is None:
                msg = "answer cases require classifier and synthesis responses"
                raise ValueError(msg)
        if (
            self.expected.outcome is RuntimeOutcome.VALIDATION_ERROR
            and self.expected.validation_error_contains is None
        ):
            msg = "validation-error cases require validation_error_contains"
            raise ValueError(msg)
        return self


class ObservedValidationMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, strict=True)

    status: ValidationStatus


class ObservedResearchMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, strict=True)

    groundedness: ObservedValidationMetadata | None = None
    policy: ObservedValidationMetadata | None = None
    fallback_used: StrictBool | None = None
    claim_source_refs: dict[StrictStr, tuple[ArtifactId, ...]] = Field(
        default_factory=dict
    )


@dataclass(frozen=True, slots=True)
class RuntimeReplayLoadError(Exception):
    path: Path
    detail: str

    def __str__(self) -> str:
        return f"Runtime replay fixture {self.path}: {self.detail}"


@dataclass(frozen=True, slots=True)
class RuntimeReplayValidationError(RuntimeReplayLoadError):
    pass
