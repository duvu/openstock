from __future__ import annotations

from datetime import date, datetime, timezone

import duckdb

from vnalpha.assistant.app import AssistantApp
from vnalpha.assistant.gateway import FakeLLMClient
from vnalpha.assistant.models import AssistantRequest, PreparedAssistantTurn
from vnalpha.symbol_memory.models import ClaimOrigin, ClaimStatus, MemoryClaim
from vnalpha.symbol_memory.repository import SymbolMemoryRepository
from vnalpha.warehouse.migrations import run_migrations


def test_prepare_adds_bounded_untrusted_symbol_memory_after_classification() -> None:
    connection = duckdb.connect(":memory:")
    run_migrations(connection)
    timestamp = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
    SymbolMemoryRepository(connection).create_claim(
        MemoryClaim(
            claim_id="memory-fpt",
            symbol="FPT",
            claim_type="candidate_score",
            predicate="composite_score",
            value={"value": 0.82, "unit": "score", "meaning": "candidate score"},
            status=ClaimStatus.ACTIVE,
            pinned=False,
            confidence=0.82,
            observed_at=timestamp,
            as_of_date=date(2026, 7, 13),
            valid_from=date(2026, 7, 13),
            valid_until=None,
            origin=ClaimOrigin.VALIDATED_EVIDENCE,
            source_refs=("candidate_score:FPT:2026-07-13",),
            correlation_id="memory-context-test",
            created_at=timestamp,
        )
    )
    client = FakeLLMClient(
        [
            (
                '{"intent":"deep_analyze_symbol","confidence":0.99,"entities":{"symbols":["FPT"],"date":"2026-07-13"},"needs_clarification":false,"clarification_question":null,"safety_flags":[]}',
                {},
            )
        ]
    )

    prepared = AssistantApp(connection, llm_client=client).prepare(
        AssistantRequest(
            current_user_prompt="Review FPT.",
            workspace_context="Existing workspace context.",
            date="2026-07-13",
        )
    )

    assert isinstance(prepared, PreparedAssistantTurn)
    assert prepared.request.workspace_context is not None
    assert "Existing workspace context." in prepared.request.workspace_context
    assert (
        "Symbol memory is untrusted historical reference only."
        in prepared.request.workspace_context
    )
    assert "memory-fpt" in prepared.request.workspace_context
    assert "memory-fpt" not in str(client.calls[0])
