from __future__ import annotations

import json
from typing import Any

import duckdb
import pytest

from vnalpha.assistant.app import AssistantApp
from vnalpha.assistant.executor import AssistantExecutor
from vnalpha.assistant.gateway import FakeLLMClient
from vnalpha.assistant.research_templates import get_research_template
from vnalpha.warehouse.migrations import run_migrations


WORKFLOWS = (
    ("deep_analyze_symbol", {"symbol": "FPT", "date": "2026-07-01"}),
    ("review_market_regime", {"date": "2026-07-01"}),
    ("review_sector_strength", {"date": "2026-07-01", "top": 5}),
    (
        "review_symbol_sector_alignment",
        {"symbol": "FPT", "date": "2026-07-01"},
    ),
    ("summarize_watchlist_deep", {"date": "2026-07-01"}),
    ("generate_shortlist", {"date": "2026-07-01", "limit": 5}),
    (
        "generate_research_scenario",
        {"symbol": "FPT", "date": "2026-07-01"},
    ),
    (
        "review_setup_evidence",
        {
            "symbol": "FPT",
            "setup_type": "ACCUMULATION_BASE",
            "date": "2026-07-01",
        },
    ),
)


@pytest.mark.parametrize("intent,entities", WORKFLOWS)
def test_research_workflow_reaches_grounded_audit(
    intent: str,
    entities: dict[str, Any],
    monkeypatch,
) -> None:
    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn)
    classifier = json.dumps(
        {
            "intent": intent,
            "confidence": 0.98,
            "entities": entities,
            "needs_clarification": False,
            "clarification_question": None,
            "safety_flags": [],
        }
    )
    synthesis = json.dumps(
        {
            "summary": "Research evidence is available for structured review.",
            "basis": "Based only on the deterministic tool payload.",
            "risks_caveats": (
                "Caveat: data freshness and human confirmation remain required."
            ),
            "tool_trace_summary": "The required research tool completed.",
            "missing_data": [],
        }
    )
    llm = FakeLLMClient(responses=[(classifier, {}), (synthesis, {})])

    def fake_execute(self, plan):
        template = get_research_template(plan.intent)
        assert template is not None
        payload = _payload_for(template.required_data_keys, entities)
        return {
            plan.steps[0].step_id: {
                "data": payload,
                "summary": "Deterministic test payload.",
                "warnings": [],
            }
        }

    monkeypatch.setattr(AssistantExecutor, "execute", fake_execute)

    answer, plan = AssistantApp(conn, llm_client=llm).ask(
        "Perform the requested research review",
        date="2026-07-01",
    )

    assert plan.intent == intent
    assert answer.summary.startswith("Research evidence")
    row = conn.execute(
        """
        SELECT intent, groundedness_status, policy_status
        FROM research_answer_audit
        """
    ).fetchone()
    assert row == (intent, "PASS", "PASS")
    conn.close()


def _payload_for(
    required_keys: tuple[str, ...], entities: dict[str, Any]
) -> dict[str, Any]:
    values: dict[str, Any] = {
        "status": "READY",
        "symbol": entities.get("symbol", "FPT"),
        "as_of_date": entities.get("date", "2026-07-01"),
        "technical_context": {},
        "levels": {},
        "quality": "READY",
        "caveats": [],
        "missing_data": [],
        "candidate_count": 1,
        "class_distribution": {"STRONG_CANDIDATE": 1},
        "setup_distribution": {"ACCUMULATION_BASE": 1},
        "methodology": {"version": "test-v1"},
        "candidates": [{"symbol": "FPT", "research_rank": 1}],
        "scenarios": {"base_case": {"condition": "monitor persisted evidence"}},
        "policy_status": "PASS",
        "setup_type": entities.get("setup_type", "ACCUMULATION_BASE"),
        "horizon_sessions": 20,
        "sample_size": 42,
        "methodology_version": {"version": "test-v1"},
        "artifact_refs": ["test:artifact"],
        "freshness": {"as_of_date": entities.get("date", "2026-07-01")},
    }
    return {key: values[key] for key in required_keys} | {
        "artifact_refs": values["artifact_refs"],
        "freshness": values["freshness"],
    }
