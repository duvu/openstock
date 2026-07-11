"""Pure conversion of a YAML observation into runtime evaluation contracts."""

from __future__ import annotations

from vnalpha.evals.contracts import EvaluationObservation, ObservedAnswerClaim
from vnalpha.evals.models import GoldenCase


def adapt_observation(case: GoldenCase) -> EvaluationObservation:
    """Copy the validated offline observation from a golden case without I/O."""

    source = case.observation
    return EvaluationObservation(
        answer_text=source.answer_text,
        caveats=source.caveats,
        missing_data=source.missing_data,
        observed_claims=tuple(
            ObservedAnswerClaim(
                claim_id=claim.claim_id,
                fact_ids=claim.fact_ids,
            )
            for claim in source.observed_claims
        ),
        artifact_references=source.artifact_references,
        refused=source.refused,
        reframed=source.reframed,
    )
