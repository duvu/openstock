from __future__ import annotations

from pathlib import Path


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
