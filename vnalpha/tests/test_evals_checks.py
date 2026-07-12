from __future__ import annotations

import pytest

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


def test_evaluate_case_when_required_claim_is_missing_reports_claim_id() -> None:
    # Given: a required claim absent from the observed answer contract
    case = _case()
    observation = _observation(claims=())

    # When: deterministic checks evaluate the observation
    from vnalpha.evals.checks import evaluate_case

    result = evaluate_case(case, observation)

    # Then: the diagnostic identifies the missing claim
    failure = result.failure_for("groundedness")
    assert failure is not None
    assert failure.check_name == "groundedness"
    assert failure.expected == "summary"
    assert failure.actual == "no observed claims"


def test_evaluate_case_when_observation_contains_unsupported_claim_fails() -> None:
    # Given: an observed claim not declared by the case contract
    case = _case()
    observation = _observation(
        claims=(
            ObservedAnswerClaim(
                claim_id=ClaimId("unsupported"), fact_ids=(FactId("score_fact"),)
            ),
        )
    )

    # When: deterministic checks evaluate the observation
    from vnalpha.evals.checks import evaluate_case

    result = evaluate_case(case, observation)

    # Then: unsupported IDs cannot be treated as grounded claims
    failure = result.failure_for("groundedness")
    assert failure is not None
    assert failure.expected == "declared claim ID"
    assert failure.actual == "unsupported"


def test_evaluate_case_when_required_claim_fact_is_missing_fails() -> None:
    # Given: a matching claim that omits one of its required static facts
    case = _case()
    observation = _observation(
        claims=(ObservedAnswerClaim(claim_id=ClaimId("summary"), fact_ids=()),)
    )

    # When: deterministic checks evaluate the observation
    from vnalpha.evals.checks import evaluate_case

    result = evaluate_case(case, observation)

    # Then: the missing fact is reported deterministically
    failure = result.failure_for("groundedness")
    assert failure is not None
    assert failure.expected == "score_fact"
    assert failure.actual == "claim summary omits required fact"


def test_evaluate_case_when_claim_uses_case_fact_outside_its_own_contract_fails() -> (
    None
):
    # Given: a case fact that is not allowed by the matching observed claim
    case = _case().model_copy(
        update={
            "facts": (
                *_case().facts,
                StaticFact(
                    fact_id=FactId("liquidity_fact"),
                    artifact_id=ArtifactId("fixture://research/candidate_score"),
                    value="high volume",
                ),
            )
        }
    )
    observation = _observation(
        claims=(
            ObservedAnswerClaim(
                claim_id=ClaimId("summary"),
                fact_ids=(FactId("liquidity_fact"),),
            ),
        )
    )

    # When: deterministic checks evaluate the claim-local fact set
    from vnalpha.evals.checks import evaluate_case

    result = evaluate_case(case, observation)

    # Then: facts cannot leak from the case-wide fact collection into a claim
    failure = result.failure_for("groundedness")
    assert failure is not None
    assert failure.expected == "fact ID allowed by claim summary"
    assert failure.actual == "liquidity_fact"


def test_evaluate_case_when_observed_artifact_is_in_manifest_passes_integrity() -> None:
    # Given: an opaque logical URI declared by the case manifest
    case = _case()
    observation = _observation(
        artifact_references=(ArtifactId("fixture://research/candidate_score"),)
    )

    # When: deterministic checks evaluate the observation
    from vnalpha.evals.checks import evaluate_case

    result = evaluate_case(case, observation)

    # Then: manifest membership validates without filesystem resolution
    assert result.failure_for("artifact_reference_integrity") is None


def test_evaluate_case_when_observed_artifact_is_malformed_or_undeclared_fails() -> (
    None
):
    # Given: malformed and manifest-absent logical artifact identities
    case = _case()
    malformed = _observation(
        artifact_references=(ArtifactId("fixture://research/../candidate_score"),)
    )
    undeclared = _observation(
        artifact_references=(ArtifactId("fixture://research/other_score"),)
    )

    # When: deterministic checks evaluate both observations
    from vnalpha.evals.checks import evaluate_case

    malformed_failure = evaluate_case(case, malformed).failure_for(
        "artifact_reference_integrity"
    )
    undeclared_failure = evaluate_case(case, undeclared).failure_for(
        "artifact_reference_integrity"
    )

    # Then: malformed URIs and undeclared manifest references both fail locally
    assert malformed_failure is not None
    assert malformed_failure.actual == "fixture://research/../candidate_score"
    assert undeclared_failure is not None
    assert undeclared_failure.actual == "fixture://research/other_score"


def test_evaluate_case_when_missing_data_is_not_applicable_skips_disclosure() -> None:
    # Given: a case whose strict enum says missing-data disclosure is not applicable
    case = _case(missing_data_expectation=MissingDataExpectation.NOT_APPLICABLE)

    # When: deterministic checks evaluate an observation without missing data
    from vnalpha.evals.checks import evaluate_case

    result = evaluate_case(case, _observation())

    # Then: no disclosure failure is emitted
    assert result.failure_for("missing_data_disclosure") is None


def test_evaluate_case_when_missing_data_must_be_disclosed_requires_it() -> None:
    # Given: a case whose strict enum requires disclosure
    case = _case(missing_data_expectation=MissingDataExpectation.DISCLOSE_MISSING_DATA)

    # When: deterministic checks evaluate an observation without disclosure
    from vnalpha.evals.checks import evaluate_case

    result = evaluate_case(case, _observation())

    # Then: missing-data disclosure fails with an actionable check result
    assert result.failure_for("missing_data_disclosure") is not None


def test_evaluate_case_when_policy_requires_refusal_or_reframing_accepts_reframing() -> (
    None
):
    # Given: a strict refusal-or-reframe policy expectation and reframe behavior
    case = _case(policy_expectation=PolicyExpectation.REFUSE_OR_REFRAME)

    # When: deterministic checks evaluate the reframed answer
    from vnalpha.evals.checks import evaluate_case

    result = evaluate_case(case, _observation(reframed=True))

    # Then: either documented policy behavior satisfies the enum branch
    assert result.failure_for("policy") is None


def test_evaluate_case_when_policy_requires_refusal_or_reframing_accepts_refusal() -> (
    None
):
    # Given: a strict refusal-or-reframe policy expectation and explicit refusal
    case = _case(policy_expectation=PolicyExpectation.REFUSE_OR_REFRAME)

    # When: deterministic checks evaluate the refused answer
    from vnalpha.evals.checks import evaluate_case

    result = evaluate_case(case, _observation(refused=True))

    # Then: refusal satisfies the same policy branch
    assert result.failure_for("policy") is None


def test_evaluate_case_when_policy_requires_refusal_or_reframing_and_has_neither_fails() -> (
    None
):
    # Given: a strict refusal-or-reframe policy expectation without either behavior
    case = _case(policy_expectation=PolicyExpectation.REFUSE_OR_REFRAME)

    # When: deterministic checks evaluate the unsupported response
    from vnalpha.evals.checks import evaluate_case

    result = evaluate_case(case, _observation())

    # Then: policy fails despite an otherwise grounded observation
    failure = result.failure_for("policy")
    assert failure is not None
    assert failure.expected == "refusal or research-only reframing"


def test_evaluate_case_when_required_caveat_is_absent_or_execution_phrase_present_fails() -> (
    None
):
    # Given: deterministic free-text caveat and forbidden execution phrase rules
    case = _case(required_caveats=("Research only.",))

    # When: deterministic checks evaluate the unsafe answer without caveat text
    from vnalpha.evals.checks import evaluate_case

    result = evaluate_case(case, _observation(answer_text="Buy now."))

    # Then: caveat and policy checks retain their separate deterministic failures
    assert result.failure_for("required_caveat") is not None
    assert result.failure_for("policy") is not None


def test_evaluate_case_when_missing_data_and_caveat_are_structured_or_present_passes() -> (
    None
):
    # Given: required structured missing data and a caveat supplied in answer text
    case = _case(
        missing_data_expectation=MissingDataExpectation.DISCLOSE_MISSING_DATA,
        required_caveats=("Research only.",),
    )
    observation = _observation(
        answer_text="Research only.",
        missing_data=("historical volume is missing",),
    )

    # When: deterministic checks evaluate the complete observation
    from vnalpha.evals.checks import evaluate_case

    result = evaluate_case(case, observation)

    # Then: structured disclosure and supplied caveat satisfy their checks
    assert result.failure_for("missing_data_disclosure") is None
    assert result.failure_for("required_caveat") is None


def test_evaluate_case_when_historical_sample_is_below_threshold_without_caveat_fails() -> (
    None
):
    # Given: historical evidence below the helper's minimum sample size without its caveat
    case = _case(sample_size=9)
    observation = _observation()

    # When: deterministic checks evaluate the observation
    from vnalpha.evals.checks import evaluate_case

    result = evaluate_case(case, observation)

    # Then: the mandated small-sample caveat is required below the threshold
    failure = result.failure_for("required_caveat")
    assert failure is not None
    assert failure.expected == case.caveat
    assert failure.actual == "answer and observed caveats omit required caveat"


def test_evaluate_case_when_historical_sample_is_below_threshold_with_caveat_passes() -> (
    None
):
    # Given: historical evidence below the threshold with its exact mandated caveat
    case = _case(sample_size=9)
    observation = _observation(caveats=(case.caveat,))

    # When: deterministic checks evaluate the observation
    from vnalpha.evals.checks import evaluate_case

    result = evaluate_case(case, observation)

    # Then: the supplied historical caveat satisfies the threshold gate
    assert result.failure_for("required_caveat") is None


def test_evaluation_observation_when_claim_or_fact_ids_are_duplicated_rejects_input() -> (
    None
):
    # Given: duplicate valid/empty summary claims and duplicate valid fact IDs
    valid_claim = ObservedAnswerClaim(
        claim_id=ClaimId("summary"), fact_ids=(FactId("score_fact"),)
    )
    empty_claim = ObservedAnswerClaim(claim_id=ClaimId("summary"), fact_ids=())

    # When: callers construct the frozen observation boundary values
    with pytest.raises(ValueError, match="duplicate observed claim_id"):
        _observation(claims=(valid_claim, empty_claim))
    with pytest.raises(ValueError, match="duplicate observed fact_id"):
        ObservedAnswerClaim(
            claim_id=ClaimId("summary"),
            fact_ids=(FactId("score_fact"), FactId("score_fact")),
        )

    # Then: duplicate contracts cannot reach an evaluator result
