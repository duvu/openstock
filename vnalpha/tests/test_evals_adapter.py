from __future__ import annotations

from pathlib import Path

import pytest


def _case_document() -> str:
    return """\
case_id: research_adapter
family: research_answer
input: Explain the evidence.
expected_intent: explain_symbol
required_tools: []
required_claims:
  - claim_id: summary
    fact_ids:
      - summary_fact
facts:
  - fact_id: summary_fact
    artifact_id: fixture://research/candidate_score
    value: Current score is 72.
forbidden_phrases: []
required_caveats: []
artifact_manifest:
  - fixture://research/candidate_score
observation:
  answer_text: Current score is 72.
  caveats:
    - Research only.
  missing_data: []
  observed_claims:
    - claim_id: summary
      fact_ids:
        - summary_fact
  artifact_references:
    - fixture://research/candidate_score
  refused: false
  reframed: false
missing_data_expectation: not_applicable
policy_expectation: research_only
"""


def test_adapt_observation_when_typed_fixture_is_valid_copies_only_local_values(
    tmp_path: Path,
) -> None:
    # Given: a self-contained golden case observation with typed identity values
    path = tmp_path / "research.yaml"
    path.write_text(_case_document(), encoding="utf-8")

    # When: the pure adapter converts the loaded fixture observation
    from vnalpha.evals.adapter import adapt_observation
    from vnalpha.evals.loader import load_golden_case

    observation = adapt_observation(load_golden_case(path))

    # Then: all runtime values come from the YAML contract without external access
    assert observation.answer_text == "Current score is 72."
    assert observation.observed_claims[0].claim_id == "summary"
    assert observation.observed_claims[0].fact_ids == ("summary_fact",)
    assert observation.artifact_references == ("fixture://research/candidate_score",)


def test_load_golden_case_when_observation_claim_id_is_invalid_rejects_boundary(
    tmp_path: Path,
) -> None:
    # Given: an otherwise valid case with an invalid observed logical claim identity
    path = tmp_path / "invalid.yaml"
    path.write_text(
        _case_document().replace("claim_id: summary\n      fact_ids", "claim_id: Bad-ID\n      fact_ids", 1),
        encoding="utf-8",
    )

    # When: the single-case loader parses the offline boundary
    from vnalpha.evals.errors import GoldenCaseValidationError
    from vnalpha.evals.loader import load_golden_case

    # Then: invalid observed identities are rejected before evaluation
    with pytest.raises(GoldenCaseValidationError, match="invalid logical identifier"):
        load_golden_case(path)


@pytest.mark.parametrize(
    ("field", "invalid_boolean"),
    (("refused", '"false"'), ("refused", "0"), ("reframed", '"false"'), ("reframed", "0")),
)
def test_load_golden_case_when_observation_boolean_is_coerced_rejects_boundary(
    tmp_path: Path, field: str, invalid_boolean: str
) -> None:
    # Given: an otherwise valid fixture with a non-boolean observation flag
    path = tmp_path / "invalid-boolean.yaml"
    path.write_text(
        _case_document().replace(f"{field}: false", f"{field}: {invalid_boolean}"),
        encoding="utf-8",
    )

    # When: the offline observation is parsed at the YAML boundary
    from vnalpha.evals.errors import GoldenCaseValidationError
    from vnalpha.evals.loader import load_golden_case

    # Then: strings and numeric zero cannot be silently coerced to false
    with pytest.raises(GoldenCaseValidationError, match=f"observation.{field}"):
        load_golden_case(path)
