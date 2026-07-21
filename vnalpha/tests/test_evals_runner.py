from __future__ import annotations

from pathlib import Path


def _case_document(case_id: str, answer_text: str = "Current score is 72.") -> str:
    return f"""\
case_id: {case_id}
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
  answer_text: {answer_text}
  caveats: []
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


def test_run_golden_corpus_when_case_passes_and_case_fails_collects_both(
    tmp_path: Path,
) -> None:
    # Given: deterministic research-answer fixtures with one safe and one unsafe answer
    root = tmp_path / "goldens"
    family = root / "research_answers"
    family.mkdir(parents=True)
    (family / "pass.yaml").write_text(_case_document("pass_case"), encoding="utf-8")
    (family / "fail.yaml").write_text(
        _case_document("fail_case", "Buy now."), encoding="utf-8"
    )

    # When: the offline runner evaluates every discovered file
    from vnalpha.evals.runner import run_golden_corpus

    report = run_golden_corpus(root)

    # Then: a failing check does not prevent the passing case from being retained
    assert report.case_count == 2
    assert report.passed_case_count == 1
    assert report.failed_case_count == 1
    assert report.failure_count == 1
    assert report.evaluations[0].path.name == "fail.yaml"
    assert report.evaluations[1].path.name == "pass.yaml"
