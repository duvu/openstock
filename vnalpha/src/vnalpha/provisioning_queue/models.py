from __future__ import annotations

from datetime import date
from enum import StrEnum
from hashlib import sha256
from json import dumps
from typing import Annotated, Final, Literal, TypeAlias, assert_never

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError
from pydantic.functional_validators import field_validator, model_validator

from vnalpha.data_availability.artifact_readiness_models import ReadinessCapability

CURRENT_GOAL_SCHEMA_VERSION: Final = 1


class GoalType(StrEnum):
    ENSURE_CURRENT_SYMBOL = "ENSURE_CURRENT_SYMBOL"
    SYNC_DATASET_RANGE = "SYNC_DATASET_RANGE"
    FINALIZE_MARKET_SESSION = "FINALIZE_MARKET_SESSION"


class GoalEnrichment(StrEnum):
    COMPANY_CONTEXT = "COMPANY_CONTEXT"
    SESSION_CONTEXT = "SESSION_CONTEXT"
    FUNDAMENTAL_CONTEXT = "FUNDAMENTAL_CONTEXT"
    OFFICIAL_EVENT_CONTEXT = "OFFICIAL_EVENT_CONTEXT"
    SHARE_COUNT_CONTEXT = "SHARE_COUNT_CONTEXT"
    FLOW_CONTEXT = "FLOW_CONTEXT"
    VALUATION_CONTEXT = "VALUATION_CONTEXT"


class RefreshMode(StrEnum):
    CACHE_FIRST = "CACHE_FIRST"
    FORCE_REFRESH = "FORCE_REFRESH"


class InvalidProvisioningGoalError(ValueError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class _GoalModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_policy_version: str

    @field_validator("source_policy_version")
    @classmethod
    def _normalize_source_policy_version(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("source_policy_version must not be empty")
        return normalized

    def payload_json(self) -> str:
        return dumps(
            self.model_dump(mode="json"), separators=(",", ":"), sort_keys=True
        )


class EnsureCurrentSymbolGoal(_GoalModel):
    goal_type: Literal[GoalType.ENSURE_CURRENT_SYMBOL] = GoalType.ENSURE_CURRENT_SYMBOL
    schema_version: Literal[CURRENT_GOAL_SCHEMA_VERSION] = CURRENT_GOAL_SCHEMA_VERSION
    symbol: str
    effective_date: date
    desired_capability: ReadinessCapability
    allowed_fallback: ReadinessCapability | None = None
    requested_enrichments: tuple[GoalEnrichment, ...] = ()
    refresh_mode: RefreshMode = RefreshMode.CACHE_FIRST
    contract_version: str

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("symbol must not be empty")
        return normalized

    @field_validator("requested_enrichments")
    @classmethod
    def _normalize_enrichments(
        cls, value: tuple[GoalEnrichment, ...]
    ) -> tuple[GoalEnrichment, ...]:
        return tuple(sorted(set(value), key=lambda enrichment: enrichment.value))

    @field_validator("contract_version")
    @classmethod
    def _normalize_contract_version(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("contract_version must not be empty")
        return normalized

    @model_validator(mode="after")
    def _validate_fallback(self) -> EnsureCurrentSymbolGoal:
        if self.allowed_fallback is self.desired_capability:
            raise ValueError("allowed_fallback must differ from desired_capability")
        return self


class SyncDatasetRangeGoal(_GoalModel):
    goal_type: Literal[GoalType.SYNC_DATASET_RANGE] = GoalType.SYNC_DATASET_RANGE
    schema_version: Literal[CURRENT_GOAL_SCHEMA_VERSION] = CURRENT_GOAL_SCHEMA_VERSION
    dataset: str
    entity_type: str
    entity_id: str
    start_date: date
    end_date: date
    refresh_mode: RefreshMode = RefreshMode.CACHE_FIRST
    contract_version: str

    @field_validator("dataset", "entity_type", "entity_id", "contract_version")
    @classmethod
    def _normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("goal identity fields must not be empty")
        return normalized

    @model_validator(mode="after")
    def _validate_date_range(self) -> SyncDatasetRangeGoal:
        if self.start_date > self.end_date:
            raise ValueError("start_date must not be after end_date")
        return self


class FinalizeMarketSessionGoal(_GoalModel):
    goal_type: Literal[GoalType.FINALIZE_MARKET_SESSION] = (
        GoalType.FINALIZE_MARKET_SESSION
    )
    schema_version: Literal[CURRENT_GOAL_SCHEMA_VERSION] = CURRENT_GOAL_SCHEMA_VERSION
    maintenance_run_id: str
    resolved_session: date
    frozen_universe_hash: str
    finalization_contract_version: str

    @field_validator(
        "maintenance_run_id", "frozen_universe_hash", "finalization_contract_version"
    )
    @classmethod
    def _normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("goal identity fields must not be empty")
        return normalized


ProvisioningGoal: TypeAlias = (
    EnsureCurrentSymbolGoal | SyncDatasetRangeGoal | FinalizeMarketSessionGoal
)

_GoalPayload = Annotated[
    ProvisioningGoal,
    Field(discriminator="goal_type"),
]
_GOAL_PAYLOAD_ADAPTER: Final = TypeAdapter(_GoalPayload)


def parse_goal_payload(payload_json: str) -> ProvisioningGoal:
    try:
        return _GOAL_PAYLOAD_ADAPTER.validate_json(payload_json)
    except ValidationError as error:
        raise InvalidProvisioningGoalError(str(error)) from error


def goal_identity(goal: ProvisioningGoal) -> str:
    return sha256(goal.payload_json().encode("utf-8")).hexdigest()


def goal_type(goal: ProvisioningGoal) -> GoalType:
    match goal:
        case EnsureCurrentSymbolGoal():
            return GoalType.ENSURE_CURRENT_SYMBOL
        case SyncDatasetRangeGoal():
            return GoalType.SYNC_DATASET_RANGE
        case FinalizeMarketSessionGoal():
            return GoalType.FINALIZE_MARKET_SESSION
        case unreachable:
            assert_never(unreachable)


__all__ = [
    "CURRENT_GOAL_SCHEMA_VERSION",
    "EnsureCurrentSymbolGoal",
    "FinalizeMarketSessionGoal",
    "GoalEnrichment",
    "GoalType",
    "InvalidProvisioningGoalError",
    "ProvisioningGoal",
    "RefreshMode",
    "SyncDatasetRangeGoal",
    "goal_identity",
    "goal_type",
    "parse_goal_payload",
]
