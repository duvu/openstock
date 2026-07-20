"""Domain models for official disclosures (issue #259)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Final

DISCLOSURES_CONTRACT_VERSION: Final = "disclosures-v1"

# Only these official authorities can create VERIFIED events. Anything else is
# quarantined rather than trusted.
APPROVED_SOURCE_AUTHORITIES: Final = frozenset({"HSX", "HNX", "UPCOM", "SSC", "ISSUER"})


class EventType(str, Enum):
    """Allowlisted normalized event set (issue #259)."""

    FINANCIAL_REPORT_PUBLICATION = "FINANCIAL_REPORT_PUBLICATION"
    CORPORATE_ACTION_ANNOUNCEMENT = "CORPORATE_ACTION_ANNOUNCEMENT"
    MANAGEMENT_OR_BOARD_CHANGE = "MANAGEMENT_OR_BOARD_CHANGE"
    SHAREHOLDER_MEETING_OR_RESOLUTION = "SHAREHOLDER_MEETING_OR_RESOLUTION"
    TRADING_STATUS_CHANGE = "TRADING_STATUS_CHANGE"


EVENT_TYPES: Final = frozenset(e.value for e in EventType)


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    QUARANTINED = "QUARANTINED"


@dataclass(frozen=True, slots=True)
class DisclosureOccurrence:
    """One immutable raw disclosure occurrence from an approved source.

    ``raw_payload`` is untrusted data: it is stored and hashed but never
    interpreted as instructions.
    """

    source_authority: str
    source_reference: str
    symbol: str
    published_at: str  # ISO date
    raw_title: str
    raw_payload: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("symbol is required")
        if not self.source_reference:
            raise ValueError("source_reference is required")


def occurrence_content_hash(occurrence: DisclosureOccurrence) -> str:
    """Deterministic content hash of the untrusted raw occurrence."""
    payload = {
        "source_authority": occurrence.source_authority,
        "source_reference": occurrence.source_reference,
        "symbol": occurrence.symbol,
        "published_at": occurrence.published_at,
        "raw_title": occurrence.raw_title,
        "raw_payload": occurrence.raw_payload,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def is_approved_source(source_authority: str) -> bool:
    return source_authority in APPROVED_SOURCE_AUTHORITIES


__all__ = [
    "APPROVED_SOURCE_AUTHORITIES",
    "DISCLOSURES_CONTRACT_VERSION",
    "EVENT_TYPES",
    "DisclosureOccurrence",
    "EventType",
    "VerificationStatus",
    "is_approved_source",
    "occurrence_content_hash",
]
