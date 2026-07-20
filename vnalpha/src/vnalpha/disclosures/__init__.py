"""Official disclosures as verified symbol events (issue #259).

Persists official exchange/company disclosures with trustworthy publication
metadata and normalizes a small allowlisted event set. Stored content is
treated as untrusted data, never executable instructions.
"""

from vnalpha.disclosures.models import (
    APPROVED_SOURCE_AUTHORITIES,
    EVENT_TYPES,
    DisclosureOccurrence,
    EventType,
    VerificationStatus,
    occurrence_content_hash,
)
from vnalpha.disclosures.repository import (
    as_of_events,
    ingest_occurrence,
    normalize_event,
)

__all__ = [
    "APPROVED_SOURCE_AUTHORITIES",
    "EVENT_TYPES",
    "DisclosureOccurrence",
    "EventType",
    "VerificationStatus",
    "as_of_events",
    "ingest_occurrence",
    "normalize_event",
    "occurrence_content_hash",
]
