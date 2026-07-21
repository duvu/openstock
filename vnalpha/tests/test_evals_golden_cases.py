from __future__ import annotations

from pathlib import Path


def _write_case(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def _case_document(case_id: str, family: str) -> str:
    return f"""\
case_id: {case_id}
family: {family}
input: Explain the current research evidence.
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
forbidden_phrases:
  - guaranteed
required_caveats: []
artifact_manifest:
  - fixture://research/candidate_score
observation:
  answer_text: Current score is 72.
  caveats: []
  missing_data: []
  observed_claims:
    - claim_id: observed_summary
      fact_ids:
        - observed_fact
  artifact_references:
    - fixture://observation/local
  refused: false
  reframed: false
missing_data_expectation: disclose_missing_data
policy_expectation: research_only
"""


def test_load_golden_cases_when_fixture_uri_and_references_are_valid_loads_case(
    tmp_path: Path,
) -> None:
    # Given: a fixture with logical artifact identity and valid claim/fact references
    path = _write_case(
        tmp_path / "research.yaml", _case_document("research-1", "research_answer")
    )

    # When: the typed fixture is loaded locally
    from vnalpha.evals.identifiers import parse_fixture_uri
    from vnalpha.evals.loader import load_golden_cases

    case = load_golden_cases((path,))[0]

    # Then: the opaque URI parses without becoming a filesystem path
    uri = parse_fixture_uri(case.artifact_manifest[0])
    assert uri.authority == "research"
    assert uri.logical_name == "candidate_score"
    assert case.required_claims[0].fact_ids == ("summary_fact",)
