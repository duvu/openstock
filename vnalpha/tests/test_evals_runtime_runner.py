from __future__ import annotations

from pathlib import Path

from tests.test_evals_runtime_loader import _runtime_case


def test_runtime_replay_when_case_is_seeded_exercises_prepared_turn_boundaries(
    tmp_path: Path,
) -> None:
    # Given: one strict context-injection replay case with local tool and LLM seeds
    path = tmp_path / "market-regime.json"
    path.write_text(_runtime_case("fixture://runtime/market_regime"), encoding="utf-8")
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
