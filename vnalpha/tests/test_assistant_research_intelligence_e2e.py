from __future__ import annotations

import json
from datetime import datetime, timezone

import duckdb

from vnalpha.assistant.app import AssistantApp
from vnalpha.assistant.gateway import FakeLLMClient
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import save_candidate_score, upsert_symbol


TARGET_DATE = "2026-07-01"


def test_deep_watchlist_answer_is_grounded_and_audited() -> None:
    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn)
    _seed_watchlist(conn)
    classifier = json.dumps(
        {
            "intent": "summarize_watchlist_deep",
            "confidence": 0.98,
            "entities": {"date": TARGET_DATE},
            "needs_clarification": False,
            "clarification_question": None,
            "safety_flags": [],
        }
    )
    synthesis = json.dumps(
        {
            "summary": (
                "Research watchlist context contains one persisted strong candidate."
            ),
            "basis": (
                "Evidence comes from class_distribution, setup_distribution, "
                "sector_clusters, and the persisted watchlist artifact."
            ),
            "risks_caveats": (
                "Caveat: this is a screening artifact; fresh data and human review "
                "remain required."
            ),
            "tool_trace_summary": "Used watchlist.summarize_deep.",
            "missing_data": [],
        }
    )
    llm = FakeLLMClient(responses=[(classifier, {}), (synthesis, {})])

    answer, plan = AssistantApp(conn, llm_client=llm).ask(
        "Summarize the watchlist deeply",
        date=TARGET_DATE,
    )

    assert plan.intent == "summarize_watchlist_deep"
    assert plan.steps[0].tool_name == "watchlist.summarize_deep"
    assert "Research watchlist" in answer.summary
    audit = conn.execute(
        """
        SELECT intent, groundedness_status, policy_status, tools_json
        FROM research_answer_audit
        """
    ).fetchone()
    assert audit[:3] == ("summarize_watchlist_deep", "PASS", "PASS")
    assert json.loads(audit[3]) == ["watchlist.summarize_deep"]
    assert conn.execute("SELECT COUNT(*) FROM tool_trace").fetchone()[0] == 1
    conn.close()


def _seed_watchlist(conn) -> None:
    upsert_symbol(conn, "FPT", sector="Technology", industry="Software")
    conn.execute(
        """
        INSERT INTO feature_snapshot (
            symbol, date, close, ma20, ma50, ma100, ma20_slope, ma50_slope,
            volume_ma20, volume_ratio, atr14, return_20d, return_60d,
            rs_20d_vs_vnindex, rs_60d_vs_vnindex, distance_to_ma20,
            distance_to_52w_high, base_range_30d, close_strength,
            volatility_20d, as_of_bar_date, benchmark_as_of_bar_date,
            source_row_count, benchmark_row_count, feature_data_status,
            feature_build_version, feature_generated_at, lineage_json
        ) VALUES (
            'FPT', ?, 129.5, 124.0, 118.0, 110.0, 0.01, 0.008,
            1000000, 1.4, 2.5, 0.08, 0.18, 0.04, 0.10, 0.044,
            -0.03, 0.08, 0.75, 0.02, ?, ?, 60, 60, 'READY',
            'test-v1', ?, '{}'
        )
        """,
        [
            TARGET_DATE,
            TARGET_DATE,
            TARGET_DATE,
            datetime.now(timezone.utc),
        ],
    )
    save_candidate_score(
        conn,
        "FPT",
        TARGET_DATE,
        {
            "score": 0.82,
            "candidate_class": "STRONG_CANDIDATE",
            "setup_type": "ACCUMULATION_BASE",
            "trend_score": 0.85,
            "relative_strength_score": 0.78,
            "volume_score": 0.70,
            "base_score": 0.80,
            "breakout_score": 0.72,
            "risk_quality_score": 0.88,
            "risk_flags": [],
        },
    )
    conn.execute(
        """
        INSERT INTO daily_watchlist (
            date, rank, symbol, score, candidate_class, setup_type,
            risk_flags_json, lineage_json
        ) VALUES (?, 1, 'FPT', 0.82, 'STRONG_CANDIDATE',
                  'ACCUMULATION_BASE', '[]', '{}')
        """,
        [TARGET_DATE],
    )
