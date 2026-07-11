"""Pure artifact-manifest integrity checks."""

from __future__ import annotations

from vnalpha.evals.contracts import (
    CheckResult,
    EvaluationObservation,
    failed_check,
)
from vnalpha.evals.identifiers import InvalidFixtureUriError, parse_fixture_uri
from vnalpha.evals.models import GoldenCase


def check_artifact_reference_integrity(
    case: GoldenCase, observation: EvaluationObservation
) -> CheckResult:
    """Validate observed logical URIs only against the case-local manifest."""

    for reference in observation.artifact_references:
        try:
            parse_fixture_uri(reference)
        except InvalidFixtureUriError:
            return failed_check(
                case.case_id,
                "artifact_reference_integrity",
                "a logical fixture URI",
                reference,
            )
        if reference not in case.artifact_manifest:
            return failed_check(
                case.case_id,
                "artifact_reference_integrity",
                "case artifact manifest URI",
                reference,
            )
    return CheckResult(name="artifact_reference_integrity")
