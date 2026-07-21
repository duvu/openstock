from __future__ import annotations

from vnalpha.evals.contracts import EvaluationObservation, ObservedAnswerClaim
from vnalpha.evals.identifiers import ArtifactId, ClaimId, FactId
from vnalpha.evals.models import (
    HistoricalEvidenceGoldenCase,
    MissingDataExpectation,
    OfflineEvaluationObservation,
    OfflineObservedAnswerClaim,
    PolicyExpectation,
    RequiredAnswerClaim,
    StaticFact,
)


def _case(
    *,
    policy_expectation: PolicyExpectation = PolicyExpectation.RESEARCH_ONLY,
    missing_data_expectation: MissingDataExpectation = MissingDataExpectation.NOT_APPLICABLE,
    required_caveats: tuple[str, ...] = (),
    sample_size: int = 10,
) -> HistoricalEvidenceGoldenCase:
    return HistoricalEvidenceGoldenCase(
        case_id="claim-contract",
        family="historical_evidence",
        input="Explain research evidence.",
        expected_intent="explain_symbol",
        required_tools=(),
        required_claims=(
            RequiredAnswerClaim(
                claim_id=ClaimId("summary"), fact_ids=(FactId("score_fact"),)
            ),
        ),
        facts=(
            StaticFact(
                fact_id=FactId("score_fact"),
                artifact_id=ArtifactId("fixture://research/candidate_score"),
                value="72",
            ),
        ),
        forbidden_phrases=(),
        required_caveats=required_caveats,
        artifact_manifest=(ArtifactId("fixture://research/candidate_score"),),
        observation=OfflineEvaluationObservation(
            answer_text="Research summary.",
            caveats=(),
            missing_data=(),
            observed_claims=(
                OfflineObservedAnswerClaim(
                    claim_id=ClaimId("summary"),
                    fact_ids=(FactId("score_fact"),),
                ),
            ),
            artifact_references=(),
            refused=False,
            reframed=False,
        ),
        missing_data_expectation=missing_data_expectation,
        policy_expectation=policy_expectation,
        sample_size=sample_size,
        minimum_sample_size=10,
        caveat="Small sample; interpret carefully.",
    )


def _observation(
    *,
    claims: tuple[ObservedAnswerClaim, ...] = (
        ObservedAnswerClaim(
            claim_id=ClaimId("summary"), fact_ids=(FactId("score_fact"),)
        ),
    ),
    artifact_references: tuple[ArtifactId, ...] = (),
    answer_text: str = "Research summary.",
    caveats: tuple[str, ...] = (),
    missing_data: tuple[str, ...] = (),
    refused: bool = False,
    reframed: bool = False,
) -> EvaluationObservation:
    return EvaluationObservation(
        answer_text=answer_text,
        caveats=caveats,
        missing_data=missing_data,
        observed_claims=claims,
        artifact_references=artifact_references,
        refused=refused,
        reframed=reframed,
    )


def test_evaluate_case_when_claim_and_fact_ids_match_passes_without_answer_value_matching() -> (
    None
):
    # Given: answer text without the fact value but with a matching typed claim/fact pair
    case = _case()
    observation = _observation(answer_text="Summary is available.")

    # When: deterministic checks evaluate the observation
    from vnalpha.evals.checks import evaluate_case

    result = evaluate_case(case, observation)

    # Then: grounding is based on IDs rather than free-text fact values
    assert result.failure_for("groundedness") is None

    # Then: duplicate contracts cannot reach an evaluator result
