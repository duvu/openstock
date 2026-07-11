from __future__ import annotations

from pathlib import Path

import pytest


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


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("missing_data_expectation", "unsupported"),
        ("policy_expectation", "unsafe"),
    ],
)
def test_load_golden_cases_when_enum_is_unknown_rejects_fixture(
    tmp_path: Path, field: str, replacement: str
) -> None:
    # Given: a fixture with an unsupported semantic enum value
    document = _case_document("invalid-enum", "research_answer").replace(
        f"{field}: "
        + (
            "disclose_missing_data"
            if field == "missing_data_expectation"
            else "research_only"
        ),
        f"{field}: {replacement}",
    )
    path = _write_case(tmp_path / "invalid-enum.yaml", document)

    # When: validation loads the fixture
    from vnalpha.evals.errors import GoldenCaseValidationError
    from vnalpha.evals.loader import load_golden_cases

    # Then: arbitrary strings cannot enter policy or missing-data semantics
    with pytest.raises(GoldenCaseValidationError, match=field):
        load_golden_cases((path,))


@pytest.mark.parametrize(
    ("needle", "replacement", "match"),
    [
        (
            "- fixture://research/candidate_score",
            "- fixture://research/../candidate_score",
            "artifact_manifest",
        ),
        (
            "      - summary_fact",
            "      - missing_fact",
            "missing_fact",
        ),
        (
            "      - summary_fact",
            "      - summary_fact\n      - summary_fact",
            "duplicate fact_id in claim",
        ),
        (
            "artifact_id: fixture://research/candidate_score",
            "artifact_id: fixture://research/other_score",
            "other_score",
        ),
        (
            "claim_id: summary",
            "claim_id: ",
            "claim_id",
        ),
        (
            "fact_id: summary_fact",
            "fact_id: summary-id",
            "invalid logical identifier",
        ),
        (
            "  - fact_id: summary_fact\n"
            "    artifact_id: fixture://research/candidate_score\n"
            "    value: Current score is 72.",
            "  - fact_id: summary_fact\n"
            "    artifact_id: fixture://research/candidate_score\n"
            "    value: Current score is 72.\n"
            "  - fact_id: summary_fact\n"
            "    artifact_id: fixture://research/candidate_score\n"
            "    value: Duplicate.",
            "duplicate fact_id",
        ),
        (
            "  - claim_id: summary\n    fact_ids:\n      - summary_fact",
            "  - claim_id: summary\n    fact_ids:\n      - summary_fact\n"
            "  - claim_id: summary\n    fact_ids:\n      - summary_fact",
            "duplicate claim_id",
        ),
        (
            "  - fixture://research/candidate_score",
            "  - fixture://research/candidate_score\n"
            "  - fixture://research/candidate_score",
            "duplicate artifact_manifest",
        ),
    ],
)
def test_load_golden_cases_when_identifiers_or_references_are_invalid_rejects_fixture(
    tmp_path: Path, needle: str, replacement: str, match: str
) -> None:
    # Given: a fixture with malformed identity, duplicate ID, or missing fact reference
    path = _write_case(
        tmp_path / "invalid.yaml",
        _case_document("invalid-reference", "research_answer").replace(
            needle, replacement
        ),
    )

    # When: the strict local schema validates it
    from vnalpha.evals.errors import GoldenCaseValidationError
    from vnalpha.evals.loader import load_golden_cases

    # Then: invalid identity graphs are rejected at the boundary
    with pytest.raises(GoldenCaseValidationError, match=match):
        load_golden_cases((path,))


def test_load_golden_cases_when_legacy_fields_are_supplied_rejects_fixture(
    tmp_path: Path,
) -> None:
    # Given: a pre-refactor fixture field that no longer belongs in the schema
    path = _write_case(
        tmp_path / "legacy.yaml",
        _case_document("legacy", "research_answer") + "required_fields: []\n",
    )

    # When: the strict schema validates the fixture
    from vnalpha.evals.errors import GoldenCaseValidationError
    from vnalpha.evals.loader import load_golden_cases

    # Then: untyped answer-field grounding cannot re-enter the contract
    with pytest.raises(GoldenCaseValidationError, match="required_fields"):
        load_golden_cases((path,))


def test_default_golden_corpus_when_all_five_family_seeds_are_valid_passes() -> None:
    # Given: the fixed, self-contained corpus contains one seed for every family
    from vnalpha.evals.runner import DEFAULT_GOLDENS_ROOT, run_golden_corpus

    # When: the public default runner evaluates its fixed root
    report = run_golden_corpus()

    # Then: exactly the five supported family seeds pass without operational failures
    assert DEFAULT_GOLDENS_ROOT.exists()
    assert report.source_count == 5
    assert report.case_count == 5
    assert report.passed_case_count == 5
    assert report.failure_count == 0
    assert {evaluation.path.parent.name for evaluation in report.evaluations} == {
        "research_answers",
        "scenario_plans",
        "policy_refusals",
        "historical_evidence",
        "shortlist",
    }


def test_failing_golden_corpus_when_all_regressions_are_evaluated_reports_each_failure() -> (
    None
):
    # Given: parseable negative fixtures isolated outside the default family directories
    from vnalpha.evals.runner import DEFAULT_GOLDENS_ROOT

    failing_root = DEFAULT_GOLDENS_ROOT / "failing"

    # When: the private root API evaluates every negative fixture without stopping
    from vnalpha.evals.runner import run_golden_corpus

    report = run_golden_corpus(failing_root)

    # Then: each required regression failure is reported from an evaluated case
    failures_by_case = {
        failure.case_id: failure.check_name for failure in report.all_failures()
    }
    assert report.source_count == 5
    assert report.case_count == 5
    assert report.passed_case_count == 0
    assert failures_by_case == {
        "unsupported-metric-claim": "groundedness",
        "missing-historical-caveat": "required_caveat",
        "missing-artifact-reference": "artifact_reference_integrity",
        "execution-wording": "policy",
        "unsafe-prompt-without-refusal": "policy",
    }
