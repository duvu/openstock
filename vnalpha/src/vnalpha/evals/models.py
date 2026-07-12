"""Frozen Pydantic schemas for research-evaluation golden cases."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, TypeAlias

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

from vnalpha.evals.identifiers import (
    ArtifactId,
    ClaimId,
    FactId,
    parse_fixture_uri,
    parse_logical_identifier,
)


class MissingDataExpectation(str, Enum):
    """Whether the case requires a missing-data disclosure."""

    NOT_APPLICABLE = "not_applicable"
    DISCLOSE_MISSING_DATA = "disclose_missing_data"


class PolicyExpectation(str, Enum):
    """Expected answer safety behavior for a golden case."""

    RESEARCH_ONLY = "research_only"
    REFUSE_OR_REFRAME = "refuse_or_reframe"


class GoldenCaseReferenceError(ValueError):
    """Raised when claim, fact, or artifact identities are inconsistent."""


class RequiredAnswerClaim(BaseModel):
    """A required answer claim and its backing static facts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: ClaimId
    fact_ids: tuple[FactId, ...] = Field(min_length=1)

    @field_validator("claim_id")
    @classmethod
    def _validate_claim_id(cls, claim_id: ClaimId) -> ClaimId:
        return ClaimId(parse_logical_identifier(claim_id))

    @field_validator("fact_ids")
    @classmethod
    def _validate_fact_ids_syntax(
        cls, fact_ids: tuple[FactId, ...]
    ) -> tuple[FactId, ...]:
        return tuple(FactId(parse_logical_identifier(fact_id)) for fact_id in fact_ids)

    @model_validator(mode="after")
    def _validate_fact_ids(self) -> RequiredAnswerClaim:
        _require_unique(self.fact_ids, f"fact_id in claim {self.claim_id}")
        return self


class StaticFact(BaseModel):
    """A static fact available to a required answer claim."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fact_id: FactId
    artifact_id: ArtifactId
    value: StrictStr = Field(min_length=1)

    @field_validator("fact_id")
    @classmethod
    def _validate_fact_id(cls, fact_id: FactId) -> FactId:
        return FactId(parse_logical_identifier(fact_id))

    @field_validator("artifact_id")
    @classmethod
    def _validate_artifact_id(cls, artifact_id: ArtifactId) -> ArtifactId:
        parse_fixture_uri(artifact_id)
        return artifact_id


class OfflineObservedAnswerClaim(BaseModel):
    """One YAML-declared answer claim linked to local fact identities."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: ClaimId
    fact_ids: tuple[FactId, ...]

    @field_validator("claim_id")
    @classmethod
    def _validate_claim_id(cls, claim_id: ClaimId) -> ClaimId:
        return ClaimId(parse_logical_identifier(claim_id))

    @field_validator("fact_ids")
    @classmethod
    def _validate_fact_ids(cls, fact_ids: tuple[FactId, ...]) -> tuple[FactId, ...]:
        parsed = tuple(
            FactId(parse_logical_identifier(fact_id)) for fact_id in fact_ids
        )
        _require_unique(parsed, "observed fact_id")
        return parsed


class OfflineEvaluationObservation(BaseModel):
    """Frozen, self-contained observation loaded from a golden-case YAML file."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    answer_text: StrictStr
    caveats: tuple[StrictStr, ...]
    missing_data: tuple[StrictStr, ...]
    observed_claims: tuple[OfflineObservedAnswerClaim, ...]
    artifact_references: tuple[ArtifactId, ...]
    refused: StrictBool
    reframed: StrictBool

    @field_validator("artifact_references")
    @classmethod
    def _validate_artifact_references(
        cls, references: tuple[ArtifactId, ...]
    ) -> tuple[ArtifactId, ...]:
        for reference in references:
            parse_fixture_uri(reference)
        _require_unique(references, "observed artifact_reference")
        return references

    @model_validator(mode="after")
    def _validate_claim_ids(self) -> OfflineEvaluationObservation:
        _require_unique(
            tuple(claim.claim_id for claim in self.observed_claims),
            "observed claim_id",
        )
        return self


class GoldenCaseBase(BaseModel):
    """Fields required by every local golden-case fixture."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: StrictStr = Field(min_length=1)
    input: StrictStr = Field(min_length=1)
    expected_intent: StrictStr = Field(min_length=1)
    required_tools: tuple[StrictStr, ...]
    required_claims: tuple[RequiredAnswerClaim, ...]
    facts: tuple[StaticFact, ...]
    forbidden_phrases: tuple[StrictStr, ...]
    required_caveats: tuple[StrictStr, ...]
    artifact_manifest: tuple[ArtifactId, ...]
    observation: OfflineEvaluationObservation
    missing_data_expectation: MissingDataExpectation
    policy_expectation: PolicyExpectation

    @field_validator("artifact_manifest")
    @classmethod
    def _validate_artifact_manifest(
        cls, artifacts: tuple[ArtifactId, ...]
    ) -> tuple[ArtifactId, ...]:
        for artifact in artifacts:
            parse_fixture_uri(artifact)
        return artifacts

    @model_validator(mode="after")
    def _validate_identity_graph(self) -> GoldenCaseBase:
        _require_unique(
            tuple(claim.claim_id for claim in self.required_claims), "claim_id"
        )
        fact_ids = tuple(fact.fact_id for fact in self.facts)
        _require_unique(fact_ids, "fact_id")
        _require_unique(self.artifact_manifest, "artifact_manifest")
        for claim in self.required_claims:
            for fact_id in claim.fact_ids:
                if fact_id not in fact_ids:
                    raise GoldenCaseReferenceError(
                        f"claim {claim.claim_id} references unknown fact_id {fact_id}"
                    )
        for fact in self.facts:
            if fact.artifact_id not in self.artifact_manifest:
                raise GoldenCaseReferenceError(
                    f"fact {fact.fact_id} references undeclared artifact_id {fact.artifact_id}"
                )
        return self


def _require_unique(values: tuple[str, ...], name: str) -> None:
    for value in values:
        if values.count(value) > 1:
            raise GoldenCaseReferenceError(f"duplicate {name}: {value}")


class ResearchAnswerGoldenCase(GoldenCaseBase):
    """Golden fixture for a grounded research answer."""

    family: Literal["research_answer"]


class ScenarioPlanGoldenCase(GoldenCaseBase):
    """Golden fixture for a monitored research scenario."""

    family: Literal["scenario_plan"]
    monitoring: StrictStr = Field(min_length=1)
    confirmation: StrictStr = Field(min_length=1)
    invalidation: StrictStr = Field(min_length=1)


class PolicyRefusalGoldenCase(GoldenCaseBase):
    """Golden fixture for refusal and research-only reframing."""

    family: Literal["policy_refusal"]
    refusal: StrictStr = Field(min_length=1)
    reframing: StrictStr = Field(min_length=1)


class HistoricalEvidenceGoldenCase(GoldenCaseBase):
    """Golden fixture for historical evidence with sample-size context."""

    family: Literal["historical_evidence"]
    sample_size: StrictInt = Field(ge=0)
    minimum_sample_size: StrictInt = Field(ge=1)
    caveat: StrictStr = Field(min_length=1)


class ShortlistGoldenCase(GoldenCaseBase):
    """Golden fixture for research-only shortlist output."""

    family: Literal["shortlist"]
    research_only_constraints: tuple[StrictStr, ...] = Field(min_length=1)


GoldenCase: TypeAlias = Annotated[
    ResearchAnswerGoldenCase
    | ScenarioPlanGoldenCase
    | PolicyRefusalGoldenCase
    | HistoricalEvidenceGoldenCase
    | ShortlistGoldenCase,
    Field(discriminator="family"),
]
