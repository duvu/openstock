from __future__ import annotations

from datetime import date
from json import dumps, loads
from traceback import format_exception

import pytest

from vnalpha.data_availability.artifact_readiness_models import ReadinessCapability
from vnalpha.provisioning_queue import (
    MAX_GOAL_PAYLOAD_BYTES,
    InvalidProvisioningGoalError,
    QueueDataset,
    QueueEntityType,
    goal_type,
)
from vnalpha.provisioning_queue.models import (
    EnsureCurrentSymbolGoal,
    FinalizeMarketSessionGoal,
    GoalEnrichment,
    GoalType,
    RefreshMode,
    SyncDatasetRangeGoal,
    goal_identity,
    parse_goal_payload,
)


def test_provisioning_goal_contract() -> None:
    first = EnsureCurrentSymbolGoal(
        symbol="fpt",
        effective_date=date(2026, 7, 21),
        desired_capability=ReadinessCapability.CANDIDATE_RANKING,
        allowed_fallback=ReadinessCapability.PRICE_ANALYSIS,
        requested_enrichments=(
            GoalEnrichment.VALUATION_CONTEXT,
            GoalEnrichment.FUNDAMENTAL_CONTEXT,
            GoalEnrichment.VALUATION_CONTEXT,
        ),
        refresh_mode=RefreshMode.CACHE_FIRST,
        source_policy_version="policy-v1",
        contract_version="current-symbol-v1",
    )
    equivalent = EnsureCurrentSymbolGoal(
        symbol="FPT",
        effective_date=date(2026, 7, 21),
        desired_capability=ReadinessCapability.CANDIDATE_RANKING,
        allowed_fallback=ReadinessCapability.PRICE_ANALYSIS,
        requested_enrichments=(
            GoalEnrichment.FUNDAMENTAL_CONTEXT,
            GoalEnrichment.VALUATION_CONTEXT,
        ),
        refresh_mode=RefreshMode.CACHE_FIRST,
        source_policy_version="policy-v1",
        contract_version="current-symbol-v1",
    )
    distinct = EnsureCurrentSymbolGoal(
        symbol="FPT",
        effective_date=date(2026, 7, 21),
        desired_capability=ReadinessCapability.CANDIDATE_RANKING,
        allowed_fallback=ReadinessCapability.PRICE_ANALYSIS,
        requested_enrichments=(GoalEnrichment.FLOW_CONTEXT,),
        refresh_mode=RefreshMode.CACHE_FIRST,
        source_policy_version="policy-v1",
        contract_version="current-symbol-v1",
    )
    range_goal = SyncDatasetRangeGoal(
        dataset=QueueDataset.INDEX_OHLCV,
        entity_type=QueueEntityType.INDEX,
        entity_id="VNINDEX",
        start_date=date(2026, 7, 20),
        end_date=date(2026, 7, 21),
        refresh_mode=RefreshMode.FORCE_REFRESH,
        source_policy_version="policy-v1",
        contract_version="dataset-range-v1",
    )
    finalization_goal = FinalizeMarketSessionGoal(
        maintenance_run_id="maintenance-2026-07-21",
        resolved_session=date(2026, 7, 21),
        frozen_universe_hash="universe-v1",
        source_policy_version="policy-v1",
        finalization_contract_version="finalization-v1",
    )

    assert first.symbol == "FPT"
    assert first.requested_enrichments == (
        GoalEnrichment.FUNDAMENTAL_CONTEXT,
        GoalEnrichment.VALUATION_CONTEXT,
    )
    assert goal_identity(first) == goal_identity(equivalent)
    assert goal_identity(first) != goal_identity(distinct)
    assert goal_identity(first) != goal_identity(range_goal)
    assert goal_identity(first) != goal_identity(finalization_goal)
    assert goal_type(first) is GoalType.ENSURE_CURRENT_SYMBOL
    assert goal_type(range_goal) is GoalType.SYNC_DATASET_RANGE
    assert goal_type(finalization_goal) is GoalType.FINALIZE_MARKET_SESSION
    assert parse_goal_payload(first.payload_json()) == first
    assert parse_goal_payload(range_goal.payload_json()) == range_goal
    assert parse_goal_payload(finalization_goal.payload_json()) == finalization_goal
    for distinct_range_goal in (
        range_goal.model_copy(update={"entity_id": "HNXINDEX"}),
        range_goal.model_copy(update={"start_date": date(2026, 7, 19)}),
        range_goal.model_copy(update={"end_date": date(2026, 7, 22)}),
        range_goal.model_copy(update={"source_policy_version": "policy-v2"}),
        range_goal.model_copy(update={"contract_version": "dataset-range-v2"}),
    ):
        assert goal_identity(range_goal) != goal_identity(distinct_range_goal)
    for unsupported_schema in ("2", "true", "1.0"):
        with pytest.raises(InvalidProvisioningGoalError):
            parse_goal_payload(
                first.payload_json().replace(
                    '"schema_version":1', f'"schema_version":{unsupported_schema}'
                )
            )
    for versionless_goal in (first, range_goal, finalization_goal):
        versionless_payload = loads(versionless_goal.payload_json())
        versionless_payload.pop("schema_version")
        with pytest.raises(InvalidProvisioningGoalError):
            parse_goal_payload(dumps(versionless_payload))
    with pytest.raises(InvalidProvisioningGoalError):
        parse_goal_payload(
            first.payload_json().replace("VALUATION_CONTEXT", "UNKNOWN_CONTEXT")
        )
    with pytest.raises(InvalidProvisioningGoalError):
        parse_goal_payload(
            range_goal.payload_json().replace("index.ohlcv", "equity.ohlcv")
        )
    with pytest.raises(InvalidProvisioningGoalError):
        parse_goal_payload(
            first.payload_json().replace("ENSURE_CURRENT_SYMBOL", "UNKNOWN_GOAL")
        )
    for payload in (
        first.payload_json().replace("FPT", "PASSWORD=secret-value"),
        range_goal.payload_json().replace("VNINDEX", "index; DROP TABLE jobs"),
        range_goal.payload_json().replace("2026-07-20", "2020-07-20"),
        first.payload_json().replace("policy-v1", "https://example.invalid/$(curl)"),
        first.payload_json()[:-1] + ',"credential":"Bearer secret-value"}',
        "x" * (MAX_GOAL_PAYLOAD_BYTES + 1),
    ):
        with pytest.raises(InvalidProvisioningGoalError) as error:
            parse_goal_payload(payload)
        assert "secret-value" not in str(error.value)
        assert "secret-value" not in "".join(format_exception(error.value))
