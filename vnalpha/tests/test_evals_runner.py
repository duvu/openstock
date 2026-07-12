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


def test_run_golden_corpus_when_empty_or_unsafe_path_records_discovery_failure(
    tmp_path: Path,
) -> None:
    # Given: an empty corpus and a corpus containing a YAML symlink escaping its root
    empty_root = tmp_path / "empty"
    empty_root.mkdir()
    unsafe_root = tmp_path / "unsafe"
    unsafe_family = unsafe_root / "research_answers"
    unsafe_family.mkdir(parents=True)
    outside = tmp_path / "outside.yaml"
    outside.write_text(_case_document("outside"), encoding="utf-8")
    (unsafe_family / "escape.yaml").symlink_to(outside)

    # When: discovery visits each supplied private root
    from vnalpha.evals.runner import run_golden_corpus

    empty_report = run_golden_corpus(empty_root)
    unsafe_report = run_golden_corpus(unsafe_root)

    # Then: no unsafe file is evaluated and each corpus reports its discovery failure
    assert empty_report.case_count == 0
    assert empty_report.failures[0].check_name == "discovery"
    assert unsafe_report.case_count == 0
    assert unsafe_report.failures[0].check_name == "discovery"
    assert unsafe_report.failures[0].path.name == "escape.yaml"


def test_run_golden_corpus_when_duplicate_case_ids_records_every_impacted_path(
    tmp_path: Path,
) -> None:
    # Given: two independently loadable fixtures that reuse one case identifier
    root = tmp_path / "goldens"
    family = root / "research_answers"
    family.mkdir(parents=True)
    (family / "first.yaml").write_text(_case_document("duplicate"), encoding="utf-8")
    (family / "second.yaml").write_text(_case_document("duplicate"), encoding="utf-8")

    # When: the runner aggregates duplicate-ID diagnostics instead of aborting
    from vnalpha.evals.runner import run_golden_corpus

    report = run_golden_corpus(root)

    # Then: both fixture paths receive an actionable duplicate-case failure
    assert {failure.path.name for failure in report.failures} == {
        "first.yaml",
        "second.yaml",
    }
    assert {failure.check_name for failure in report.failures} == {"duplicate_case_id"}


def test_run_golden_corpus_when_utf8_load_fails_retains_valid_case(
    tmp_path: Path,
) -> None:
    # Given: one invalid UTF-8 YAML file alongside one independently valid fixture
    root = tmp_path / "goldens"
    family = root / "research_answers"
    family.mkdir(parents=True)
    (family / "broken.yaml").write_bytes(b"\xff\xfe")
    (family / "valid.yaml").write_text(_case_document("valid_case"), encoding="utf-8")

    # When: the runner processes each discovered fixture independently
    from vnalpha.evals.runner import run_golden_corpus

    report = run_golden_corpus(root)

    # Then: decoding becomes a per-file load failure without aborting the valid case
    assert report.source_count == 2
    assert report.case_count == 1
    assert report.evaluations[0].case_id == "valid_case"
    assert report.failures[0].path.name == "broken.yaml"
    assert report.failures[0].check_name == "load"


def test_run_golden_corpus_when_three_paths_share_case_id_emits_one_failure_each(
    tmp_path: Path,
) -> None:
    # Given: three independently valid fixtures with one repeated case identifier
    root = tmp_path / "goldens"
    family = root / "research_answers"
    family.mkdir(parents=True)
    for name in ("first.yaml", "second.yaml", "third.yaml"):
        (family / name).write_text(_case_document("duplicate"), encoding="utf-8")

    # When: duplicate case IDs are aggregated after loading all fixture paths
    from vnalpha.evals.runner import run_golden_corpus

    report = run_golden_corpus(root)

    # Then: each involved path receives exactly one stable duplicate diagnostic
    duplicates = tuple(
        failure
        for failure in report.failures
        if failure.check_name == "duplicate_case_id"
    )
    assert len(duplicates) == 3
    assert tuple(failure.path.name for failure in duplicates) == (
        "first.yaml",
        "second.yaml",
        "third.yaml",
    )
