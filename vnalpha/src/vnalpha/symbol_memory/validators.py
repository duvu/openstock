from __future__ import annotations

from datetime import date

from vnalpha.symbol_memory.models import ClaimOrigin, MemoryClaim
from vnalpha.symbol_memory.paths import SymbolPathError, normalize_symbol


class MemoryValidationError(ValueError):
    pass


def validate_claim(claim: MemoryClaim) -> None:
    try:
        normalize_symbol(claim.symbol)
    except SymbolPathError as exc:
        raise MemoryValidationError(str(exc)) from exc
    if not claim.claim_id or not claim.claim_type or not claim.predicate:
        raise MemoryValidationError("Claim identity fields are required.")
    if claim.origin is ClaimOrigin.VALIDATED_EVIDENCE:
        if not claim.source_refs:
            raise MemoryValidationError("Validated claims require source references.")
        if not isinstance(claim.as_of_date, date) or claim.observed_at is None:
            raise MemoryValidationError(
                "Validated claims require observed_at and as_of_date."
            )
    if claim.confidence is not None and not 0 <= claim.confidence <= 1:
        raise MemoryValidationError("confidence must be between zero and one.")


__all__ = ["MemoryValidationError", "validate_claim"]
