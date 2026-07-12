from __future__ import annotations

import socket
from pathlib import Path

import pytest

from tests.test_evals_runtime_loader import _runtime_case


def test_runtime_replay_when_case_is_seeded_exercises_prepared_turn_boundaries(
    tmp_path: Path,
) -> None:
    # Given: one strict context-injection replay case with local tool and LLM seeds
    path = tmp_path / "market-regime.json"
    path.write_text(
        _runtime_case("fixture://runtime/market_regime"), encoding="utf-8"
    )
    from vnalpha.evals.runtime_loader import load_runtime_replay_case

    case = load_runtime_replay_case(path)

    # When: the offline runtime runner drives the production assistant lifecycle
    from vnalpha.evals.runtime_runner import run_runtime_replay_case

    result = run_runtime_replay_case(case)

    # Then: intent, exact plan, trace, validation, audit, and context isolation pass
    assert result.passed
    assert {check.name for check in result.checks} == {
        "outcome",
        "intent",
        "plan",
        "successful_trace_tools",
        "groundedness_status",
        "policy_status",
        "fallback_used",
        "audit_status",
        "required_missing_data",
        "forbidden_source_refs",
        "claim_source_refs",
        "classifier_context_isolation",
    }


def test_network_guard_when_socket_is_opened_fails_closed() -> None:
    # Given: runtime replay's process-level no-network boundary
    from vnalpha.evals.network_guard import (
        NetworkAccessProhibitedError,
        prohibit_network,
    )

    # When: code inside the boundary attempts to create a network connection
    with prohibit_network(), pytest.raises(NetworkAccessProhibitedError):
        socket.create_connection(("127.0.0.1", 9), timeout=0.01)

    # Then: leaving the boundary restores ordinary socket construction
    plain_socket = socket.socket()
    plain_socket.close()


def test_runtime_corpus_when_private_root_is_supplied_runs_every_json_case(
    tmp_path: Path,
) -> None:
    # Given: a private corpus containing one strict runtime-replay case
    (tmp_path / "market-regime.json").write_text(
        _runtime_case("fixture://runtime/market_regime"), encoding="utf-8"
    )

    # When: corpus discovery and replay execute through the public aggregate runner
    from vnalpha.evals.runtime_runner import run_runtime_replay_corpus

    report = run_runtime_replay_corpus(tmp_path)

    # Then: the discovered case contributes one passing aggregate result
    assert report.source_count == 1
    assert report.passed_case_count == 1
    assert report.failure_count == 0
    assert report.passed


def test_default_runtime_corpus_when_packaged_covers_all_intents_and_negatives() -> (
    None
):
    # Given: the package-owned runtime corpus and canonical research intent taxonomy
    from vnalpha.assistant.research_intelligence_intents import (
        RESEARCH_INTELLIGENCE_INTENTS,
    )
    from vnalpha.evals.runtime_corpus import (
        DEFAULT_RUNTIME_CASES_ROOT,
        run_runtime_replay_corpus,
    )
    from vnalpha.evals.runtime_loader import load_runtime_replay_case

    paths = tuple(sorted(Path(str(DEFAULT_RUNTIME_CASES_ROOT)).glob("*.json")))
    cases = tuple(load_runtime_replay_case(path) for path in paths)

    # When: every packaged seed and negative replay is executed
    report = run_runtime_replay_corpus()

    # Then: intent coverage and named regressions are complete and passing
    assert {case.expected.intent for case in cases} >= RESEARCH_INTELLIGENCE_INTENTS
    assert {case.case_id for case in cases} >= {
        "market_regime_context_injection",
        "missing_grounded_refs",
        "fabricated_number_rewrite",
        "sector_strength_missing_artifact",
        "invalid_explicit_date",
        "scenario_unsafe_wording_rewrite",
        "deep_symbol_claim_mapping",
    }
    assert report.source_count == len(cases) >= 10
    assert report.passed
