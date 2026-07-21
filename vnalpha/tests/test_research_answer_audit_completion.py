from __future__ import annotations

import json

import duckdb

from vnalpha.warehouse.migrations import run_migrations


def _intent_response() -> tuple[str, dict]:
    return (
        json.dumps(
            {
                "intent": "deep_analyze_symbol",
                "confidence": 0.99,
                "entities": {"symbol": "FPT", "date": "2026-07-10"},
                "needs_clarification": False,
                "clarification_question": None,
                "safety_flags": [],
            }
        ),
        {},
    )


def _answer_response() -> tuple[str, dict]:
    return (
        json.dumps(
            {
                "summary": "FPT has a persisted score of 0.75 for research review.",
                "basis": "Based on the deterministic deep-symbol payload.",
                "risks_caveats": (
                    "Research-only context; data freshness remains relevant."
                ),
                "tool_trace_summary": "analysis.deep_symbol completed.",
                "missing_data": [],
                "grounded_source_refs": [],
                "research_metadata": {},
            }
        ),
        {"prompt_tokens": 10, "completion_tokens": 20},
    )


def _tool_outputs(plan):
    step = next(s for s in plan.steps if s.tool_name == "analysis.deep_symbol")
    return {
        step.step_id: {
            "data": {
                "tool": "analysis.deep_symbol",
                "available": True,
                "symbol": "FPT",
                "as_of_date": "2026-07-10",
                "candidate": {
                    "score": 0.75,
                    "candidate_class": "WATCH_CANDIDATE",
                    "setup_type": "MOMENTUM_CONTINUATION",
                },
                "feature_context": {"close": 100.0, "ma20": 98.0},
                "levels": {"support_20d": 95.0, "resistance_20d": 105.0},
                "freshness": {"price_bar_date": "2026-07-10"},
                "lineage": {"source": "persisted warehouse"},
                "artifact_refs": ["candidate_score:FPT:2026-07-10"],
                "missing_data": [],
                "caveats": ["Research-only persisted context."],
            },
            "summary": "Persisted deep research context.",
            "warnings": [],
        }
    }


def test_migrations_create_research_answer_audit_table():
    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn)

    row = conn.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_name = 'research_answer_audit'
        """
    ).fetchone()

    assert row == (1,)
    conn.close()
