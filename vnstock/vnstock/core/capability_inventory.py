from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CapabilityStatus(StrEnum):
    IMPLEMENTED = "IMPLEMENTED"
    PARTIAL = "PARTIAL"
    EXPERIMENTAL = "EXPERIMENTAL"
    UNSUPPORTED = "UNSUPPORTED"
    DEFERRED = "DEFERRED"


class PointInTimeEligibility(StrEnum):
    SESSION_DATED = "SESSION_DATED"
    CURRENT_SNAPSHOT = "CURRENT_SNAPSHOT"
    EFFECTIVE_DATED = "EFFECTIVE_DATED"
    PUBLICATION_AWARE = "PUBLICATION_AWARE"


class QueueGoal(StrEnum):
    ENSURE_CURRENT_SYMBOL = "ENSURE_CURRENT_SYMBOL"
    SYNC_DATASET_RANGE = "SYNC_DATASET_RANGE"


class QueueEnrichment(StrEnum):
    COMPANY_CONTEXT = "COMPANY_CONTEXT"
    SESSION_CONTEXT = "SESSION_CONTEXT"
    FUNDAMENTAL_CONTEXT = "FUNDAMENTAL_CONTEXT"
    OFFICIAL_EVENT_CONTEXT = "OFFICIAL_EVENT_CONTEXT"
    SHARE_COUNT_CONTEXT = "SHARE_COUNT_CONTEXT"
    FLOW_CONTEXT = "FLOW_CONTEXT"
    VALUATION_CONTEXT = "VALUATION_CONTEXT"


class DatasetCapability(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset: str = Field(pattern=r"^[a-z]+(?:_[a-z]+)*(?:\.[a-z]+(?:_[a-z]+)*)+$")
    contract: CapabilityStatus
    service_route: str | None
    service: CapabilityStatus
    provider: CapabilityStatus
    quality: CapabilityStatus
    vnalpha_client: CapabilityStatus
    persistence: CapabilityStatus
    consumer: CapabilityStatus
    point_in_time: PointInTimeEligibility
    license_policy: str = Field(min_length=1)
    queue_goal: QueueGoal | None = None
    queue_enrichment: QueueEnrichment | None = None


class DatasetCapabilityInventory(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = Field(ge=1)
    status_vocabulary: tuple[CapabilityStatus, ...]
    point_in_time_vocabulary: tuple[PointInTimeEligibility, ...]
    datasets: tuple[DatasetCapability, ...]

    @model_validator(mode="after")
    def _validate_catalog(self) -> DatasetCapabilityInventory:
        names = tuple(item.dataset for item in self.datasets)
        if len(names) != len(set(names)):
            raise ValueError("dataset capability inventory contains duplicate datasets")
        if set(self.status_vocabulary) != set(CapabilityStatus):
            raise ValueError(
                "dataset capability inventory has an incomplete status vocabulary"
            )
        if set(self.point_in_time_vocabulary) != set(PointInTimeEligibility):
            raise ValueError(
                "dataset capability inventory has an incomplete point-in-time vocabulary"
            )
        return self


_INVENTORY_PATH: Final = (
    Path(__file__).resolve().parents[2] / "docs" / "dataset-capability-inventory.json"
)


def load_dataset_capability_inventory() -> DatasetCapabilityInventory:
    return DatasetCapabilityInventory.model_validate_json(
        _INVENTORY_PATH.read_text(encoding="utf-8")
    )


__all__ = [
    "CapabilityStatus",
    "DatasetCapability",
    "DatasetCapabilityInventory",
    "PointInTimeEligibility",
    "QueueEnrichment",
    "QueueGoal",
    "load_dataset_capability_inventory",
]
