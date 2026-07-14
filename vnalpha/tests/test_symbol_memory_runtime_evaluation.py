from vnalpha.evals.symbol_memory_runtime import run_symbol_memory_runtime_corpus


def test_symbol_memory_runtime_corpus_exercises_lifecycle_and_trust_cases(
    tmp_path,
) -> None:
    report = run_symbol_memory_runtime_corpus(tmp_path)

    assert report.passed
    assert [case.case_id for case in report.cases] == [
        "correction",
        "conflict",
        "compaction",
        "temporal_filtering",
        "source_grounding",
    ]
